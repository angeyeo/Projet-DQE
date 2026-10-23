"""
Maçonnerie et enduit métrés à partir du PLAN DES MURS (issue #73, audit T14).

Activé par projet (Projet.metrer_murs_depuis_plan, désactivé par défaut :
les DQE existants ne changent pas). Pour chaque poutre VALIDÉE dont le
tronçon porte un mur sur le plan des murs :

    L_net   = L_axes − (a_origine + a_destination) / 2      [m]
              (a = côté validé des poteaux aux deux extrémités)
    h_mur   = h_étage − h_poutre                           [m]
              (h_poutre = hauteur VALIDÉE de la poutre ; même hauteur de mur
              que pour la charge des murs)
    S_brute = L_net × h_mur × n                            [m²]
              n = 1 au rez-de-chaussée, nb_niveaux − 1 aux étages
              (un seul plan des murs pour tous les étages, règle actuelle)
    S_nette = S_brute × (1 − baies / 100)   si la part des baies est saisie
            = S_brute × 0,80                sinon (règle B6, confirmée par le
              technicien le 21/10/2026 : 20 % d'ouvertures) -> « estimé »

    Agglos 15 creux (m²) = S_nette   (mur en agglos de 15 : poids validé par
                                      l'ingénieur le 12/10/2026)
    Enduit (m²)          = 2 × S_nette (deux faces)

Non compris (non lus dans le plan, jamais supposés) : soubassement en agglos
pleins, enduit sous plafond, cloisons légères. Les saisir en postes.

DOUBLE COMPTAGE : si le projet a déjà un poste à ratio « maçonnerie »
(ou « enduit »), le métré du plan correspondant n'est PAS ajouté (le poste
saisi prime) et une alerte le dit. Un poste simple dont la désignation
évoque des agglos ou un enduit est signalé (il pourrait faire doublon).
"""

from decimal import ROUND_HALF_UP, Decimal

from moteur_calcul.constantes import COEFFICIENT_PLEIN_MACONNERIE_ELEVATION

from ..models import ElementStructurel, PosteComplementaire

TYPE_ELEMENT = "MURS_PLAN"
DESIGNATION_AGGLOS = "Agglos 15 creux — murs du plan"
DESIGNATION_ENDUIT = "Enduit 2 faces — murs du plan"


def _v(x, n=2):
    return f"{round(float(x), n):g}".replace(".", ",")


def D(x):
    return Decimal(str(x))


def _cote_cm(poteau):
    res = (poteau.resultat_valide or {}) if poteau and poteau.statut == ElementStructurel.Statut.VALIDE else {}
    return res.get("cote_cm") or None


def troncons_murs(projet):
    """Tronçons de mur du plan, avec leur métré. Renvoie (troncons, alertes)."""
    rdc, etages = set(projet.murs_rdc or []), set(projet.murs_etages or [])
    alertes, troncons = [], []
    if not (rdc or etages):
        return troncons, ["ALERTE : métré des murs demandé, mais aucun mur n'est placé sur le plan des murs."]
    if not projet.hauteur_etage:
        return troncons, ["ALERTE : métré des murs impossible : hauteur d'étage non renseignée."]
    n_etages = max((projet.nb_niveaux or 1) - 1, 0)
    poutres = (projet.elements.filter(type_element=ElementStructurel.TypeElement.POUTRE)
               .select_related("poteau_origine", "poteau_destination").order_by("id"))
    vus = set()
    for p in poutres:
        cle = (p.resultat_calcul or {}).get("cle_segment")
        niveaux = [("RDC", 1)] * (cle in rdc) + [("étages", n_etages)] * (cle in etages and n_etages > 0)
        if not cle or not niveaux or cle in vus:
            continue
        vus.add(cle)
        if p.statut != ElementStructurel.Statut.VALIDE:
            alertes.append(f"ALERTE : mur sur la poutre {p.identifiant} non métré : poutre non validée.")
            continue
        res = p.resultat_valide or {}
        h_poutre = D(res.get("hauteur_cm") or 0) / 100
        if not p.portee or not h_poutre:
            alertes.append(f"ALERTE : mur sur la poutre {p.identifiant} non métré : portée ou hauteur absente.")
            continue
        a1, a2 = _cote_cm(p.poteau_origine), _cote_cm(p.poteau_destination)
        if a1 is None or a2 is None:
            alertes.append(f"ALERTE : mur sur la poutre {p.identifiant} métré entre axes : poteau d'extrémité "
                           "non validé ou non relié (longueur légèrement surestimée).")
            a1, a2 = a1 or 0, a2 or 0
        # Calcul en Decimal (valeurs lues en texte) : aucun arrondi
        # intermédiaire, seule la quantité finale est arrondie au millième.
        l_net = D(p.portee) - (D(a1) + D(a2)) / 200
        h_mur = D(projet.hauteur_etage) - h_poutre
        if l_net <= 0 or h_mur <= 0:
            alertes.append(f"ALERTE : mur sur la poutre {p.identifiant} non métré : longueur ou hauteur de mur nulle.")
            continue
        for niveau, n in niveaux:
            troncons.append({"poutre": p.identifiant, "niveau": niveau, "nombre": n, "longueur_axes_m": p.portee,
                             "longueur_nette_m": float(l_net), "hauteur_mur_m": float(h_mur),
                             "surface_brute_m2": float(l_net * h_mur * n), "_s": l_net * h_mur * n})
    return troncons, alertes


def lignes_murs_depuis_plan(projet, prix_unitaires, problemes, _ligne, _prix, lot):
    """Lignes de DQE (agglos et enduit) et hypothèses. `_ligne` et `_prix`
    sont ceux de dqe_calculator (même format, mêmes contrôles de prix)."""
    hypotheses = []
    ratio = set(projet.postes_complementaires.filter(mode=PosteComplementaire.Mode.RATIO)
                .values_list("type_poste", flat=True))
    simples = projet.postes_complementaires.filter(mode=PosteComplementaire.Mode.SIMPLE)
    doublons = [s.designation for s in simples
                if any(m in (s.designation or "").lower() for m in ("agglo", "enduit", "maçonnerie", "maconnerie"))]
    if doublons:
        hypotheses.append("ALERTE : poste(s) saisi(s) pouvant faire double emploi avec le métré du plan des murs : "
                          + ", ".join(f"« {d} »" for d in doublons) + ". Vérifiez avant de chiffrer.")

    troncons, alertes = troncons_murs(projet)
    hypotheses += alertes
    if not troncons:
        return [], hypotheses

    s_brute = sum((t.pop("_s") for t in troncons), Decimal("0"))
    baies = projet.pourcentage_baies_murs or 0
    if baies:
        coef, origine = 1 - D(baies) / 100, "calcul_moteur"
        texte_coef = f"× (1 − {_v(baies, 1)} % de baies saisies)"
    else:
        coef, origine = D(COEFFICIENT_PLEIN_MACONNERIE_ELEVATION), "ratio_reference"
        texte_coef = f"× {_v(coef)} (20 % d'ouvertures, règle B6)"
        hypotheses.append(
            f"Murs du plan : part des baies non saisie, surface de mur × {_v(coef)} (20 % d'ouvertures, règle B6 "
            "confirmée par le technicien le 21/10/2026). Saisissez la part des baies pour un métré exact.")
    # Surface de mur arrondie au millième, puis enduit = 2 × cette surface :
    # le DQE imprimé se vérifie à la main sans écart d'arrondi.
    s_nette = (s_brute * coef).quantize(Decimal("0.001"), rounding=ROUND_HALF_UP)
    nb_rdc = sum(1 for t in troncons if t["niveau"] == "RDC")
    nb_etages = sum(1 for t in troncons if t["niveau"] == "étages")
    formule = (f"Σ (L entre axes − a) × (h étage − h poutre) × niveaux = {_v(s_brute)} m² "
               f"({nb_rdc} tronçon(s) RDC, {nb_etages} aux étages) {texte_coef}")
    hypotheses.append(
        "Maçonnerie et enduit métrés à partir du plan des murs (agglos de 15, enduit sur 2 faces). Non compris : "
        "soubassement en agglos pleins, enduit sous plafond, cloisons légères (à saisir en postes).")

    lignes = []
    for type_poste, designation, quantite, formule_ligne in (
        ("maconnerie", DESIGNATION_AGGLOS, s_nette, formule),
        ("enduit", DESIGNATION_ENDUIT, 2 * s_nette, f"2 faces × {_v(s_nette, 3)} m² de mur"),
    ):
        if type_poste in ratio:
            hypotheses.append(f"ALERTE : un poste à ratio « {type_poste} » existe : la ligne « {designation} » n'est "
                              "pas ajoutée (pas de double comptage). Supprimez le poste pour utiliser le plan des murs.")
            continue
        cle = "agglos_15_creux_m2" if type_poste == "maconnerie" else "enduit_m2"
        avant = len(problemes)
        pu = _prix(prix_unitaires, cle, problemes, "le métré du plan des murs")
        if pu is None:
            for p in problemes[avant:]:
                p["plan_murs"] = True
            continue
        ligne = _ligne(element_id=None, repere="MURS", type_element=TYPE_ELEMENT, designation=designation,
                       categorie="MACONNERIE" if type_poste == "maconnerie" else "ENDUIT", unite="m²",
                       quantite=quantite.quantize(Decimal("0.001"), rounding=ROUND_HALF_UP), pu=pu,
                       source_quantite=origine,
                       cle_prix=cle, formule=formule_ligne)
        ligne["lot"] = lot
        ligne["detail_murs"] = troncons
        lignes.append(ligne)
    return lignes, hypotheses
