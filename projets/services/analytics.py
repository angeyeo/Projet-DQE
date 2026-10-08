"""
Analytics -- règles d'honnêteté :

1. Deux sources seulement, jamais mélangées sans le dire :
   - l'ÉTAT ACTUEL de la base (nombre de projets, éléments validés,
     anomalies de cohérence...) -- exact à l'instant de la requête ;
   - le JOURNAL EvenementProduit pour tout ce qui est HISTORIQUE (activité
     mensuelle, montants de DQE générés, adoption, funnel). Aucune
     reconstitution par estimation à partir des dates de création.
2. Chaque réponse expose `date_debut_fiabilite` : la date du premier
   événement journalisé. Avant cette date, l'historique est inconnu (et
   affiché comme tel), pas "nul".
3. Les montants viennent de l'instantané enregistré au moment où le DQE a
   été réellement généré ; un instantané antérieur à la dernière
   modification du projet est signalé "à régénérer".
"""

from collections import Counter, defaultdict
from datetime import timedelta

from django.db.models import Count, Max, Q
from django.db.models.functions import TruncMonth
from django.utils import timezone

from moteur_calcul.constantes import (
    RATIO_ACIER_DALLES_KG_M3,
    RATIO_ACIER_POTEAUX_KG_M3,
    RATIO_ACIER_POUTRES_KG_M3,
    RATIO_ACIER_SEMELLES_KG_M3,
)

from ..models import ElementStructurel, EvenementProduit, PosteComplementaire, Projet
from .assistant_ia import analyser_projet_coherence
from .dqe_calculator import LIBELLES_PRIX, DQEIncomplet, calculer_projet_dqe
from .parametres_projet import statut_projet

T = EvenementProduit.Type
NB_MOIS = 12

# Fourchettes de référence (kg d'acier par m³ de béton) -- constantes.py.
FOURCHETTES_ACIER = {
    "POTEAU": RATIO_ACIER_POTEAUX_KG_M3,
    "POUTRE": RATIO_ACIER_POUTRES_KG_M3,
    "LONGRINE": RATIO_ACIER_POUTRES_KG_M3,
    "SEMELLE": RATIO_ACIER_SEMELLES_KG_M3,
    "SEMELLE_FILANTE": RATIO_ACIER_SEMELLES_KG_M3,
    "DALLE": RATIO_ACIER_DALLES_KG_M3,
}

# Regroupement des catégories du DQE. Les prix du barème sont des prix
# "fourni-posé" : la part main-d'œuvre des ouvrages béton/acier/coffrage
# n'est PAS séparable. "Postes saisis" = postes complémentaires du lot
# choisi par l'utilisateur (historiquement nommés "main d'œuvre").
GROUPES_COUT = {
    "ouvrages": {"beton", "acier", "coffrage", "maconnerie", "enduit"},
    "postes_saisis": {"main_doeuvre"},
    "autres": {"autre"},
}
NOTE_VENTILATION = (
    "Les prix unitaires du barème sont « fourni-posé » : la part main-d'œuvre des ouvrages "
    "(béton, acier, coffrage, maçonnerie, enduit) n'est pas isolable. « Postes saisis » regroupe "
    "les postes complémentaires chiffrés manuellement."
)


def date_debut_fiabilite():
    premier = EvenementProduit.objects.order_by("date").values_list("date", flat=True).first()
    return premier


def _mois_glissants(nb=NB_MOIS):
    """Liste des 1ers jours de mois (aware), du plus ancien au courant."""
    maintenant = timezone.localtime()
    annee, mois = maintenant.year, maintenant.month
    res = []
    for _ in range(nb):
        res.append((annee, mois))
        mois -= 1
        if mois == 0:
            annee, mois = annee - 1, 12
    res.reverse()
    return res


def _serie_mensuelle(qs, debut_fiabilite):
    """{(annee, mois): n} complété à 0 -- sauf les mois ANTÉRIEURS à la mise
    en service du journal, renvoyés à None (inconnu, pas zéro)."""
    comptes = {
        (d["mois"].year, d["mois"].month): d["n"]
        for d in qs.annotate(mois=TruncMonth("date")).values("mois").annotate(n=Count("id"))
    }
    serie = []
    for annee, mois in _mois_glissants():
        connu = debut_fiabilite is not None and (annee, mois) >= (debut_fiabilite.year, debut_fiabilite.month)
        serie.append({
            "mois": f"{annee:04d}-{mois:02d}",
            "valeur": comptes.get((annee, mois), 0) if connu else None,
        })
    return serie


def _derniers_dqe(evenements_qs):
    """Dernier instantané dqe_genere par projet : {projet_id: evenement}."""
    derniers = {}
    for ev in evenements_qs.filter(type=T.DQE_GENERE, projet__isnull=False).order_by("projet_id", "-date"):
        derniers.setdefault(ev.projet_id, ev)
    return derniers


def _derniere_modification_contenu(projet_ids):
    """Date de la dernière modification d'un élément ou poste, par projet."""
    res = defaultdict(lambda: None)
    for modele in (ElementStructurel, PosteComplementaire):
        for row in modele.objects.filter(projet_id__in=projet_ids).values("projet_id").annotate(m=Max("date_modification")):
            if res[row["projet_id"]] is None or row["m"] > res[row["projet_id"]]:
                res[row["projet_id"]] = row["m"]
    return res


def _evenement_public(ev):
    u = ev.utilisateur
    return {
        "type": ev.type,
        "libelle": ev.get_type_display(),
        "date": ev.date,
        "utilisateur": (u.get_full_name() or u.username) if u else None,
        "projet_id": ev.projet_id,
        "projet_nom": ev.projet.nom if ev.projet_id else None,
        "donnees": {k: v for k, v in ev.donnees.items() if k in ("total_general", "format", "source", "succes", "nb_elements")},
    }


def _regrouper(evenements, limite):
    """Fusionne les événements CONSÉCUTIFS identiques (même type, projet et
    auteur) : « 31 éléments validés » plutôt que 31 lignes. Le nombre est
    le compte réel des événements fusionnés."""
    groupes = []
    for ev in evenements:
        pub = _evenement_public(ev)
        dernier = groupes[-1] if groupes else None
        if dernier and (dernier["type"], dernier["projet_id"], dernier["utilisateur"]) == (
                pub["type"], pub["projet_id"], pub["utilisateur"]):
            dernier["nombre"] += 1
            continue
        if len(groupes) == limite:
            break
        pub["nombre"] = 1
        groupes.append(pub)
    return groupes


# ---------------------------------------------------------------------------
# Cabinet
# ---------------------------------------------------------------------------

def analytics_cabinet(entreprise) -> dict:
    debut = date_debut_fiabilite()
    projets = list(
        Projet.objects.filter(entreprise=entreprise).annotate(
            nb_el=Count("elements", distinct=True),
            nb_val=Count("elements", filter=Q(elements__statut=ElementStructurel.Statut.VALIDE), distinct=True),
        )
    )
    ids = [p.id for p in projets]
    evs = EvenementProduit.objects.filter(entreprise=entreprise)
    derniers = _derniers_dqe(evs)
    modifs = _derniere_modification_contenu(ids)

    par_statut = Counter()
    a_traiter = []
    valeur_totale = 0
    lots = Counter()
    categories = Counter()
    projets_chiffres = 0
    elements_valides = elements_en_attente = 0
    anomalies = {"critiques": 0, "attentions": 0, "calculs_a_refaire": 0, "projets_concernes": []}

    for p in projets:
        dqe = derniers.get(p.id)
        statut = statut_projet(p.nb_el, p.nb_val, dqe is not None)
        par_statut[statut] += 1
        elements_valides += p.nb_val
        elements_en_attente += p.nb_el - p.nb_val

        perime = bool(dqe and modifs[p.id] and modifs[p.id] > dqe.date)
        if dqe:
            projets_chiffres += 1
            valeur_totale += dqe.donnees.get("total_general", 0)
            lots.update(dqe.donnees.get("lots", {}))
            categories.update(dqe.donnees.get("sous_totaux", {}))

        if p.nb_el:
            resume = analyser_projet_coherence(p)["resume"]
            if resume["critiques"] or resume["attentions"] or resume["calculs_a_refaire"]:
                anomalies["critiques"] += resume["critiques"]
                anomalies["attentions"] += resume["attentions"]
                anomalies["calculs_a_refaire"] += resume["calculs_a_refaire"]
                anomalies["projets_concernes"].append({
                    "projet_id": p.id, "nom": p.nom, "critiques": resume["critiques"],
                    "attentions": resume["attentions"], "calculs_a_refaire": resume["calculs_a_refaire"],
                })

        raisons = []
        if statut == "brouillon":
            raisons.append("Aucun élément structurel : générez la trame ou importez un plan.")
        elif statut == "en_etude":
            raisons.append(f"{p.nb_el - p.nb_val} élément(s) en attente de validation ingénieur.")
        elif statut == "valide":
            raisons.append("Tous les éléments sont validés : le DQE peut être généré.")
        if perime:
            raisons.append("Le projet a été modifié depuis le dernier DQE : à régénérer.")
        if raisons:
            a_traiter.append({
                "projet_id": p.id, "nom": p.nom, "statut": statut, "raisons": raisons,
                "date_modification": p.date_modification,
            })

    a_traiter.sort(key=lambda x: x["date_modification"], reverse=True)
    bareme = entreprise.prix_unitaires or {}
    prix_manquants = [{"cle": c, "libelle": l} for c, l in LIBELLES_PRIX.items() if bareme.get(c) in (None, "")]

    return {
        "date_debut_fiabilite": debut,
        "projets": {
            "total": len(projets),
            "par_statut": {s: par_statut.get(s, 0) for s in ("brouillon", "en_etude", "valide", "dqe_genere")},
            "actifs": par_statut.get("brouillon", 0) + par_statut.get("en_etude", 0) + par_statut.get("valide", 0),
            "termines": par_statut.get("dqe_genere", 0),
        },
        "dqe": {
            "valeur_totale": valeur_totale,
            "projets_chiffres": projets_chiffres,
            "repartition_par_lot": dict(lots),
            "repartition_par_categorie": dict(categories),
            "source": "Dernier DQE réellement généré de chaque projet (journal d'événements).",
        },
        "elements": {"valides": elements_valides, "en_attente": elements_en_attente},
        "anomalies": anomalies,
        "projets_a_traiter": a_traiter[:10],
        "bareme": {"prix_manquants": prix_manquants},
        "activite_mensuelle": {
            "projets_crees": _serie_mensuelle(evs.filter(type=T.PROJET_CREE), debut),
            "elements_valides": _serie_mensuelle(evs.filter(type=T.ELEMENT_VALIDE), debut),
            "dqe_generes": _serie_mensuelle(evs.filter(type=T.DQE_GENERE), debut),
        },
        "activite_recente": _regrouper(evs.select_related("utilisateur", "projet")[:300], 12),
    }


# ---------------------------------------------------------------------------
# Projet
# ---------------------------------------------------------------------------

def _ratios_par_type(lignes):
    """Ratio acier/béton par type d'élément, comparé aux fourchettes."""
    beton, acier, estime = Counter(), Counter(), defaultdict(bool)
    for l in lignes:
        t = l["type_element"]
        if t not in FOURCHETTES_ACIER:
            continue
        if l["categorie"] == "BETON":
            beton[t] += l["quantite"]
        elif l["categorie"] == "ACIER":
            acier[t] += l["quantite"]
            estime[t] = estime[t] or l["source_quantite"] == "ratio_reference"
    res = []
    for t, v in beton.items():
        if v <= 0:
            continue
        ratio = round(acier[t] / v, 1)
        mini, maxi = FOURCHETTES_ACIER[t]
        res.append({
            "type_element": t,
            "beton_m3": round(v, 3),
            "acier_kg": round(acier[t], 3),
            "ratio_kg_m3": ratio,
            "fourchette": [mini, maxi],
            "dans_fourchette": mini <= ratio <= maxi,
            # Acier estimé AU ratio de référence : le ratio obtenu est par
            # construction le milieu de la fourchette -- la comparaison ne
            # prouve rien et l'interface doit le dire.
            "acier_estime": estime[t],
        })
    return sorted(res, key=lambda r: r["type_element"])


def analytics_projet(projet) -> dict:
    debut = date_debut_fiabilite()
    elements = list(projet.elements.all().order_by("identifiant"))
    nb = len(elements)
    non_valides = [e for e in elements if e.statut != ElementStructurel.Statut.VALIDE]
    evs = EvenementProduit.objects.filter(projet=projet).select_related("utilisateur", "projet")
    dernier_dqe = evs.filter(type=T.DQE_GENERE).first()
    modifs = _derniere_modification_contenu([projet.id])[projet.id]

    # Coût : calcul EN DIRECT sur les éléments validés (même moteur que le
    # DQE). S'il manque des données, on renvoie la liste des problèmes --
    # jamais un coût partiel présenté comme complet.
    cout, problemes = None, []
    try:
        dqe = calculer_projet_dqe(projet, prix_unitaires=projet.entreprise.get_prix_unitaires())
    except DQEIncomplet as exc:
        problemes = exc.problemes
    else:
        if dqe["lignes"]:
            groupes = {g: sum(v for c, v in dqe["sous_totaux"].items() if c in cats)
                       for g, cats in GROUPES_COUT.items()}
            libelles = dict(PosteComplementaire.Lot.choices)
            cout = {
                "total": dqe["total_general"],
                "partiel": bool(non_valides),
                "elements_exclus": len(non_valides),
                "par_groupe": groupes,
                "note_ventilation": NOTE_VENTILATION,
                "par_lot": [{"lot": l["lot"], "libelle": libelles.get(l["lot"], l["lot"]), "montant": l["sous_total"]}
                            for l in dqe["lots"]],
                "par_categorie": dqe["sous_totaux"],
                "synthese": dqe["synthese"],
                "ratios_acier": _ratios_par_type(dqe["lignes"]),
                "hypotheses": dqe["hypotheses"],
            }

    coherence = analyser_projet_coherence(projet) if nb else None
    # Alertes regroupées par SIGNAL réel (code + message du contrôle), avec
    # la liste des éléments concernés -- plutôt qu'une ligne par élément.
    groupes = {}
    if coherence:
        for el in coherence["elements"]:
            if el["statut_analyse"] == "CALCUL_A_REFAIRE":
                g = groupes.setdefault(("CALCUL_A_REFAIRE", "CALCUL_A_REFAIRE"), {
                    "niveau": "CALCUL_A_REFAIRE", "code": "CALCUL_A_REFAIRE",
                    "message": "Élément modifié après validation : à recalculer et revalider.", "elements": []})
                g["elements"].append(el["identifiant"])
            for sig in el["signaux"]:
                if sig["categorie"] not in ("CRITIQUE", "ATTENTION"):
                    continue
                g = groupes.setdefault((sig["categorie"], sig["code"]), {
                    "niveau": sig["categorie"], "code": sig["code"], "message": sig["message_local"], "elements": []})
                g["elements"].append(el["identifiant"])
    from moteur_calcul.plausibilite import controler_projet

    for a in controler_projet(projet):
        g = groupes.setdefault(("ALERTE", a["code"]), {
            "niveau": "ALERTE", "code": a["code"], "message": a["message"], "elements": []})
        if a.get("element"):
            g["elements"].append(a["element"])
            g["message"] = a.get("message_groupe", a["message"])
    ordre = {"CRITIQUE": 0, "CALCUL_A_REFAIRE": 1, "ALERTE": 2, "ATTENTION": 3}
    alertes = sorted(groupes.values(), key=lambda g: ordre.get(g["niveau"], 9))
    if dernier_dqe and modifs and modifs > dernier_dqe.date:
        alertes.append({"niveau": "INFORMATION", "message": "Le projet a été modifié depuis le dernier DQE généré."})

    return {
        "date_debut_fiabilite": debut,
        "projet": {"id": projet.id, "nom": projet.nom, "usage_batiment": projet.usage_batiment,
                   "nb_niveaux": projet.nb_niveaux, "date_modification": projet.date_modification},
        "statut": statut_projet(nb, nb - len(non_valides), dernier_dqe is not None),
        "progression": {"elements": nb, "valides": nb - len(non_valides),
                        "taux": round((nb - len(non_valides)) / nb, 4) if nb else None},
        "elements_non_valides": [
            {"id": e.id, "identifiant": e.identifiant, "type_element": e.type_element, "statut": e.statut,
             "calcule": e.resultat_calcul is not None}
            for e in non_valides
        ],
        "cout": cout,
        "problemes_dqe": problemes,
        "dernier_dqe": ({"date": dernier_dqe.date, "total_general": dernier_dqe.donnees.get("total_general")}
                        if dernier_dqe else None),
        "coherence": coherence["resume"] if coherence else None,
        "alertes": alertes,
        "dernieres_actions": _regrouper(evs[:300], 10),
    }


# ---------------------------------------------------------------------------
# Staff (adoption produit)
# ---------------------------------------------------------------------------

def analytics_staff() -> dict:
    debut = date_debut_fiabilite()
    evs = EvenementProduit.objects.all()
    il_y_a_30j = timezone.now() - timedelta(days=30)

    def distincts_mensuels(champ):
        rows = (evs.filter(**{f"{champ}__isnull": False}).annotate(mois=TruncMonth("date"))
                .values("mois").annotate(n=Count(champ, distinct=True)))
        comptes = {(r["mois"].year, r["mois"].month): r["n"] for r in rows}
        return [
            {"mois": f"{a:04d}-{m:02d}",
             "valeur": comptes.get((a, m), 0)
             if debut and (a, m) >= (debut.year, debut.month) else None}
            for a, m in _mois_glissants()
        ]

    # Funnel : cohorte = cabinets dont l'INSCRIPTION est journalisée.
    # Les cabinets inscrits avant la mise en service du journal sont
    # exclus (leur parcours est inconnu), pas comptés comme "bloqués".
    cohorte = set(evs.filter(type=T.INSCRIPTION, entreprise__isnull=False).values_list("entreprise_id", flat=True))
    etapes = [
        ("inscription", "Inscription", None),
        ("premier_projet", "Premier projet", T.PROJET_CREE),
        ("import_ifc", "Import IFC", T.IMPORT_IFC),
        ("premiere_validation", "Première validation", T.ELEMENT_VALIDE),
        ("premier_dqe", "Premier DQE", T.DQE_GENERE),
    ]
    funnel = []
    for cle, libelle, type_ev in etapes:
        if type_ev is None:
            n = len(cohorte)
        else:
            n = evs.filter(type=type_ev, entreprise_id__in=cohorte).values("entreprise_id").distinct().count()
        funnel.append({"etape": cle, "libelle": libelle, "cabinets": n})

    derniers = _derniers_dqe(evs)
    ia = evs.filter(type=T.APPEL_IA)
    ia_par_source = Counter(ia.values_list("donnees__source", flat=True))
    ia_echecs = sum(1 for d in ia.values_list("donnees", flat=True) if d.get("succes") is False)

    return {
        "date_debut_fiabilite": debut,
        "totaux": {
            "cabinets_inscrits": len(cohorte),
            "cabinets_actifs_30j": evs.filter(date__gte=il_y_a_30j, entreprise__isnull=False)
                                      .values("entreprise_id").distinct().count(),
            "utilisateurs_actifs_30j": evs.filter(date__gte=il_y_a_30j, utilisateur__isnull=False)
                                          .values("utilisateur_id").distinct().count(),
            "projets_crees": evs.filter(type=T.PROJET_CREE).count(),
            "imports_ifc": evs.filter(type=T.IMPORT_IFC).count(),
            "dqe_generes": evs.filter(type=T.DQE_GENERE).count(),
            "montant_total_traite": sum(e.donnees.get("total_general", 0) for e in derniers.values()),
            "appels_ia": ia.count(),
        },
        "ia": {"par_source": dict(ia_par_source), "echecs": ia_echecs},
        "funnel": funnel,
        "mensuel": {
            "inscriptions": _serie_mensuelle(evs.filter(type=T.INSCRIPTION), debut),
            "projets_crees": _serie_mensuelle(evs.filter(type=T.PROJET_CREE), debut),
            "dqe_generes": _serie_mensuelle(evs.filter(type=T.DQE_GENERE), debut),
            "imports_ifc": _serie_mensuelle(evs.filter(type=T.IMPORT_IFC), debut),
            "appels_ia": _serie_mensuelle(ia, debut),
            "cabinets_actifs": distincts_mensuels("entreprise"),
            "utilisateurs_actifs": distincts_mensuels("utilisateur"),
        },
        "notes": [
            "Montant total traité = somme du DERNIER DQE généré de chaque projet (pas de double comptage).",
            "Funnel : cohorte des cabinets dont l'inscription est journalisée ; les cabinets antérieurs "
            "au journal sont exclus faute d'historique.",
        ],
    }
