"""
Calcul du DQE (Devis Quantitatif et Estimatif) d'un projet.

Règles (audit du 06/10/2026) :
- AUCUN prix par défaut : seul le barème du cabinet propriétaire du
  projet (EntrepriseParametres.prix_unitaires) est utilisé. Un prix
  manquant bloque la génération avec un message explicite.
- AUCUNE ligne silencieusement omise : un élément validé dont une
  dimension manque, un poste saisi incomplet ou un poste à ratio dont la
  géométrie est incomplète lèvent DQEIncomplet avec la liste exhaustive
  des problèmes, pour que l'utilisateur sache exactement quoi corriger.
- Traçabilité : chaque ligne d'acier indique si son poids vient du calcul
  du moteur ("calcul_moteur") ou d'un ratio de référence documenté dans
  moteur_calcul/constantes.py ("ratio_reference"), et chaque hypothèse
  utilisée est remontée dans "hypotheses".
- Montant = quantité ARRONDIE affichée x prix unitaire, arrondi au FCFA :
  le lecteur peut refaire la multiplication sur le document.
"""

from decimal import Decimal, ROUND_HALF_UP, InvalidOperation
from collections import defaultdict

from projets.models import Projet, ElementStructurel, PosteComplementaire

from moteur_calcul.constantes import (
    RATIO_ACIER_POTEAUX_KG_M3,
    RATIO_ACIER_POUTRES_KG_M3,
    RATIO_ACIER_SEMELLES_KG_M3,
    RATIO_ACIER_DALLES_KG_M3,
    RATIO_ACIER_ELEMENT_LINEAIRE_LEGER_KG_M3,
    DENSITE_ACIER_KG_M3,
)
from moteur_calcul.formules.postes_ratio import calculer_poste_ratio

# Précision d'affichage des quantités (et base du calcul des montants).
PRECISION_QUANTITE = Decimal("0.001")

# Barème de RÉFÉRENCE (FCFA), relevé sur le DQE CIMBAT n°0017-2026 (villa
# basse 4 pièces). Il n'est JAMAIS appliqué automatiquement : il est
# seulement proposé à l'administrateur du cabinet comme point de départ
# de son propre barème (voir GET /api/referentiel/).
# Agglos 15 pleins : unité CONFIRMÉE m² par le technicien BTP (07/10/2026)
# -- le 9 000 FCFA du DQE CIMBAT est donc un prix au m² de mur. L'ancienne
# clé "agglos_pleins_m3" n'est plus lue (jamais de conversion implicite
# m³ -> m² : voir CLE_PRIX_AGGLOS_PLEINS_OBSOLETE).
PRIX_UNITAIRES_REFERENCE = {
    "beton_m3": 100000,
    "acier_kg": 800,
    "coffrage_m2": 12000,
    "agglos_15_pleins_m2": 9000,
    "agglos_15_creux_m2": 8000,
    "agglos_10_creux_m2": 6000,
    "enduit_m2": 3500,
}

CLE_PRIX_AGGLOS_PLEINS_OBSOLETE = "agglos_pleins_m3"

LIBELLES_PRIX = {
    "beton_m3": "Béton (FCFA/m³)",
    "acier_kg": "Acier (FCFA/kg)",
    "coffrage_m2": "Coffrage (FCFA/m²)",
    "agglos_15_pleins_m2": "Agglos 15 pleins (FCFA/m²)",
    "agglos_15_creux_m2": "Agglos 15 creux (FCFA/m²)",
    "agglos_10_creux_m2": "Agglos 10 creux (FCFA/m²)",
    "enduit_m2": "Enduit (FCFA/m²)",
}

# Ratios d'acier (kg/m³) utilisés quand le moteur ne fournit pas le poids
# réel : milieu de chaque fourchette de moteur_calcul.constantes
# (document technicien BTP, section 5.2). Valeurs documentées, signalées
# comme hypothèse sur chaque ligne concernée.
RATIOS_ACIER_KG_M3 = {
    "poteau": Decimal(str(sum(RATIO_ACIER_POTEAUX_KG_M3) / 2)),    # 125
    "poutre": Decimal(str(sum(RATIO_ACIER_POUTRES_KG_M3) / 2)),    # 150
    "longrine": Decimal(str(sum(RATIO_ACIER_POUTRES_KG_M3) / 2)),  # même physique que poutre
    "semelle": Decimal(str(sum(RATIO_ACIER_SEMELLES_KG_M3) / 2)),  # 50
    "semelle_filante": Decimal(str(sum(RATIO_ACIER_SEMELLES_KG_M3) / 2)),
    "dalle": Decimal(str(sum(RATIO_ACIER_DALLES_KG_M3) / 2)),      # 85
    "chainage": Decimal(str(RATIO_ACIER_ELEMENT_LINEAIRE_LEGER_KG_M3)),  # 90
}


class DQEIncomplet(Exception):
    """Le DQE ne peut pas être produit sans données inventées.

    `problemes` : liste de dicts {"code", "message", ...} -- exhaustive,
    pour que l'interface puisse tout afficher d'un coup.
    """

    def __init__(self, problemes):
        self.problemes = problemes
        super().__init__("; ".join(p["message"] for p in problemes))


def _dec(valeur) -> Decimal:
    return Decimal(str(valeur))


def _q(valeur: Decimal) -> Decimal:
    return valeur.quantize(PRECISION_QUANTITE, rounding=ROUND_HALF_UP)


def _prix(prix_unitaires: dict, cle: str, problemes: list, contexte: str):
    """Prix du barème du cabinet, ou None + problème explicite."""
    brut = prix_unitaires.get(cle)
    if (brut is None or brut == "") and cle == "agglos_15_pleins_m2" \
            and prix_unitaires.get(CLE_PRIX_AGGLOS_PLEINS_OBSOLETE) not in (None, ""):
        problemes.append({
            "code": "PRIX_UNITE_A_CONFIRMER",
            "cle_prix": cle,
            "message": (
                f"Le barème contient un ancien prix « agglos pleins au m³ » "
                f"({prix_unitaires[CLE_PRIX_AGGLOS_PLEINS_OBSOLETE]} FCFA). L'unité validée est le m² de mur : "
                f"renseignez le prix « {LIBELLES_PRIX[cle]} » dans les paramètres du cabinet "
                f"(aucune conversion automatique). Nécessaire pour {contexte}."
            ),
        })
        return None
    if brut is None or brut == "":
        problemes.append({
            "code": "PRIX_MANQUANT",
            "cle_prix": cle,
            "message": (
                f"Prix unitaire « {LIBELLES_PRIX.get(cle, cle)} » non renseigné dans le "
                f"barème du cabinet (nécessaire pour {contexte})."
            ),
        })
        return None
    try:
        pu = _dec(brut)
    except InvalidOperation:
        pu = None
    if pu is None or pu < 0:
        problemes.append({
            "code": "PRIX_INVALIDE",
            "cle_prix": cle,
            "message": f"Prix unitaire « {LIBELLES_PRIX.get(cle, cle)} » invalide : {brut!r}.",
        })
        return None
    return pu


def _nombre_json(valeur: Decimal):
    """int si entier, sinon float -- pour un JSON lisible."""
    return int(valeur) if valeur == valeur.to_integral_value() else float(valeur)


# Nature de la donnée « quantité », pour l'affichage (règle : calculé /
# saisi / estimé ne sont jamais confondus).
TYPE_DONNEE = {"calcul_moteur": "calculé", "ratio_reference": "estimé", "saisie": "saisi"}


def _ligne(*, element_id, repere, type_element, designation, categorie, unite,
           quantite: Decimal, pu: Decimal, source_quantite="calcul_moteur", hypothese=None,
           cle_prix=None, formule=None):
    quantite = _q(quantite)
    montant = (quantite * pu).quantize(Decimal("1"), rounding=ROUND_HALF_UP)
    ligne = {
        "element_id": element_id,
        "repere": repere,
        "type_element": type_element,
        "designation": designation,
        "categorie": categorie,
        "unite": unite,
        "quantite": float(quantite),
        "prix_unitaire": _nombre_json(pu),
        "montant": int(montant),
        "source_quantite": source_quantite,
        "type_donnee": TYPE_DONNEE.get(source_quantite, source_quantite),
        "cle_prix": cle_prix,
        "formule_quantite": formule,
    }
    if hypothese:
        ligne["hypothese"] = hypothese
    return ligne


def _cm_vers_m(valeur_cm) -> float:
    return float(valeur_cm) / 100.0


def _geometrie_element(element: ElementStructurel, res: dict):
    """
    (volume_beton_m3, coffrage_m2, poids_acier_kg ou None, champs_manquants)
    à partir du résultat VALIDÉ par l'ingénieur.

    Hypothèses géométriques (inchangées, documentées) :
    - poteau carré : béton = a² h, coffrage = 4 a h ;
    - poutre/longrine : coffrage = (b + 2h) L (face supérieure non coffrée) ;
    - semelle isolée carrée : coffrage latéral = 4 a h ;
    - dalle : coffrage = sous-face ;
    - semelle filante / chaînage : coffrage = 2 faces latérales.
    """
    t = element.type_element
    T = ElementStructurel.TypeElement
    manquants = []

    def requis(nom, valeur):
        if valeur is None or (isinstance(valeur, (int, float)) and valeur <= 0):
            manquants.append(nom)
        return valeur

    if t == T.POTEAU:
        a = requis("côté du poteau (cote_cm)", res.get("cote_cm"))
        h = requis("hauteur du poteau", element.hauteur_poteau)
        if manquants:
            return None, None, None, manquants
        a = _cm_vers_m(a)
        return a * a * h, 4 * a * h, res.get("poids_acier_total_kg"), []

    if t in (T.POUTRE, T.LONGRINE):
        b = requis("largeur (largeur_cm)", res.get("largeur_cm"))
        h = requis("hauteur (hauteur_cm)", res.get("hauteur_cm"))
        portee = requis("portée", element.portee)
        if manquants:
            return None, None, None, manquants
        b, h = _cm_vers_m(b), _cm_vers_m(h)
        return b * h * portee, (b + 2 * h) * portee, res.get("poids_acier_total_kg"), []

    if t == T.SEMELLE:
        a = requis("côté de la semelle (cote_cm)", res.get("cote_cm"))
        h = requis("hauteur de la semelle (hauteur_cm)", res.get("hauteur_cm"))
        if manquants:
            return None, None, None, manquants
        a, h = _cm_vers_m(a), _cm_vers_m(h)
        return a * a * h, 4 * a * h, res.get("poids_acier_total_kg"), []

    if t == T.DALLE:
        e = requis("épaisseur (epaisseur_cm)", res.get("epaisseur_cm"))
        surface = requis("surface de la dalle (surface_m2)", element.surface_m2)
        if manquants:
            return None, None, None, manquants
        return surface * _cm_vers_m(e), surface, None, []

    if t == T.SEMELLE_FILANTE:
        b = requis("largeur (largeur_cm)", res.get("largeur_cm"))
        h = requis("hauteur (hauteur_cm)", res.get("hauteur_cm"))
        longueur = requis("longueur (longueur_m)", element.longueur_m)
        if manquants:
            return None, None, None, manquants
        b, h = _cm_vers_m(b), _cm_vers_m(h)
        poids = None
        a_t = res.get("acier_transversal_cm2_ml")
        if a_t is not None:
            # Section totale par ml (cm²/ml -> m²) x longueur x densité.
            section_m2 = (a_t + (res.get("acier_repartition_cm2_ml") or 0)) / 10_000
            poids = section_m2 * longueur * DENSITE_ACIER_KG_M3
        return b * h * longueur, 2 * h * longueur, poids, []

    if t == T.CHAINAGE:
        b = requis("largeur (largeur_cm)", res.get("largeur_cm"))
        h = requis("hauteur (hauteur_cm)", res.get("hauteur_cm"))
        longueur = requis("longueur (longueur_m)", element.longueur_m)
        if manquants:
            return None, None, None, manquants
        b, h = _cm_vers_m(b), _cm_vers_m(h)
        volume = res.get("volume_beton_m3") or b * h * longueur
        return volume, 2 * h * longueur, res.get("poids_acier_total_kg"), []

    return None, None, None, [f"type d'élément non pris en charge par le DQE ({t})"]


TYPES_PLURIEL = {
    "poteau": "Poteaux", "poutre": "Poutres", "longrine": "Longrines", "semelle": "Semelles isolées",
    "semelle_filante": "Semelles filantes", "dalle": "Dalles", "chainage": "Chaînages",
}


def _f(v):
    return f"{float(v):g}".replace(".", ",")


def _formules_element(element: ElementStructurel, res: dict) -> dict:
    """Formules de métré lisibles (mêmes conventions que _geometrie_element)."""
    t = element.type_element
    T = ElementStructurel.TypeElement
    cm = lambda k: _f(_cm_vers_m(res[k]))  # noqa: E731
    try:
        if t == T.POTEAU:
            a, h = cm("cote_cm"), _f(element.hauteur_poteau)
            return {"beton": f"a² × h = {a}² × {h}", "coffrage": f"4 a h = 4 × {a} × {h}"}
        if t in (T.POUTRE, T.LONGRINE):
            b, h, l = cm("largeur_cm"), cm("hauteur_cm"), _f(element.portee)
            return {"beton": f"b × h × L = {b} × {h} × {l}", "coffrage": f"(b + 2h) × L = ({b} + 2 × {h}) × {l}"}
        if t == T.SEMELLE:
            a, h = cm("cote_cm"), cm("hauteur_cm")
            return {"beton": f"A² × h = {a}² × {h}", "coffrage": f"4 A h = 4 × {a} × {h}"}
        if t == T.DALLE:
            e, sf = cm("epaisseur_cm"), _f(element.surface_m2)
            return {"beton": f"S × e = {sf} × {e}", "coffrage": f"S = {sf} (sous-face)"}
        if t in (T.SEMELLE_FILANTE, T.CHAINAGE):
            b, h, l = cm("largeur_cm"), cm("hauteur_cm"), _f(element.longueur_m)
            return {"beton": f"b × h × L = {b} × {h} × {l}", "coffrage": f"2 h L = 2 × {h} × {l}"}
    except (KeyError, TypeError, ValueError):
        pass
    return {}


def largeurs_poutres_validees(projet) -> set:
    """Largeurs (cm) des POUTRES validées du projet -- sert à déduire leur
    emprise du béton des dalles (règle de métré validée)."""
    largeurs = set()
    for el in projet.elements.filter(statut=ElementStructurel.Statut.VALIDE,
                                     type_element=ElementStructurel.TypeElement.POUTRE):
        b = (el.resultat_valide or {}).get("largeur_cm")
        if b:
            largeurs.add(float(b))
    return largeurs


def deduction_poutres_dalle(element: ElementStructurel, res: dict, largeurs_poutres: set):
    """Béton de dalle net de l'emprise des poutres.

    RÈGLE DE MÉTRÉ VALIDÉE PAR LE TECHNICIEN BTP (07/10/2026) : poutres
    comptées sur toute leur hauteur, longueurs entre axes des poteaux ; la
    partie de la poutre sous la dalle est DÉDUITE du béton de la dalle.

    Géométrie : panneau Lx × Ly mesuré entre axes, bordé de poutres de
    largeur b centrées sur les axes -> la dalle coulée en place couvre
    (Lx − b) × (Ly − b) ; la bande b/2 de chaque côté appartient aux
    poutres (et les angles aux poteaux).

    Retour : (volume_m3 ou None si non applicable, formule, hypothese).
    Ne modifie que le BÉTON (le coffrage de sous-face reste S, non
    tranché par le technicien).
    """
    if not largeurs_poutres:
        return None, None, None
    e = _cm_vers_m(res["epaisseur_cm"])
    lx, ly, surface = element.portee, element.longueur_m, element.surface_m2
    if len(largeurs_poutres) > 1:
        return None, None, (
            "Dalles : emprise des poutres NON déduite (largeurs de poutres différentes dans le projet) -- "
            "volume de béton des dalles surestimé, à vérifier."
        )
    if not lx or not ly:
        return None, None, (
            "Dalles : emprise des poutres NON déduite (Lx ou Ly non renseignée) -- volume de béton surestimé."
        )
    if abs(surface - lx * ly) > 0.01 * lx * ly:
        return None, None, (
            "Dalles : emprise des poutres NON déduite (surface saisie différente de Lx × Ly) -- à vérifier."
        )
    b = _cm_vers_m(next(iter(largeurs_poutres)))
    if lx <= b or ly <= b:
        return None, None, "Dalles : portée inférieure à la largeur des poutres -- emprise non déduite."
    volume = (lx - b) * (ly - b) * e
    formule = f"(Lx − b) × (Ly − b) × e = ({_f(lx)} − {_f(b)}) × ({_f(ly)} − {_f(b)}) × {_f(e)}"
    hypothese = (
        f"Dalles : béton net de l'emprise des poutres (b = {_f(b)} m sur les 4 côtés, panneau mesuré entre axes) "
        f"-- règle de métré validée par le technicien BTP."
    )
    return volume, formule, hypothese


def calculer_element_dqe(element: ElementStructurel, prix_unitaires: dict, problemes: list | None = None,
                         largeurs_poutres: set | None = None) -> list:
    """Lignes béton / coffrage / acier d'un élément VALIDÉ.

    Avec `problemes` fourni : y ajoute (sans lever) toute donnée
    manquante, pour que calculer_projet_dqe() remonte la liste complète.
    Sans `problemes` (appel unitaire) : lève DQEIncomplet.
    """
    if problemes is None:
        locaux = []
        lignes = calculer_element_dqe(element, prix_unitaires, locaux, largeurs_poutres=largeurs_poutres)
        if locaux:
            raise DQEIncomplet(locaux)
        return lignes
    res = element.resultat_valide
    libelle = f"{element.get_type_element_display()} {element.identifiant}"
    if not res:
        problemes.append({
            "code": "RESULTAT_VALIDE_ABSENT",
            "element_id": element.id,
            "repere": element.identifiant,
            "message": f"{libelle} : aucun résultat validé.",
        })
        return []

    volume, coffrage, poids_moteur, manquants = _geometrie_element(element, res)
    if manquants:
        problemes.append({
            "code": "DIMENSION_MANQUANTE",
            "element_id": element.id,
            "repere": element.identifiant,
            "message": f"{libelle} : donnée manquante ou nulle -- {', '.join(manquants)}.",
        })
        return []

    # Ouvrages identiques (ex. même poteau à chaque niveau) : quantité × n.
    n = element.nombre_identiques or 1
    fois = f" × {n} (niveaux identiques)" if n > 1 else ""
    formules = _formules_element(element, res)
    hyp_beton = None
    if element.type_element == ElementStructurel.TypeElement.DALLE and largeurs_poutres:
        volume_net, formule_nette, hyp_beton = deduction_poutres_dalle(element, res, largeurs_poutres)
        if volume_net is not None:
            volume = volume_net
            formules = {**formules, "beton": formule_nette}
    volume, coffrage = _dec(volume) * n, _dec(coffrage) * n
    if poids_moteur is not None and poids_moteur > 0:
        poids = _dec(poids_moteur) * n
        source_acier, hyp_acier = "calcul_moteur", None
    else:
        ratio = RATIOS_ACIER_KG_M3[element.type_element]
        poids = volume * ratio  # volume déjà multiplié par n
        source_acier = "ratio_reference"
        hyp_acier = (
            f"{TYPES_PLURIEL.get(element.type_element, element.type_element)} : acier estimé à "
            f"{_nombre_json(ratio)} kg par m³ de béton (milieu de la fourchette de référence), "
            f"le ferraillage détaillé n'étant pas calculé pour ces éléments."
        )

    pu_beton = _prix(prix_unitaires, "beton_m3", problemes, libelle)
    pu_coffrage = _prix(prix_unitaires, "coffrage_m2", problemes, libelle)
    pu_acier = _prix(prix_unitaires, "acier_kg", problemes, libelle)
    if None in (pu_beton, pu_coffrage, pu_acier):
        return []

    commun = {
        "element_id": element.id,
        "repere": element.identifiant,
        "type_element": element.type_element.upper(),
    }
    return [
        _ligne(**commun, designation=f"Béton armé — {libelle}", categorie="BETON",
               unite="m³", quantite=volume, pu=pu_beton, cle_prix="beton_m3", hypothese=hyp_beton,
               formule=(formules.get("beton") or "") + fois or None),
        _ligne(**commun, designation=f"Coffrage — {libelle}", categorie="COFFRAGE",
               unite="m²", quantite=coffrage, pu=pu_coffrage, cle_prix="coffrage_m2",
               formule=(formules.get("coffrage") or "") + fois or None),
        _ligne(**commun, designation=f"Armatures acier — {libelle}", categorie="ACIER",
               unite="kg", quantite=poids, pu=pu_acier, cle_prix="acier_kg",
               source_quantite=source_acier, hypothese=hyp_acier,
               formule=(f"béton × {_nombre_json(RATIOS_ACIER_KG_M3[element.type_element])} kg/m³"
                        if source_acier == "ratio_reference" else "poids des barres calculé par le moteur") + fois),
    ]


def _cle_prix_unitaire(designation: str) -> str:
    """Associe une ligne de postes_ratio à sa clé de barème."""
    d = designation.lower()
    if "agglos 15 pleins" in d:
        return "agglos_15_pleins_m2"
    if "agglos 15 creux" in d:
        return "agglos_15_creux_m2"
    if "agglos 10 creux" in d:
        return "agglos_10_creux_m2"
    if "enduit" in d:
        return "enduit_m2"
    if "béton" in d:
        return "beton_m3"
    if "acier" in d:
        return "acier_kg"
    if "coffrage" in d:
        return "coffrage_m2"
    raise ValueError(f"Pas de clé de prix unitaire connue pour la ligne : {designation!r}")


def _categorie_depuis_designation(designation: str) -> str:
    # Les agglos sont de la MAÇONNERIE, pas du béton : avant, ils étaient
    # classés "BETON" et gonflaient le volume de béton du projet.
    d = designation.lower()
    if "agglos" in d:
        return "MACONNERIE"
    if "béton" in d:
        return "BETON"
    if "acier" in d:
        return "ACIER"
    if "coffrage" in d:
        return "COFFRAGE"
    if "enduit" in d:
        return "ENDUIT"
    return "AUTRE"


def calculer_poste_ratio_dqe(poste: PosteComplementaire, prix_unitaires: dict, problemes: list) -> list:
    """Lignes d'un poste complémentaire en mode RATIO, recalculées à
    partir de SA géométrie (jamais de lignes_calculees périmées)."""
    libelle = f"Poste « {poste.get_type_poste_display() or poste.type_poste} » (#{poste.id})"
    if not poste.type_poste or not poste.geometrie:
        problemes.append({
            "code": "POSTE_RATIO_INCOMPLET",
            "poste_id": poste.id,
            "message": f"{libelle} : type de poste ou géométrie non renseigné.",
        })
        return []
    try:
        lignes_brutes = calculer_poste_ratio(poste.type_poste, poste.geometrie)
    except KeyError as exc:
        problemes.append({
            "code": "GEOMETRIE_INCOMPLETE",
            "poste_id": poste.id,
            "message": f"{libelle} : donnée géométrique manquante -- {exc.args[0]}.",
        })
        return []
    except (ValueError, TypeError) as exc:
        problemes.append({
            "code": "GEOMETRIE_INVALIDE",
            "poste_id": poste.id,
            "message": f"{libelle} : {exc}",
        })
        return []

    lignes_brutes = [l for l in lignes_brutes if l["quantite"] and l["quantite"] > 0]
    if not lignes_brutes:
        problemes.append({
            "code": "POSTE_RATIO_VIDE",
            "poste_id": poste.id,
            "message": f"{libelle} : aucune quantité calculable avec la géométrie fournie.",
        })
        return []

    lignes = []
    for brute in lignes_brutes:
        cle = _cle_prix_unitaire(brute["designation"])
        pu = _prix(prix_unitaires, cle, problemes, libelle)
        if pu is None:
            continue
        lignes.append(_ligne(
            element_id=None,
            repere=poste.type_poste.upper(),
            type_element="RATIO_" + poste.type_poste.upper(),
            designation=brute["designation"],
            categorie=_categorie_depuis_designation(brute["designation"]),
            unite=brute["unite"],
            quantite=_dec(brute["quantite"]),
            pu=pu,
            source_quantite="ratio_reference",
            hypothese=brute.get("hypothese"),
            cle_prix=cle,
            formule=brute.get("formule") or "ratio de métré (voir hypothèse)",
        ) | {"poste_id": poste.id})
    return lignes


def calculer_poste_simple_dqe(poste: PosteComplementaire, problemes: list) -> list:
    """Ligne d'un poste saisi manuellement (quantité et prix fournis par l'utilisateur)."""
    manquants = []
    if not (poste.designation or "").strip():
        manquants.append("désignation")
    if not (poste.unite or "").strip():
        manquants.append("unité")
    if poste.quantite is None or poste.quantite <= 0:
        manquants.append("quantité (> 0)")
    if poste.prix_unitaire is None or poste.prix_unitaire < 0:
        manquants.append("prix unitaire (≥ 0)")
    if manquants:
        problemes.append({
            "code": "POSTE_INCOMPLET",
            "poste_id": poste.id,
            "message": f"Poste « {poste.designation or f'#{poste.id}'} » : {', '.join(manquants)} manquant(s).",
        })
        return []
    return [_ligne(
        element_id=None,
        repere="MO",
        type_element="MAIN_DOEUVRE",
        designation=poste.designation,
        categorie="MAIN_DOEUVRE",
        unite=poste.unite,
        quantite=_dec(poste.quantite),
        pu=_dec(poste.prix_unitaire),
        source_quantite="saisie",
        formule="quantité saisie",
    ) | {"poste_id": poste.id, "prix_source": "saisie (poste)", "prix_date": None}]


# --- Montant en toutes lettres (Jour 4) ----------------------------------
#
# Convention d'écriture financière (utilisée par CIMBAT sur le DQE de
# référence : "...soixante et un mille sept cent", pas "sept cents") :
# "cent" et "vingt" ne prennent JAMAIS la marque du pluriel dans un
# montant écrit en toutes lettres, contrairement à la règle grammaticale
# standard -- convention usuelle sur les chèques et devis pour éviter
# toute altération frauduleuse du montant.

_UNITES = ["", "un", "deux", "trois", "quatre", "cinq", "six", "sept", "huit", "neuf"]
_DIX_DIX_NEUF = [
    "dix", "onze", "douze", "treize", "quatorze", "quinze", "seize",
    "dix-sept", "dix-huit", "dix-neuf",
]
_DIZAINES = {20: "vingt", 30: "trente", 40: "quarante", 50: "cinquante", 60: "soixante"}


def _deux_chiffres_en_lettres(n: int) -> str:
    if n < 10:
        return _UNITES[n]
    if n < 20:
        return _DIX_DIX_NEUF[n - 10]
    if n < 70:
        dizaine, unite = divmod(n, 10)
        mot = _DIZAINES[dizaine * 10]
        if unite == 0:
            return mot
        if unite == 1:
            return f"{mot} et un"
        return f"{mot}-{_UNITES[unite]}"
    if n < 80:
        # 70-79 : soixante + 10..19 (soixante-dix, soixante et onze, soixante-douze...)
        reste = n - 60
        if reste == 11:
            return "soixante et onze"
        return f"soixante-{_DIX_DIX_NEUF[reste - 10]}"
    # 80-99 : quatre-vingt + 0..19 (pas de "s", convention financière)
    reste = n - 80
    if reste == 0:
        return "quatre-vingt"
    if reste < 10:
        return f"quatre-vingt-{_UNITES[reste]}"
    return f"quatre-vingt-{_DIX_DIX_NEUF[reste - 10]}"


def _trois_chiffres_en_lettres(n: int) -> str:
    centaines, reste = divmod(n, 100)
    mots = []
    if centaines > 0:
        prefixe = "cent" if centaines == 1 else f"{_UNITES[centaines]} cent"
        mots.append(prefixe)  # jamais de "s" (convention financière)
    if reste > 0:
        mots.append(_deux_chiffres_en_lettres(reste))
    return " ".join(mots) if mots else "zéro"


def nombre_en_lettres(n: int) -> str:
    """Convertit un entier positif en toutes lettres (français, convention financière)."""
    if n == 0:
        return "zéro"
    if n < 0:
        return "moins " + nombre_en_lettres(-n)

    milliards, reste = divmod(n, 10**9)
    millions, reste = divmod(reste, 10**6)
    milliers, unites = divmod(reste, 1000)

    parts = []
    if milliards:
        mot = _trois_chiffres_en_lettres(milliards)
        parts.append(f"{mot} milliard" + ("s" if milliards > 1 else ""))
    if millions:
        mot = _trois_chiffres_en_lettres(millions)
        parts.append(f"{mot} million" + ("s" if millions > 1 else ""))
    if milliers:
        parts.append("mille" if milliers == 1 else f"{_trois_chiffres_en_lettres(milliers)} mille")
    if unites:
        parts.append(_trois_chiffres_en_lettres(unites))
    return " ".join(parts)


def montant_en_toutes_lettres(montant_fcfa) -> str:
    """Ex. 45 961 700 -> 'quarante-cinq millions neuf cent soixante et un mille sept cent'."""
    return nombre_en_lettres(int(montant_fcfa))


def _fusionner_prix_manquants(problemes: list) -> list:
    """Un prix manquant n'est signalé qu'UNE fois (avec le nombre d'ouvrages
    concernés), au lieu d'une ligne par élément : la liste reste exhaustive
    mais lisible. Les autres problèmes sont conservés tels quels, en tête."""
    autres, prix = [], {}
    for p in problemes:
        if p["code"] in ("PRIX_MANQUANT", "PRIX_INVALIDE"):
            cle = (p["code"], p["cle_prix"])
            if cle not in prix:
                prix[cle] = dict(p, nb_ouvrages=0)
            prix[cle]["nb_ouvrages"] += 1
        else:
            autres.append(p)
    for p in prix.values():
        libelle = LIBELLES_PRIX.get(p["cle_prix"], p["cle_prix"])
        etat = "non renseigné" if p["code"] == "PRIX_MANQUANT" else "invalide"
        p["message"] = (
            f"Prix unitaire « {libelle} » {etat} dans le barème du cabinet "
            f"(nécessaire pour {p['nb_ouvrages']} ouvrage(s))."
        )
    return autres + list(prix.values())


def _synthese_quantites(lignes: list) -> dict:
    """Quantités physiques agrégées (béton structurel, acier) et ratio
    acier/béton, calculés UNIQUEMENT à partir des lignes du DQE."""
    beton = sum((_dec(l["quantite"]) for l in lignes
                 if l["categorie"] == "BETON" and l["unite"] == "m³"), Decimal("0"))
    acier = sum((_dec(l["quantite"]) for l in lignes
                 if l["categorie"] == "ACIER" and l["unite"] == "kg"), Decimal("0"))
    acier_estime = sum((_dec(l["quantite"]) for l in lignes
                        if l["categorie"] == "ACIER" and l["source_quantite"] == "ratio_reference"),
                       Decimal("0"))
    ratio = (acier / beton).quantize(Decimal("0.1"), rounding=ROUND_HALF_UP) if beton > 0 else None
    return {
        "beton_m3": float(_q(beton)),
        "acier_kg": float(_q(acier)),
        "acier_estime_par_ratio_kg": float(_q(acier_estime)),
        "ratio_acier_kg_m3": float(ratio) if ratio is not None else None,
    }


def calculer_projet_dqe(projet: Projet, prix_unitaires: dict) -> dict:
    """
    DQE complet d'un projet, regroupé par LOT façon CIMBAT :
      1. éléments structurels VALIDÉS (Infrastructure / Superstructure
         selon `position`) ;
      2. postes complémentaires en mode RATIO (maçonnerie, enduit,
         chaînage, raidisseur, acrotère), recalculés depuis leur géométrie ;
      3. postes complémentaires saisis (mode SIMPLE), chacun dans son lot.

    Lève DQEIncomplet (liste exhaustive) si une donnée indispensable
    manque -- jamais de ligne à 0, jamais de prix ni de quantité inventés.
    `prix_unitaires` : barème du cabinet (obligatoire, éventuellement vide).
    """
    if prix_unitaires is None:
        raise DQEIncomplet([{
            "code": "CABINET_ABSENT",
            "message": "Ce projet n'est rattaché à aucun cabinet : aucun barème de prix disponible.",
        }])

    LOT_INFRA = PosteComplementaire.Lot.GROS_OEUVRE_INFRA.value
    LOT_SUPER = PosteComplementaire.Lot.GROS_OEUVRE_SUPER.value

    problemes = []
    toutes_lignes = []

    elements_valides = projet.elements.filter(statut=ElementStructurel.Statut.VALIDE).order_by("id")
    largeurs_poutres = largeurs_poutres_validees(projet)
    for element in elements_valides:
        lot = LOT_INFRA if element.position == ElementStructurel.Position.INFRASTRUCTURE else LOT_SUPER
        for ligne in calculer_element_dqe(element, prix_unitaires, problemes, largeurs_poutres=largeurs_poutres):
            ligne["lot"] = lot
            toutes_lignes.append(ligne)

    for poste in projet.postes_complementaires.all().order_by("id"):
        if poste.mode == PosteComplementaire.Mode.RATIO:
            lignes = calculer_poste_ratio_dqe(poste, prix_unitaires, problemes)
        else:
            lignes = calculer_poste_simple_dqe(poste, problemes)
        for ligne in lignes:
            ligne["lot"] = poste.lot
            toutes_lignes.append(ligne)

    if problemes:
        raise DQEIncomplet(_fusionner_prix_manquants(problemes))

    meta_prix = (getattr(projet.entreprise, "prix_unitaires_meta", None) or {}) if projet.entreprise_id else {}
    for ligne in toutes_lignes:
        if ligne.get("cle_prix"):
            m = meta_prix.get(ligne["cle_prix"]) or {}
            ligne["prix_source"] = {"reference": "barème de référence (pré-rempli)", "saisie": "barème du cabinet"}.get(
                m.get("source"), "barème du cabinet (date non tracée)")
            ligne["prix_date"] = m.get("date")

    sous_totaux_categorie = defaultdict(int)
    lots = defaultdict(lambda: {"lignes": [], "sous_total": 0, "sous_lots": {}})
    for ligne in toutes_lignes:
        lot = lots[ligne["lot"]]
        lot["lignes"].append(ligne)
        lot["sous_total"] += ligne["montant"]
        sl = lot["sous_lots"].setdefault(_sous_lot(ligne), {"libelle": _sous_lot(ligne), "lignes": [], "sous_total": 0})
        sl["lignes"].append(ligne)
        sl["sous_total"] += ligne["montant"]
        sous_totaux_categorie[ligne["categorie"].lower()] += ligne["montant"]

    total_general = sum(l["sous_total"] for l in lots.values())

    ordre_lots = [choix.value for choix in PosteComplementaire.Lot]
    lots_ordonnes = sorted(
        lots.keys(), key=lambda lot: ordre_lots.index(lot) if lot in ordre_lots else len(ordre_lots)
    )
    libelles_lots = dict(PosteComplementaire.Lot.choices)

    hypotheses = sorted({l["hypothese"] for l in toutes_lignes if l.get("hypothese")})

    return {
        "projet": {
            "id": projet.id,
            "nom": projet.nom,
            "description": projet.description,
            "usage_batiment": projet.usage_batiment,
            "nb_niveaux": projet.nb_niveaux,
            "numero_devis": projet.numero_devis,
        },
        "lignes": toutes_lignes,
        "lots": [
            {
                "lot": lot,
                "libelle": libelles_lots.get(lot, lot),
                "lignes": lots[lot]["lignes"],
                "sous_lots": list(lots[lot]["sous_lots"].values()),
                "sous_total": lots[lot]["sous_total"],
            }
            for lot in lots_ordonnes
        ],
        "sous_totaux": dict(sous_totaux_categorie),
        "synthese": _synthese_quantites(toutes_lignes),
        "hypotheses": hypotheses,
        "total_general": total_general,
        "montant_lettres": montant_en_toutes_lettres(total_general),
        "devise": "FCFA",
        "finances": _finances(projet.entreprise, total_general),
        # Hypothèses de CALCUL du projet (G, Q, sol, méthode des semelles...)
        # -- distinctes des hypothèses de MÉTRÉ ci-dessus.
        "hypotheses_projet": _hypotheses_projet(projet),
    }


def _hypotheses_projet(projet):
    from .parametres_projet import messages_hypotheses

    return messages_hypotheses(projet)["hypotheses"]


SOUS_LOTS = {
    "SEMELLE": "Fondations isolées", "SEMELLE_FILANTE": "Fondations filantes", "LONGRINE": "Longrines",
    "POTEAU": "Poteaux", "POUTRE": "Poutres", "DALLE": "Dalles et planchers", "CHAINAGE": "Chaînages",
    "MAIN_DOEUVRE": "Postes saisis",
}


def _sous_lot(ligne):
    t = ligne["type_element"]
    if t.startswith("RATIO_"):
        return "Ouvrages au ratio — " + t[6:].replace("_", " ").lower()
    return SOUS_LOTS.get(t, t.replace("_", " ").capitalize())


def _arrondi_fcfa(v: Decimal) -> int:
    return int(v.quantize(Decimal("1"), rounding=ROUND_HALF_UP))


def _finances(entreprise, total_lignes: int) -> dict:
    """HT / marge / TVA / TTC à partir des seuls paramètres DU CABINET.
    Un taux non renseigné n'est jamais supposé : le montant correspondant
    reste null et un message l'explique."""
    nature = getattr(entreprise, "nature_prix", "vente_ht") or "vente_ht"
    marge_pct = getattr(entreprise, "taux_marge_pct", None)
    tva_pct = getattr(entreprise, "taux_tva_pct", None)
    messages = []
    res = {"nature_prix": nature, "total_lignes": total_lignes, "debourse_sec": None,
           "taux_marge_pct": float(marge_pct) if marge_pct is not None else None, "montant_marge": None,
           "total_ht": None, "taux_tva_pct": float(tva_pct) if tva_pct is not None else None,
           "montant_tva": None, "total_ttc": None, "messages": messages}
    if nature == "debourse_sec":
        res["debourse_sec"] = total_lignes
        if marge_pct is None:
            messages.append("Prix du barème = déboursé sec, mais taux de marge non renseigné : "
                            "prix de vente HT non calculé.")
        else:
            res["montant_marge"] = _arrondi_fcfa(Decimal(total_lignes) * Decimal(marge_pct) / 100)
            res["total_ht"] = total_lignes + res["montant_marge"]
    else:
        res["total_ht"] = total_lignes
    if res["total_ht"] is not None:
        if tva_pct is None:
            messages.append("Taux de TVA non renseigné dans les paramètres du cabinet : TTC non calculé.")
        else:
            res["montant_tva"] = _arrondi_fcfa(Decimal(res["total_ht"]) * Decimal(tva_pct) / 100)
            res["total_ttc"] = res["total_ht"] + res["montant_tva"]
    return res
