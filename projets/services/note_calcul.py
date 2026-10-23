"""
Note de calcul d'un projet (issue #96) : DONNÉES.

Rassemble, pour un projet, ce qui justifie les résultats : données d'entrée,
matériaux, combinaisons, hypothèses, puis pour chaque élément la descente
de charges et les formules appliquées (traces enregistrées par le moteur au
moment du calcul), le résultat retenu et les quantités.

Règles :
  - aucune valeur n'est recalculée ni arrondie ici : tout vient du moteur
    (traces et résultats enregistrés) ou des données du projet ;
  - chaque valeur porte son origine : « calculé » (produit par le moteur),
    « saisi » (donnée de l'utilisateur, ou valeur modifiée par l'ingénieur
    à la validation) ou « estimé » (valeur par défaut, valeur normative,
    ratio) ;
  - aucun texte de l'assistant IA n'est repris.

Le rendu PDF est dans note_calcul_pdf.py.
"""

from django.utils import timezone

from moteur_calcul.constantes import (
    GAMMA_ACIER, GAMMA_BETON, LIMITE_ELASTIQUE_ACIER, POIDS_VOLUMIQUE_BETON, RESISTANCE_BETON_DEFAUT,
)
from moteur_calcul.version import NORME, identifiant_version

from ..models import ElementStructurel, Projet
from .dqe_calculator import largeurs_poutres_validees, quantites_element
from .parametres_projet import parametres_structure

CALCULE, SAISI, ESTIME = "calculé", "saisi", "estimé"

MENTION_RESPONSABILITE = (
    "Cette note est produite par le logiciel à partir des données du projet et des règles de "
    "pré-dimensionnement du BAEL 91 modifié 99. Elle justifie un pré-dimensionnement et un métré : ce n'est "
    "ni une note de calcul d'exécution, ni un plan d'exécution. Sections, ferraillages et quantités doivent "
    "être vérifiés et validés par un ingénieur structure qualifié, qui en assume seul la responsabilité. "
    "Les valeurs « estimé » reposent sur des valeurs par défaut, des valeurs normatives ou des ratios ; les "
    "valeurs « saisi » sur les données fournies par l'utilisateur."
)

ORDRE_TYPES = ("poteau", "semelle", "poutre", "longrine", "semelle_filante", "dalle", "chainage")
TITRES_TYPES = {
    "poteau": "Poteaux", "semelle": "Semelles isolées", "poutre": "Poutres", "longrine": "Longrines",
    "semelle_filante": "Semelles filantes", "dalle": "Dalles", "chainage": "Chaînages",
}
ORIGINES_GEOMETRIE = {
    "trame": "trame régulière", "plan": "lue dans le plan importé", "saisi": "placée par l'utilisateur",
}
SOURCES_STRUCTURE = {
    "trame": "Trame régulière saisie (travées et portées).",
    "plan": "Poteaux lus dans le plan importé.",
    "saisie": "Poteaux placés par l'utilisateur sur un plan d'architecte (non lus dans le plan).",
    "mixte": "Plan ou trame modifiés à la main par l'utilisateur (poteaux ajoutés ou déplacés).",
}
USAGES = {"habitation": "Habitation", "bureau": "Bureaux", "commerce": "Commerce", "industriel": "Industriel"}

# Résultats affichés par type : (clé, libellé, unité). Clés absentes ignorées.
RESULTATS = {
    "poteau": [("charge_elu_kn", "Effort ultime Nu", "kN"), ("charge_els_kn", "Effort de service Ns", "kN"),
               ("cote_cm", "Côté a", "cm"), ("elancement", "Élancement λ", ""),
               ("coefficient_alpha", "Coefficient α", ""), ("section_acier_retenue_cm2", "Acier longitudinal A", "cm²"),
               ("barres_proposees", "Barres proposées", "")],
    "semelle": [("charge_dimensionnement_kn", "Effort de dimensionnement", "kN"),
                ("contrainte_sol_kn_m2", "Contrainte admissible du sol", "kN/m²"), ("cote_cm", "Côté A", "cm"),
                ("hauteur_cm", "Hauteur h", "cm"), ("pression_sol_kn_m2", "Pression sur le sol", "kN/m²"),
                ("section_acier_par_direction_cm2", "Acier par direction", "cm²"),
                ("barres_proposees", "Barres proposées (par direction)", ""),
                ("espacement_barres_cm", "Espacement", "cm"), ("poids_acier_total_kg", "Poids d'acier", "kg")],
    "poutre": [("charge_elu_kn_m", "Charge ultime pu", "kN/m"), ("charge_els_kn_m", "Charge de service pser", "kN/m"),
               ("largeur_cm", "Largeur b", "cm"), ("hauteur_cm", "Hauteur h", "cm"),
               ("moment_flechissant_knm", "Moment ultime Mu", "kN·m"), ("moment_reduit", "Moment réduit µ", ""),
               ("section_acier_theorique_cm2", "Acier tendu As", "cm²"), ("section_acier_min_cm2", "Acier minimal", "cm²"),
               ("barres_proposees", "Barres proposées", ""), ("effort_tranchant_kn", "Effort tranchant Vu", "kN"),
               ("contrainte_cisaillement_mpa", "Cisaillement τu", "MPa"),
               ("contrainte_cisaillement_limite_mpa", "Cisaillement limite", "MPa")],
    "dalle": [("epaisseur_cm", "Épaisseur", "cm"), ("alpha", "Rapport Lx / Ly", "")],
    "chainage": [("largeur_cm", "Largeur", "cm"), ("hauteur_cm", "Hauteur", "cm")],
    "semelle_filante": [("largeur_cm", "Largeur", "cm"), ("hauteur_cm", "Hauteur", "cm")],
}
RESULTATS["longrine"] = RESULTATS["poutre"]
CLES_ESTIMEES = {  # drapeau du résultat -> clés concernées, marquées « estimé »
    "hypothese_sol": ("contrainte_sol_kn_m2",),
}


class NoteImpossible(Exception):
    """Données insuffisantes : la note n'est pas produite (rien d'inventé)."""

    def __init__(self, message, champs=None):
        super().__init__(message)
        self.champs = champs or []


def _donnee(libelle, valeur, unite, origine, detail=""):
    return {"libelle": libelle, "valeur": valeur, "unite": unite, "origine": origine, "detail": detail}


def _donnees_entree(projet, hyp):
    origine_g = {"couches": (CALCULE, "calculée à partir de la composition du plancher saisie"),
                 "saisie": (SAISI, "valeur saisie"),
                 "forfait": (ESTIME, "valeur par défaut validée par le technicien (plancher à hourdis 16+4)")}
    og, dg = origine_g.get(hyp.origine_g, (ESTIME, hyp.origine_g))
    oq, dq = ((SAISI, "valeur saisie") if hyp.origine_q == "saisie"
              else (ESTIME, f"valeur normative de l'usage ({hyp.origine_q.split(':', 1)[-1]})"))
    d = [
        _donnee("Usage du bâtiment", USAGES.get(projet.usage_batiment, projet.usage_batiment), "", SAISI),
        _donnee("Nombre de niveaux", projet.nb_niveaux, "", SAISI),
        _donnee("Hauteur d'étage", projet.hauteur_etage, "m", SAISI),
        _donnee("Charge permanente des planchers G", hyp.g_plancher_kn_m2, "kN/m²", og, dg),
        _donnee("Charge d'exploitation Q", hyp.q_kn_m2, "kN/m²", oq, dq),
        _donnee("Charge d'exploitation de toiture", hyp.q_toiture_kn_m2, "kN/m²", ESTIME,
                "valeur validée par le technicien BTP"),
        _donnee("Type de toiture", "charpente" if hyp.type_toiture == "charpente" else "toiture-terrasse (dalle)",
                "", SAISI),
    ]
    if hyp.type_toiture == "charpente":
        d.append(_donnee("Charge permanente de la charpente", hyp.g_toiture_kn_m2, "kN/m²", ESTIME,
                         "valeur validée par le technicien BTP (règle B14)"))
    if projet.contrainte_sol_kn_m2 is not None:
        d.append(_donnee("Contrainte admissible du sol", projet.contrainte_sol_kn_m2, "kN/m²", SAISI, "valeur saisie"))
    else:
        d.append(_donnee("Contrainte admissible du sol", hyp.contrainte_sol_effective, "kN/m²", ESTIME,
                         "valeur par défaut : étude géotechnique non renseignée"))
    if hyp.poids_murs_kn_m2 is not None:
        d.append(_donnee("Poids des murs", hyp.poids_murs_kn_m2, "kN/m² de mur", SAISI, "valeur saisie"))
    else:
        d.append(_donnee("Poids des murs", "non renseigné", "", "", "charge des murs NON comptée"))
    d += [
        _donnee("Poids propre de l'ossature", "inclus" if hyp.inclure_poids_propre_ossature else "non inclus", "", SAISI),
        _donnee("Dimensionnement des semelles", f"à l'{hyp.methode_semelles}", "", SAISI),
    ]
    return d


def _materiaux(hyp):
    fbu = round(0.85 * RESISTANCE_BETON_DEFAUT / GAMMA_BETON, 2)
    fsu = round(LIMITE_ELASTIQUE_ACIER / GAMMA_ACIER, 1)
    defaut = "valeur par défaut du moteur, confirmée par le technicien (règle B13)"
    return [
        _donnee("Résistance du béton fc28", RESISTANCE_BETON_DEFAUT, "MPa", ESTIME, defaut),
        _donnee("Limite élastique de l'acier fe", LIMITE_ELASTIQUE_ACIER, "MPa", ESTIME, defaut),
        _donnee("Coefficient de sécurité du béton γb", GAMMA_BETON, "", ESTIME, "BAEL 91 (situation durable)"),
        _donnee("Coefficient de sécurité de l'acier γs", GAMMA_ACIER, "", ESTIME, "BAEL 91 (situation durable)"),
        _donnee("Résistance de calcul du béton fbu = 0,85 fc28 / γb", fbu, "MPa", CALCULE),
        _donnee("Résistance de calcul de l'acier fsu = fe / γs", fsu, "MPa", CALCULE),
        _donnee("Poids volumique du béton armé", hyp.poids_volumique_beton_kn_m3 or POIDS_VOLUMIQUE_BETON, "kN/m³",
                ESTIME, "valeur courante"),
    ]


def _combinaisons(hyp):
    return [
        f"ELU (état limite ultime) : {hyp.gamma_g_elu:g} G + {hyp.gamma_q_elu:g} Q".replace(".", ","),
        f"ELS (état limite de service) : {hyp.gamma_g_els:g} G + {hyp.gamma_q_els:g} Q".replace("1 G", "G")
        .replace("1 Q", "Q").replace(".", ","),
    ]


def _barres(v):
    if not isinstance(v, dict) or not v.get("nombre_barres"):
        return None
    return f"{v['nombre_barres']} HA {v['diametre_mm']} ({v['section_reelle_cm2']:g} cm²)"


def _resultats(element, calcul, valide):
    """Valeurs retenues : celles validées par l'ingénieur si elles existent.
    Origine « saisi » quand l'ingénieur a changé la valeur du moteur."""
    retenu = valide or calcul
    lignes = []
    estimes = {k for drapeau, cles in CLES_ESTIMEES.items() if retenu.get(drapeau) for k in cles}
    for cle, libelle, unite in RESULTATS.get(element.type_element, []):
        if cle not in retenu or retenu[cle] is None:
            continue
        valeur = _barres(retenu[cle]) if cle == "barres_proposees" else retenu[cle]
        if valeur is None or isinstance(valeur, (dict, list)):
            continue
        if valide and cle in valide and valide.get(cle) != calcul.get(cle):
            origine, detail = SAISI, f"modifié à la validation (moteur : {calcul.get(cle)})"
        elif cle in estimes:
            origine, detail = ESTIME, "valeur par défaut"
        else:
            origine, detail = CALCULE, ""
        lignes.append(_donnee(libelle, valeur, unite, origine, detail))
    return lignes


def _quantites(element, retenu, largeurs):
    q = quantites_element(element, retenu, largeurs)
    if q["manquants"]:
        return {"manquants": q["manquants"]}
    acier_origine = CALCULE if q["source_acier"] == "calcul_moteur" else ESTIME
    return {
        "manquants": [],
        "nombre_identiques": q["n"],
        "beton_m3": float(q["volume"]), "formule_beton": q["formules"].get("beton", ""),
        "coffrage_m2": float(q["coffrage"]), "formule_coffrage": q["formules"].get("coffrage", ""),
        "acier_kg": float(q["poids"]), "origine_acier": acier_origine,
        "detail_acier": (f"ratio de {float(q['ratio_acier']):g} kg/m³" if q["ratio_acier"] is not None
                         else "poids calculé par le moteur"),
        "hypothese_beton": q["hyp_beton"] or "",
    }


def _cle_tri(e):
    import re

    nombres = [int(n) for n in re.findall(r"\d+", e.identifiant or "")]
    rang = ORDRE_TYPES.index(e.type_element) if e.type_element in ORDRE_TYPES else len(ORDRE_TYPES)
    return (rang, nombres, e.identifiant or "")


def construire_note(projet: Projet, auteur: str = "") -> dict:
    """Données complètes de la note. Lève NoteImpossible si le projet n'a
    pas d'élément ou s'il manque une donnée d'entrée."""
    from .parametres_projet import ParametresIncomplets

    elements = sorted(projet.elements.all(), key=_cle_tri)
    if not elements:
        raise NoteImpossible("Aucun élément calculé : lancez le calcul du projet avant de produire la note.")
    try:
        prm = parametres_structure(projet, avec_grille=False)
    except ParametresIncomplets as exc:
        raise NoteImpossible("Données du projet incomplètes : la note ne peut pas être produite.",
                             [m["libelle"] for m in exc.manquants]) from exc
    hyp = prm["hyp"]
    largeurs = largeurs_poutres_validees(projet)

    groupes, totaux = [], {"beton_m3": 0.0, "coffrage_m2": 0.0, "acier_calcule_kg": 0.0, "acier_estime_kg": 0.0}
    sans_trace = 0
    for type_element in [t for t in ORDRE_TYPES if any(e.type_element == t for e in elements)] + sorted(
            {e.type_element for e in elements} - set(ORDRE_TYPES)):
        fiches = []
        for e in (x for x in elements if x.type_element == type_element):
            calcul = dict(e.resultat_calcul or {})
            valide = dict(e.resultat_valide or {}) if e.resultat_valide else None
            trace = [dict(t) for t in calcul.get("trace") or []]
            if not trace:
                sans_trace += 1
            retenu = valide or calcul
            quantites = _quantites(e, retenu, largeurs) if retenu else {"manquants": ["aucun résultat"]}
            if not quantites["manquants"]:
                totaux["beton_m3"] += quantites["beton_m3"]
                totaux["coffrage_m2"] += quantites["coffrage_m2"]
                cle = "acier_calcule_kg" if quantites["origine_acier"] == CALCULE else "acier_estime_kg"
                totaux[cle] += quantites["acier_kg"]
            fiches.append({
                "identifiant": e.identifiant,
                "type": e.type_element,
                "libelle_type": e.get_type_element_display(),
                "statut": e.statut, "libelle_statut": e.get_statut_display(),
                "position": ([e.position_x, e.position_y] if e.position_x is not None and e.position_y is not None
                             else None),
                "origine_geometrie": ORIGINES_GEOMETRIE.get(e.origine_geometrie, "non renseignée"),
                "nombre_identiques": e.nombre_identiques or 1,
                "portee_m": e.portee,
                "trace": trace,
                "resultats": _resultats(e, calcul, valide),
                "quantites": quantites,
            })
        groupes.append({"type": type_element, "titre": TITRES_TYPES.get(type_element, type_element), "elements": fiches})

    nb_valides = sum(1 for e in elements if e.statut == ElementStructurel.Statut.VALIDE)
    avertissements = []
    if nb_valides < len(elements):
        avertissements.append(f"Note PROVISOIRE : {len(elements) - nb_valides} élément(s) sur {len(elements)} "
                              "ne sont pas encore validés par l'ingénieur.")
    if sans_trace:
        avertissements.append(f"{sans_trace} élément(s) sans détail de calcul enregistré (élément saisi à la main "
                              "ou calculé avant l'enregistrement des étapes) : seuls leurs résultats sont donnés.")
    if hyp.poids_murs_kn_m2 is None:
        avertissements.append("Poids des murs non renseigné : la charge des murs en maçonnerie n'est pas comptée.")

    hypotheses = list(dict.fromkeys(prm["hypotheses"]))
    return {
        "projet": {"id": projet.id, "nom": projet.nom, "numero_devis": projet.numero_devis or "",
                   "cabinet": getattr(projet.entreprise, "nom", "") if projet.entreprise_id else "",
                   "source_structure": SOURCES_STRUCTURE.get(projet.source_structure, "non renseignée")},
        "edition": {"date": timezone.localtime().strftime("%d/%m/%Y %H:%M"), "auteur": auteur,
                    "version_moteur": identifiant_version(), "norme": NORME},
        "statut": {"elements": len(elements), "valides": nb_valides, "provisoire": nb_valides < len(elements)},
        "mention": MENTION_RESPONSABILITE,
        "donnees_entree": _donnees_entree(projet, hyp),
        "materiaux": _materiaux(hyp),
        "combinaisons": _combinaisons(hyp),
        "hypotheses": hypotheses,
        "avertissements": avertissements,
        "groupes": groupes,
        "totaux": {k: round(v, 3) for k, v in totaux.items()},
    }
