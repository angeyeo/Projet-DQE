"""
Trame structurelle -- feuille de route "Ma partie -- Backend", Jour 1
§1.3 et Jour 2 §2.3, et Phase B de la feuille de route "Import plan
automatique" (positions réelles, sans grille uniforme).

generer_poteau_sur_grille() est appelée en boucle par Samuel dans son
endpoint generer_trame/ (son Jour 2) : elle doit rester prête AVANT
qu'il attaque cette partie -- c'est la priorité du jour.

generer_poteau_depuis_position_reelle() et generer_poutre_depuis_positions_reelles()
(Phase B) couvrent le cas import : une trame réelle n'est jamais une
grille parfaite (poteaux manquants, décrochés, portées irrégulières --
voir import_ifc/lecture_ifc.py), donc au lieu d'indices (i, j) sur une
grille régulière, on part du nuage de points réel détecté dans l'IFC et
on retrouve les voisins direct de chaque poteau par proximité.

Ne touche à aucun modèle Django ni à la base : ce sont des fonctions
pures, testables en isolation sans dépendre des champs pas encore
ajoutés côté Projet/ElementStructurel (nb_travees_x, position_x...).
"""

from ..hypotheses import CONTENU_G_FORFAITAIRE, G_PLANCHER_FORFAITAIRE_KN_M2, HypothesesCalcul, hypotheses_par_defaut
from ..import_ifc.lecture_ifc import TOLERANCE_ALIGNEMENT_M
from ..constantes import LF_SUR_L0_DEFAUT, PORTEE_MAX_M, PORTEE_MIN_POUTRE_M, RESISTANCE_BETON_DEFAUT
from ..unites import cm_vers_m
from .descente_charges import calculer_surface_influence, cumuler_charges_exploitation_degressives
from .dimensionnement_poteaux import dimensionner_poteau
from .dimensionnement_poutres import dimensionner_poutre, hauteur_poutre_retenue
from .dimensionnement_semelles import dimensionner_semelle

# Conservé pour compatibilité : la valeur vit désormais dans hypotheses.py
# et n'est appliquée que si le projet ne fournit ni G ni composition.
CHARGE_PERMANENTE_FORFAITAIRE_KN_M2 = G_PLANCHER_FORFAITAIRE_KN_M2

HYPOTHESE_G_FORFAITAIRE = (
    f"HYPOTHÈSE : charge permanente des planchers G = {G_PLANCHER_FORFAITAIRE_KN_M2} kN/m² "
    f"(valeur par défaut validée : {CONTENU_G_FORFAITAIRE})."
)

LARGEUR_POUTRE_M = 0.20  # largeur par défaut de dimensionner_poutre()
COTE_POTEAU_INITIAL_CM = 20  # point de départ de l'itération sur le poids propre du poteau
MAX_ITERATIONS_POIDS_PROPRE = 6


def _hyp(hyp, charge_exploitation, taux_travail_sol):
    if hyp is not None:
        return hyp
    return hypotheses_par_defaut(charge_exploitation, taux_travail_sol)


def _etape(etape, formule, calcul, resultat, unite):
    return {"etape": etape, "formule": formule, "calcul": calcul, "resultat": resultat, "unite": unite}


def cle_segment(a, b):
    """Identifiant d'un tronçon de poutre entre deux poteaux, indépendant
    du sens et de la numérotation : coordonnées des extrémités au cm,
    triées. Sert à placer les murs (plan des murs du projet) et survit à
    une régénération de la trame tant que la géométrie ne change pas."""
    def pt(p):
        return (round(float(p[0]), 2) + 0.0, round(float(p[1]), 2) + 0.0)
    p1, p2 = sorted((pt(a), pt(b)))
    return f"{p1[0]:.2f};{p1[1]:.2f}|{p2[0]:.2f};{p2[1]:.2f}"


def poids_propre_poutre_kn_m(portee, hyp: HypothesesCalcul):
    """Poids propre linéique d'une poutre de la trame : b × h(portée) × γ_béton (kN/m),
    avec la MÊME hauteur que celle retenue par dimensionner_poutre() : h = max(L/8 ; 25 cm)."""
    if not portee:
        return 0.0
    return LARGEUR_POUTRE_M * hauteur_poutre_retenue(portee) * hyp.poids_volumique_beton_kn_m3


def charge_mur_kn_m(portee, hyp: HypothesesCalcul, hauteur_etage):
    """Charge linéique d'un mur posé sur une poutre (kN/m) :
        h_mur = h_étage − h_poutre(l)                   [m]
        q_mur = p_mur × h_mur × (1 − baies / 100)       [kN/m² × m = kN/m]
    Renvoie (q_mur, h_mur)."""
    if hauteur_etage is None or hauteur_etage <= 0:
        raise ValueError("Hauteur d'étage requise pour calculer la charge des murs.")
    h_poutre = hauteur_poutre_retenue(portee)
    h_mur = hauteur_etage - h_poutre
    if h_mur <= 0:
        raise ValueError(
            f"Hauteur d'étage ({_virgule(hauteur_etage)} m) inférieure à la hauteur de la poutre "
            f"({_virgule(round(h_poutre, 3))} m) pour une portée de {_virgule(portee)} m : mur impossible."
        )
    return hyp.poids_murs_kn_m2 * h_mur * (1 - hyp.pourcentage_baies_murs / 100), h_mur


def _somme_murs(hyp, portees, segments, niveau, hauteur_etage):
    """Σ (l/2) × q_mur sur les tronçons aboutissant au poteau qui portent un
    mur de ce niveau. Renvoie (total kN, détail [(l, h_mur)])."""
    detail = []
    for cote, l in portees.items():
        if l and hyp.mur_sur((segments or {}).get(cote), niveau):
            q, h = charge_mur_kn_m(l, hyp, hauteur_etage)
            detail.append((l, h, q))
    return sum((l / 2) * q for l, _, q in detail), detail


def _etape_murs(titre, hyp, total, detail):
    facteur = f"×{_virgule(round(1 - hyp.pourcentage_baies_murs / 100, 4))}" if hyp.pourcentage_baies_murs else ""
    return _etape(
        titre, "Σ (l/2) × p_mur × (h_étage − h_poutre)" + (" × (1 − baies)" if facteur else ""),
        " + ".join(f"({_virgule(l)}/2)×{_virgule(hyp.poids_murs_kn_m2)}×{_virgule(round(h, 3))}{facteur}"
                   for l, h, _ in detail),
        round(total, 2), "kN",
    )


def _calcul_noeud(portees, hyp: HypothesesCalcul, nb_niveaux, usage_batiment, hauteur_etage, segments=None):
    """Descente de charges d'UN poteau (tous niveaux), puis poteau et semelle.

    portees : dict gauche/droite/avant/arriere (m), 0 en rive.
    segments : dict gauche/droite/avant/arriere -> cle_segment() du tronçon
    (pour savoir s'il porte un mur) ; None = aucun mur rattachable.
    Renvoie un dict avec charges ELU/ELS, résultats et TRACE complète.
    """
    nb_niveaux = nb_niveaux or 1
    if nb_niveaux < 1:
        raise ValueError("nb_niveaux doit être un entier positif (au moins 1).")
    pg, pd, pa, pr = (portees[k] for k in ("gauche", "droite", "avant", "arriere"))
    surface = calculer_surface_influence(pg, pd, pa, pr)
    trace = [_etape(
        "Surface d'influence", "S = (lg/2 + ld/2) × (la/2 + lr/2)",
        f"({pg}/2 + {pd}/2) × ({pa}/2 + {pr}/2)", round(surface, 3), "m²",
    )]
    g_plancher = surface * hyp.g_plancher_kn_m2
    q_niveau = surface * hyp.q_kn_m2
    q_toiture = surface * hyp.q_toiture_effective
    trace.append(_etape("G planchers / niveau", "G = S × g", f"{round(surface, 3)} × {hyp.g_plancher_kn_m2}",
                        round(g_plancher, 2), "kN"))
    charpente = hyp.type_toiture == "charpente"
    g_toiture = surface * hyp.g_toiture_effective
    if charpente:
        trace.append(_etape("G toiture (charpente + couverture)", "G0 = S × g_toiture",
                            f"{round(surface, 3)} × {hyp.g_toiture_kn_m2}", round(g_toiture, 2), "kN"))
    if nb_niveaux > 1:
        trace.append(_etape("Q / étage", "Q = S × q", f"{round(surface, 3)} × {hyp.q_kn_m2}", round(q_niveau, 2), "kN"))
    trace.append(_etape("Q toiture", "Q0 = S × q_toiture", f"{round(surface, 3)} × {hyp.q_toiture_effective}",
                        round(q_toiture, 2), "kN"))

    pp_poutres = 0.0
    if hyp.inclure_poids_propre_ossature:
        # Moitié de chaque poutre aboutissant au poteau.
        pp_poutres = sum((l / 2) * poids_propre_poutre_kn_m(l, hyp) for l in (pg, pd, pa, pr) if l)
        trace.append(_etape(
            "Poids propre poutres / niveau", "Σ (l/2) × b × h(l) × γ, h = max(l/8 ; 25 cm)",
            " + ".join(f"({l}/2)×{LARGEUR_POUTRE_M}×{round(hauteur_poutre_retenue(l), 3)}×{hyp.poids_volumique_beton_kn_m3}"
                       for l in (pg, pd, pa, pr) if l) or "0",
            round(pp_poutres, 2), "kN",
        ))

    # Moitié de chaque mur porté par un tronçon aboutissant au poteau, et
    # seulement là où un mur est placé. Les murs d'un étage reposent sur
    # les poutres du plancher situé dessous : le poteau du RDC porte les
    # murs des n − 1 étages ; ceux du RDC reposent sur les longrines.
    # Issue #81 : chaque étage R+k a son plan (celui du R+1 par défaut).
    nb_murs_poteau = nb_niveaux - 1
    murs_etages = [_somme_murs(hyp, portees, segments, k, hauteur_etage) for k in range(1, nb_niveaux)]
    plans_identiques = not hyp.murs_etages_specifiques
    g_murs, detail_etages = murs_etages[0] if murs_etages else (0.0, [])
    g_murs_rdc_total, detail_rdc = _somme_murs(hyp, portees, segments, "rdc", hauteur_etage)
    if plans_identiques:
        g_murs_etages = nb_murs_poteau * g_murs
        if detail_etages:
            trace.append(_etape_murs("Murs d'étage / niveau", hyp, g_murs, detail_etages))
    else:
        g_murs_etages = sum(g for g, _ in murs_etages)
        for k, (g_k, detail_k) in enumerate(murs_etages, start=1):
            if detail_k:
                trace.append(_etape_murs(f"Murs du R+{k}", hyp, g_k, detail_k))

    q_deg = cumuler_charges_exploitation_degressives(
        charge_toiture_kn=q_toiture, charges_etages_kn=[q_niveau] * (nb_niveaux - 1), usage_batiment=usage_batiment,
    )
    q_cumul = q_deg["cumuls_kn"][-1]
    coef = q_deg["coefficients"][-1]

    cote_cm = COTE_POTEAU_INITIAL_CM
    for _ in range(MAX_ITERATIONS_POIDS_PROPRE):
        pp_poteau = (cm_vers_m(cote_cm) ** 2 * hauteur_etage * hyp.poids_volumique_beton_kn_m3
                     if hyp.inclure_poids_propre_ossature else 0.0)
        # Dalle : le dernier niveau est un plancher comme les autres.
        # Charpente : le dernier niveau ne porte que la toiture (G0).
        g_cumul = ((nb_niveaux - 1) * g_plancher + g_toiture + nb_niveaux * (pp_poutres + pp_poteau)
                   + g_murs_etages)
        nu = hyp.elu(g_cumul, q_cumul)
        resultat_poteau = dimensionner_poteau(charge_calculee=nu, hauteur_poteau=hauteur_etage)
        if not hyp.inclure_poids_propre_ossature or resultat_poteau["cote_cm"] == cote_cm:
            break
        cote_cm = resultat_poteau["cote_cm"]
    ns = hyp.els(g_cumul, q_cumul)

    if hyp.inclure_poids_propre_ossature:
        trace.append(_etape("Poids propre poteau / niveau", "a² × h_étage × γ",
                            f"{cm_vers_m(cote_cm)}² × {hauteur_etage} × {hyp.poids_volumique_beton_kn_m3}",
                            round(pp_poteau, 2), "kN"))
    if plans_identiques:
        formule_murs = " + (n − 1) × G murs" if g_murs else ""
        calcul_murs = f" + {nb_murs_poteau} × {round(g_murs, 2)}" if g_murs else ""
    else:
        formule_murs = " + Σ G murs des étages" if g_murs_etages else ""
        calcul_murs = (" + (" + " + ".join(str(round(g, 2)) for g, _ in murs_etages) + ")") if g_murs_etages else ""
    if charpente:
        trace.append(_etape("G cumulée", "G = (n − 1) × G plancher + G toiture + n × poids propres" + formule_murs,
                            f"{nb_niveaux - 1} × {round(g_plancher, 2)} + {round(g_toiture, 2)} + {nb_niveaux} × "
                            f"({round(pp_poutres, 2)} + {round(pp_poteau, 2)})" + calcul_murs, round(g_cumul, 2), "kN"))
    else:
        trace.append(_etape("G cumulée", "G = n × (G planchers + poids propres)" + formule_murs,
                            f"{nb_niveaux} × ({round(g_plancher, 2)} + {round(pp_poutres, 2)} + {round(pp_poteau, 2)})"
                            + calcul_murs, round(g_cumul, 2), "kN"))
    if q_deg["degression_appliquee"]:
        calcul_q = f"{_virgule(round(q_toiture, 2))} + " + " + ".join(
            f"{_virgule(k)} × {_virgule(round(q_niveau, 2))}" for k in q_deg["coefficients_par_etage"])
    else:
        calcul_q = " + ".join([_virgule(round(q_toiture, 2))] + [_virgule(round(q_niveau, 2))] * (nb_niveaux - 1))
    trace.append(_etape(
        "Q cumulée (dégression)" if q_deg["degression_appliquee"] else "Q cumulée",
        "Q = Q0 + Q1 + 0,9 Q2 + 0,8 Q3 + 0,7 Q4…" if q_deg["degression_appliquee"] else "Q = Q0 + Σ Qi",
        calcul_q, round(q_cumul, 2), "kN",
    ))
    trace.append(_etape("Effort ELU", f"Nu = {hyp.gamma_g_elu} G + {hyp.gamma_q_elu} Q",
                        f"{hyp.gamma_g_elu} × {round(g_cumul, 2)} + {hyp.gamma_q_elu} × {round(q_cumul, 2)}",
                        round(nu, 2), "kN"))
    trace.append(_etape("Effort ELS", "Ns = G + Q", f"{round(g_cumul, 2)} + {round(q_cumul, 2)}", round(ns, 2), "kN"))
    trace_poteau = trace + _trace_section_poteau(nu, hauteur_etage, resultat_poteau)

    # Semelle : effort du poteau + murs du RDC apportés par les longrines.
    g_murs_rdc = g_murs_rdc_total if hyp.murs_rdc_sur_semelles else 0.0
    nu_semelle = nu + hyp.gamma_g_elu * g_murs_rdc
    ns_semelle = ns + hyp.gamma_g_els * g_murs_rdc
    etapes_murs_rdc = []
    if g_murs_rdc:
        etapes_murs_rdc = [
            _etape_murs("Murs du RDC (longrines → semelle)", hyp, g_murs_rdc, detail_rdc),
            _etape("Effort ELU semelle", f"Nu,s = Nu + {hyp.gamma_g_elu} G murs RDC",
                   f"{round(nu, 2)} + {hyp.gamma_g_elu} × {round(g_murs_rdc, 2)}", round(nu_semelle, 2), "kN"),
            _etape("Effort ELS semelle", "Ns,s = Ns + G murs RDC",
                   f"{round(ns, 2)} + {round(g_murs_rdc, 2)}", round(ns_semelle, 2), "kN"),
        ]
    resultat_semelle = dimensionner_semelle(
        charge_poteau=nu_semelle, taux_travail_sol=hyp.contrainte_sol_kn_m2, cote_poteau_cm=resultat_poteau["cote_cm"],
        charge_service=ns_semelle, methode=hyp.methode_semelles, inclure_poids_propre=hyp.inclure_poids_propre_ossature,
    )
    n_dim = resultat_semelle["charge_dimensionnement_kn"]
    trace_semelle = trace + etapes_murs_rdc + [
        _etape("Côté théorique", f"A = √(N{'u' if hyp.methode_semelles == 'ELU' else 's'} / σsol)",
               f"√({n_dim} / {resultat_semelle['contrainte_sol_kn_m2']})", resultat_semelle["cote_theorique_cm"], "cm"),
        _etape("Côté retenu", "arrondi 5 cm" + (" + poids propre" if hyp.inclure_poids_propre_ossature else ""),
               f"pression sol {resultat_semelle['pression_sol_kn_m2']} ≤ {resultat_semelle['contrainte_sol_kn_m2']} kN/m²",
               resultat_semelle["cote_cm"], "cm"),
        _etape("Hauteur", "d ≥ (A − b)/4 ; h = arrondi5(d + 5), h ≥ 20",
               f"({resultat_semelle['cote_cm']} − {resultat_poteau['cote_cm']})/4", resultat_semelle["hauteur_cm"], "cm"),
        _etape("Acier / direction", "As = Nu (A − b) / (8 d fsu)",
               f"Nu = {round(nu_semelle, 2)} kN, d = {resultat_semelle['hauteur_utile_cm']} cm",
               resultat_semelle["section_acier_par_direction_cm2"], "cm²"),
    ]
    resultat_poteau = {**resultat_poteau, "trace": trace_poteau, "hypotheses_calcul": hyp.vers_dict(),
                       "charge_elu_kn": round(nu, 2), "charge_els_kn": round(ns, 2)}
    resultat_semelle = {**resultat_semelle, "trace": trace_semelle, "hypotheses_calcul": hyp.vers_dict(),
                        "charge_elu_kn": round(nu_semelle, 2), "charge_els_kn": round(ns_semelle, 2)}
    return {
        "charge_elu_kn": nu,
        "charge_els_kn": ns,
        "charge_elu_semelle_kn": nu_semelle,
        "charge_els_semelle_kn": ns_semelle,
        "charge_murs_niveau_kn": round(g_murs, 2),  # R+1
        "charge_murs_etages_kn": round(g_murs_etages, 2),  # tous les étages
        "charge_murs_rdc_kn": round(g_murs_rdc, 2),
        "resultat_poteau": resultat_poteau,
        "resultat_semelle": resultat_semelle,
        "nb_niveaux": nb_niveaux,
        "charge_g_cumulee_kn": round(g_cumul, 2),
        "charge_q_cumulee_kn": q_cumul,
        "coefficient_degression": coef,
        "degression_appliquee": q_deg["degression_appliquee"],
        "surface_influence_m2": round(surface, 4),
        "hypotheses": hyp.messages(),
    }


def _v(valeur, decimales=3):
    """Nombre lisible dans une trace : décimales utiles seulement."""
    return f"{round(valeur, decimales):g}"


def _trace_section_poteau(nu, hauteur_etage, res):
    """Étapes de la section et du ferraillage d'un poteau, avec les valeurs
    (issue #96) ; la formule de flambement est celle de la branche
    réellement appliquée par le moteur."""
    a = res["cote_cm"]
    lam = res["elancement"]
    lf = LF_SUR_L0_DEFAUT * hauteur_etage
    i_cm = min(res.get("largeur_cm") or a, res.get("profondeur_cm") or a) / 12 ** 0.5
    if lam <= 50:
        formule_alpha = "α = 0,85 / (1 + 0,2 (λ/35)²)  (λ ≤ 50)"
    else:
        formule_alpha = "α = 0,6 (50/λ)²  (50 < λ ≤ 70)"
    return [
        _etape("Section du poteau", "B ≥ 1,3 Nu / (0,7 fc28) ; a = √B arrondi à 5 cm, 20 cm au minimum",
               f"1,3 × {_v(nu / 1000, 5)} MN / (0,7 × {_v(RESISTANCE_BETON_DEFAUT)} MPa) = "
               f"{_v(res['section_theorique_cm2'])} cm² ⇒ a ≥ {_v(res['section_theorique_cm2'] ** 0.5, 1)} cm",
               a, "cm"),
        _etape("Flambement", "λ = lf / i, lf = k × l0, i = a / √12 ; " + formule_alpha,
               f"lf = {_v(LF_SUR_L0_DEFAUT)} × {_v(hauteur_etage)} = {_v(lf)} m ; i = {_v(i_cm, 2)} cm ; λ = {_v(lam)}",
               res["coefficient_alpha"], "—"),
        _etape("Acier longitudinal", "A = max(A_min ; (Nu/α − Br fc28 / (0,9 γb)) γs / fe), Br = (a − 2)²",
               f"Br = ({_v(a)} − 2)² = {_v((a - 2) ** 2)} cm² ; A théorique = {_v(res['section_acier_theorique_cm2'])} cm² ; "
               f"A_min = {_v(res['section_acier_min_cm2'])} cm²",
               res["section_acier_retenue_cm2"], "cm²"),
    ]


def _virgule(v):
    return f"{v:g}".replace(".", ",")


def generer_poteau_sur_grille(
    i, j, portee_x, portee_y, nb_travees_x, nb_travees_y,
    charge_exploitation, hauteur_etage, nb_niveaux=1, usage_batiment=None, taux_travail_sol=None,
    hyp=None,
):
    """
    (i, j) : indices de la grille, i de 0 à nb_travees_x inclus, j de 0
    à nb_travees_y inclus (nb_travees_x travées => nb_travees_x + 1
    files de poteaux dans cette direction).

    Calcule la position réelle du poteau et sa charge ELU en réutilisant
    calculer_surface_influence() (Module 1) : les portées vers chaque
    côté valent portee_x/portee_y sauf en bord de grille, où elles
    valent 0 (pas de travée au-delà du bord).

    nb_niveaux : int, optionnel (défaut 1 -- comportement historique
    inchangé si l'appelant ne le précise pas)
        Nombre de niveaux dont la charge descend sur ce poteau (voir
        _cumuler_charge_poteau_multi_niveaux). La loi de dégression
        (Module 1) est appliquée à la charge d'exploitation cumulée.
    usage_batiment : str, optionnel
        Usage du bâtiment (voir constantes.USAGES_AVEC_DEGRESSION) --
        détermine si la dégression s'applique. Si non fourni, la
        dégression est appliquée par défaut (voir
        cumuler_charges_exploitation_degressives).

    Retour :
    {
        "x": ..., "y": ...,                # mètres, position réelle
        "charge_elu_kn": ...,
        "resultat_poteau": {...},          # sortie de dimensionner_poteau()
        "resultat_semelle": {...},         # sortie de dimensionner_semelle(),
                                            # avec cote_poteau_cm renseigné (Module 6)
    }
    """
    if not (0 <= i <= nb_travees_x) or not (0 <= j <= nb_travees_y):
        raise ValueError(
            f"Indices hors grille : (i={i}, j={j}) pour une trame "
            f"{nb_travees_x}x{nb_travees_y} (i doit être dans [0, {nb_travees_x}], "
            f"j dans [0, {nb_travees_y}])."
        )

    portees = {
        "gauche": portee_x if i > 0 else 0,
        "droite": portee_x if i < nb_travees_x else 0,
        "avant": portee_y if j > 0 else 0,
        "arriere": portee_y if j < nb_travees_y else 0,
    }
    hyp = _hyp(hyp, charge_exploitation, taux_travail_sol)
    x, y = i * portee_x, j * portee_y
    segments = {
        "gauche": cle_segment((x, y), ((i - 1) * portee_x, y)),
        "droite": cle_segment((x, y), ((i + 1) * portee_x, y)),
        "avant": cle_segment((x, y), (x, (j - 1) * portee_y)),
        "arriere": cle_segment((x, y), (x, (j + 1) * portee_y)),
    }
    noeud = _calcul_noeud(portees, hyp, nb_niveaux, usage_batiment, hauteur_etage, segments=segments)
    return {"x": x, "y": y, **noeud}


def _trouver_voisin_direct(poteau, voisins, axe, sens):
    """
    Cherche, parmi `voisins` (nuage de points détecté, ex. sortie
    d'extraire_poteaux()), le voisin direct de `poteau` dans une seule
    direction cardinale :
        axe  : "x" ou "y" -- l'axe sur lequel on avance.
        sens : +1 (droite/arrière) ou -1 (gauche/avant).

    "Aligné" = même ligne/colonne de grille au sens de la Phase A :
    écart <= TOLERANCE_ALIGNEMENT_M sur l'axe PERPENDICULAIRE (mêmes
    poteaux réels ne sont jamais parfaitement alignés). Parmi les
    poteaux alignés situés dans la bonne direction, on retient celui à
    distance minimale -- c'est le voisin "direct" (rien entre les deux).

    Retour : (voisin, distance) -- (None, 0.0) si aucun voisin dans
    cette direction (poteau en bord de trame réelle).
    """
    axe_perp = "y" if axe == "x" else "x"
    meilleur = None
    meilleure_distance = None
    for v in voisins:
        if v is poteau or v.get("guid") == poteau.get("guid"):
            continue
        if abs(v[axe_perp] - poteau[axe_perp]) > TOLERANCE_ALIGNEMENT_M:
            continue
        delta = (v[axe] - poteau[axe]) * sens
        # delta doit dépasser la tolérance pour compter comme un voisin
        # distinct dans cette direction (évite qu'un point quasi-confondu,
        # bruit de relevé, ne soit pris pour un voisin direct).
        if delta <= TOLERANCE_ALIGNEMENT_M:
            continue
        if meilleure_distance is None or delta < meilleure_distance:
            meilleure_distance = delta
            meilleur = v
    return meilleur, (meilleure_distance or 0.0)


def _nom_poteau(p):
    nom = p.get("nom") or p.get("guid") or "sans nom"
    return f"Poteau {nom} (x = {_virgule(round(p['x'], 2))} m ; y = {_virgule(round(p['y'], 2))} m)"


def generer_poteau_depuis_position_reelle(
    poteau_ifc, voisins, charge_exploitation, hauteur_etage, nb_niveaux=1, usage_batiment=None,
    taux_travail_sol=None, hyp=None,
):
    """
    Phase B (import) -- équivalent de generer_poteau_sur_grille() mais
    sans grille régulière : la position et la charge du poteau sont
    calculées à partir de ses voisins RÉELLEMENT détectés dans le nuage
    de points, pas d'une portée fixe.

    poteau_ifc : un élément de extraire_poteaux() -- dict avec au moins
    "x", "y" (mètres) ; "guid"/"nom" transmis dans le résultat s'ils
    existent.
    voisins : le nuage de points complet dans lequel chercher les
    voisins de poteau_ifc (typiquement tous les poteaux du même niveau,
    poteau_ifc inclus -- il est exclu automatiquement de la recherche).

    Réutilise calculer_surface_influence() (Module 1) exactement comme
    generer_poteau_sur_grille(), en lui passant les 4 distances réelles
    aux voisins directs (0 si aucun voisin dans une direction : bord de
    la trame réelle) au lieu de portee_x/y fixes.

    Retour : même forme que generer_poteau_sur_grille(), plus "guid",
    "nom" (traçabilité vers le poteau IFC d'origine) et
    "portees_detectees" (diagnostic : les 4 distances utilisées).
    """
    v_gauche, portee_gauche = _trouver_voisin_direct(poteau_ifc, voisins, axe="x", sens=-1)
    v_droite, portee_droite = _trouver_voisin_direct(poteau_ifc, voisins, axe="x", sens=+1)
    v_avant, portee_avant = _trouver_voisin_direct(poteau_ifc, voisins, axe="y", sens=-1)
    v_arriere, portee_arriere = _trouver_voisin_direct(poteau_ifc, voisins, axe="y", sens=+1)

    surface = calculer_surface_influence(portee_gauche, portee_droite, portee_avant, portee_arriere)
    if surface <= 0:
        # Surface nulle = aucun voisin détecté sur tout un axe (poteau
        # isolé, en bout de ligne sans direction perpendiculaire, ou mal
        # aligné/hors tolérance) -- pas une trame 2D exploitable pour ce
        # poteau. On lève une erreur explicite plutôt que de laisser
        # dimensionner_poteau échouer plus loin avec une charge nulle.
        raise ValueError(
            f"Impossible de calculer la surface d'influence du poteau "
            f"{poteau_ifc.get('nom') or poteau_ifc.get('guid') or '(sans nom)'} : "
            f"aucun voisin direct détecté sur un axe entier (portées : "
            f"gauche={portee_gauche}, droite={portee_droite}, avant={portee_avant}, "
            f"arriere={portee_arriere}). Vérifiez le nuage de points -- poteau "
            f"isolé, en bout de ligne, ou hors tolérance d'alignement "
            f"({TOLERANCE_ALIGNEMENT_M} m)."
        )

    hyp = _hyp(hyp, charge_exploitation, taux_travail_sol)
    portees = {"gauche": portee_gauche, "droite": portee_droite, "avant": portee_avant, "arriere": portee_arriere}
    hors_domaine = {cote: l for cote, l in portees.items() if l and not (PORTEE_MIN_POUTRE_M < l <= PORTEE_MAX_M)}
    if hors_domaine:
        # Poteaux superposés (entraxe ≤ 20 cm) ou portée > 15 m : le poteau
        # n'est PAS calculé, et on dit exactement pourquoi -- jamais de
        # charge inventée ni perdue en silence. Les poutres courtes
        # (20 cm à 1 m) sont, elles, calculées (section 20 × 25 cm).
        raise ValueError(
            f"{_nom_poteau(poteau_ifc)} non calculé : portée "
            + ", ".join(f"{_virgule(round(l, 2))} m ({cote})" for cote, l in hors_domaine.items())
            + f" hors du domaine du moteur (plus de {_virgule(PORTEE_MIN_POUTRE_M)} m et au plus "
            f"{_virgule(PORTEE_MAX_M)} m). Sa charge, sa semelle et ses poutres ne sont pas comptées : vérifiez "
            "le plan (poteaux doublés ?) ou dimensionnez ces éléments à la main."
        )
    pos = (poteau_ifc["x"], poteau_ifc["y"])
    segments = {cote: cle_segment(pos, (v["x"], v["y"])) if v is not None else None
                for cote, v in (("gauche", v_gauche), ("droite", v_droite), ("avant", v_avant),
                                ("arriere", v_arriere))}
    noeud = _calcul_noeud(portees, hyp, nb_niveaux, usage_batiment, hauteur_etage, segments=segments)
    return {
        "guid": poteau_ifc.get("guid"),
        "nom": poteau_ifc.get("nom"),
        "x": poteau_ifc["x"],
        "y": poteau_ifc["y"],
        **noeud,
        "portees_detectees": portees,
    }


def calculer_longueur_chainage(nb_travees_x, nb_travees_y, portee_x, portee_y):
    """
    Longueur totale de chaînage bas = tous les segments reliant deux
    poteaux directement adjacents de la grille (périmètre + alignements
    internes).

    Vérifiée à la main sur trame 2x1, 5,0x4,0 m -> 32 ml.
    """
    if nb_travees_x < 1 or nb_travees_y < 1:
        raise ValueError("Une trame nécessite au moins 1 travée dans chaque direction.")
    longueur_x = nb_travees_x * portee_x * (nb_travees_y + 1)
    longueur_y = nb_travees_y * portee_y * (nb_travees_x + 1)
    return longueur_x + longueur_y


def generer_poutre_sur_grille(portee, largeur_influence, charge_exploitation, hyp=None, nb_niveaux=None,
                              hauteur_etage=None, cle=None, rive=None):
    """
    Poutre reliant deux poteaux adjacents de la grille.

    largeur_influence (m) : largeur de plancher reprise -- portée
    perpendiculaire pour une poutre intérieure (demi-travée de chaque
    côté), moitié pour une poutre de rive.

        g_lin = g × largeur (+ mur porté) (+ b × h × γ si poids propre inclus)   [kN/m]
        mur porté = p_mur × (h_étage − h_poutre) × (1 − baies), seulement
        pour une poutre de plancher (un étage au-dessus) dont le tronçon
        `cle` porte un mur d'étage sur le plan des murs.
        q_lin = q × largeur                                         [kN/m]
        pu = 1,35 g_lin + 1,5 q_lin ; pser = g_lin + q_lin
        γ = pu / pser  (transmis au calcul de la poutre : plus d'estimation 1,45)
    """
    hyp = _hyp(hyp, charge_exploitation, None)
    pp = poids_propre_poutre_kn_m(portee, hyp) if hyp.inclure_poids_propre_ossature else 0.0
    # Mêmes poutres à tous les niveaux : on retient le niveau le plus chargé.
    # Poutre de plancher (s'il y a un étage au-dessus) : G plancher + mur
    # de l'étage posé dessus. Poutre du dernier niveau : G de toiture
    # (= G plancher pour une dalle), aucun mur au-dessus.
    niveaux = nb_niveaux or 1
    candidats = [("toiture", hyp.g_toiture_effective, 0.0)]
    if niveaux >= 2:
        q_mur = charge_mur_kn_m(portee, hyp, hauteur_etage)[0] if hyp.mur_sur(cle, "etages") else 0.0
        candidats.append(("plancher", hyp.g_plancher_kn_m2, q_mur))
    _, g_surf, q_mur = max(candidats, key=lambda c: c[1] * largeur_influence + c[2])
    g_lin = g_surf * largeur_influence + q_mur + pp
    # Mêmes poutres à tous les niveaux (règle validée) : on retient la
    # charge d'exploitation du niveau le plus chargé (étage ou toiture).
    q_poutre = max(hyp.q_kn_m2, hyp.q_toiture_effective)
    q_lin = q_poutre * largeur_influence
    pu = hyp.elu(g_lin, q_lin)
    pser = hyp.els(g_lin, q_lin)
    resultat_poutre = dimensionner_poutre(portee=portee, charge_lineaire=pu, gamma_elu_els=pu / pser)
    trace = [
        _etape("Charge permanente linéique",
               "g_lin = g × largeur" + (" + p_mur × (h_étage − h)" if q_mur else "") + (" + b·h·γ" if pp else ""),
               f"{g_surf} × {round(largeur_influence, 3)}" + (f" + {round(q_mur, 2)}" if q_mur else "")
               + (f" + {round(pp, 2)}" if pp else ""),
               round(g_lin, 2), "kN/m"),
        _etape("Charge d'exploitation linéique", "q_lin = q × largeur (niveau le plus chargé)",
               f"{q_poutre} × {round(largeur_influence, 3)}", round(q_lin, 2), "kN/m"),
        _etape("Charge ELU", f"pu = {hyp.gamma_g_elu} g + {hyp.gamma_q_elu} q",
               f"{hyp.gamma_g_elu} × {round(g_lin, 2)} + {hyp.gamma_q_elu} × {round(q_lin, 2)}", round(pu, 2), "kN/m"),
        _etape("Charge ELS", "pser = g + q", f"{round(g_lin, 2)} + {round(q_lin, 2)}", round(pser, 2), "kN/m"),
        _etape("Hauteur", "h = max(L / 8 ; 25 cm) (isostatique, prudent ; 25 cm : section minimale)",
               f"max({portee} / 8 ; 0,25)", resultat_poutre["hauteur_cm"], "cm"),
        _etape("Moment ELU", "Mu = pu L² / 8", f"{round(pu, 2)} × {portee}² / 8",
               resultat_poutre["moment_flechissant_knm"], "kN·m"),
        _etape("Moment réduit", "µ = Mu / (b d² fbu), d = 0,9 h, fbu = 0,85 fc28 / γb",
               f"{_v(resultat_poutre['moment_flechissant_knm'] / 1000, 5)} MN·m / "
               f"({_v(resultat_poutre['largeur_cm'] / 100)} × {_v(resultat_poutre['hauteur_utile_cm'] / 100)}² "
               f"× {_v(resultat_poutre['fbu_mpa'])} MPa)",
               resultat_poutre["moment_reduit"], "—"),
        _etape("Acier tendu", "α = 1,25 (1 − √(1 − 2µ)) ; z = d (1 − 0,4 α) ; As = Mu / (z fsu), fsu = fe / γs",
               f"α = {_v(resultat_poutre['alpha_u'], 4)} ; z = {_v(resultat_poutre['bras_levier_cm'])} cm ; "
               f"As = {_v(resultat_poutre['moment_flechissant_knm'] / 1000, 5)} / "
               f"({_v(resultat_poutre['bras_levier_cm'] / 100, 4)} × {_v(resultat_poutre['fsu_mpa'])}) × 10⁴",
               resultat_poutre["section_acier_theorique_cm2"], "cm²"),
        _etape("Effort tranchant", "Vu = pu L / 2 ; τu = Vu / (b d) ≤ min(0,2 fc28 / γb ; 5 MPa)",
               f"Vu = {resultat_poutre['effort_tranchant_kn']} kN ; τu = {resultat_poutre['contrainte_cisaillement_mpa']} MPa",
               resultat_poutre["contrainte_cisaillement_limite_mpa"], "MPa (limite)"),
    ]
    messages = hyp.messages()
    if not resultat_poutre["cisaillement_verifie"]:
        messages = messages + [
            f"ALERTE : poutre de {_virgule(portee)} m -- contrainte de cisaillement "
            f"{_virgule(resultat_poutre['contrainte_cisaillement_mpa'])} MPa supérieure à la limite "
            f"{_virgule(resultat_poutre['contrainte_cisaillement_limite_mpa'])} MPa : section à agrandir."
        ]
    resultat_poutre = {**resultat_poutre, "trace": trace, "hypotheses_calcul": hyp.vers_dict(),
                       "charge_elu_kn_m": round(pu, 2), "charge_els_kn_m": round(pser, 2),
                       # Plan des murs : identifiant du tronçon, façade ou non,
                       # murs placés (affichés, jamais déduits ici).
                       "cle_segment": cle, "rive": rive,
                       "mur_etage": hyp.mur_sur(cle, "etages"), "mur_rdc": hyp.mur_sur(cle, "rdc")}
    return {
        "charge_lineaire_kn_m": pu,
        "charge_lineaire_service_kn_m": pser,
        "resultat_poutre": resultat_poutre,
        "hypotheses": messages,
    }


def generer_poutre_depuis_positions_reelles(poteau_a, poteau_b, axe, voisins, charge_exploitation, hyp=None,
                                            nb_niveaux=None, hauteur_etage=None):
    """
    Phase B (import) -- une poutre entre deux poteaux RÉELLEMENT
    adjacents (au lieu d'une boucle i, i+1 sur une grille). `axe`
    ("x" ou "y") précise la direction du tronçon ; `portee` est déduite
    de la distance réelle entre poteau_a et poteau_b.

    Largeur d'influence : approximée par la demi-somme des portées
    perpendiculaires détectées à CHAQUE extrémité (chacune divisée par
    2 comme pour une poutre "intérieure" -- voir generer_poutre_sur_grille),
    moyennée entre les deux poteaux. Une extrémité en rive (aucun voisin
    perpendiculaire d'un côté) réduit naturellement sa moitié à 0, comme
    calculer_surface_influence() le fait déjà pour les poteaux de bord.
    C'est une approximation tant qu'une reconstruction 2D complète des
    mailles de dalle n'est pas faite -- à vérifier si les poteaux ne
    sont pas répartis de façon à peu près régulière autour de la poutre.

    Retour : même forme que generer_poutre_sur_grille(), plus
    "poteau_origine_guid", "poteau_destination_guid", "axe" et
    "portee_m" (traçabilité et diagnostic).
    """
    axe_perp = "y" if axe == "x" else "x"
    portee = abs(poteau_b[axe] - poteau_a[axe])

    _, perp_a_pos = _trouver_voisin_direct(poteau_a, voisins, axe=axe_perp, sens=+1)
    _, perp_a_neg = _trouver_voisin_direct(poteau_a, voisins, axe=axe_perp, sens=-1)
    _, perp_b_pos = _trouver_voisin_direct(poteau_b, voisins, axe=axe_perp, sens=+1)
    _, perp_b_neg = _trouver_voisin_direct(poteau_b, voisins, axe=axe_perp, sens=-1)

    largeur_influence = (
        ((perp_a_pos + perp_a_neg) / 2) + ((perp_b_pos + perp_b_neg) / 2)
    ) / 2
    # Poutre de façade : aucun poteau d'un même côté aux deux extrémités.
    rive = (not perp_a_pos and not perp_b_pos) or (not perp_a_neg and not perp_b_neg)

    if largeur_influence <= 0:
        # Aucun poteau perpendiculaire détecté à AUCUNE des deux
        # extrémités (segment en bord de trame réelle sans dalle
        # adjacente d'un côté ou de l'autre -- ex. aile en L, poteau
        # isolé) : pas de largeur de dalle à reprendre, donc pas de
        # charge linéaire calculable pour cette poutre. Erreur
        # explicite plutôt que de laisser dimensionner_poutre échouer
        # plus loin avec une charge nulle -- l'appelant (Phase B) doit
        # l'attraper et ignorer ce segment (voir generer_poteau_depuis_
        # position_reelle() pour le même principe côté poteaux).
        raise ValueError(
            f"Impossible de calculer la largeur d'influence de la poutre "
            f"{poteau_a.get('guid', '?')}->{poteau_b.get('guid', '?')} : "
            f"aucun poteau perpendiculaire détecté à une extrémité ou "
            f"l'autre du segment (axe {axe})."
        )

    resultat = generer_poutre_sur_grille(
        portee=portee, largeur_influence=largeur_influence, charge_exploitation=charge_exploitation, hyp=hyp,
        nb_niveaux=nb_niveaux, hauteur_etage=hauteur_etage,
        cle=cle_segment((poteau_a["x"], poteau_a["y"]), (poteau_b["x"], poteau_b["y"])), rive=rive,
    )
    resultat["poteau_origine_guid"] = poteau_a.get("guid")
    resultat["poteau_destination_guid"] = poteau_b.get("guid")
    resultat["axe"] = axe
    resultat["portee_m"] = portee
    return resultat


def troncons_adjacents(voisins):
    """Tronçons de poutre entre poteaux directement voisins (géométrie
    seule, sans calcul) : [(cle_segment, (xa, ya), (xb, yb))], chaque
    tronçon une seule fois -- mêmes paires que detecter_poutres_adjacentes()."""
    troncons = []
    for poteau in voisins:
        for axe in ("x", "y"):
            voisin, _ = _trouver_voisin_direct(poteau, voisins, axe=axe, sens=+1)
            if voisin is not None:
                a, b = (poteau["x"], poteau["y"]), (voisin["x"], voisin["y"])
                troncons.append((cle_segment(a, b), a, b))
    return troncons


def detecter_poutres_adjacentes(voisins, charge_exploitation, hyp=None, nb_niveaux=None, hauteur_etage=None,
                                segments_ignores=None):
    """
    Phase B (import) -- génère une poutre par paire de poteaux
    directement adjacents dans le nuage de points détecté, sans passer
    par une grille i, i+1 régulière.

    Pour chaque poteau, on ne regarde que ses voisins directs dans le
    sens +x et +y : le voisin +x d'un poteau est le voisin -x de ce
    voisin, donc chaque segment du nuage de points n'est généré qu'une
    seule fois (pas de doublon).

    Un segment dont la largeur d'influence est nulle (poteau en bord de
    trame réelle sans dalle perpendiculaire d'un côté ou de l'autre --
    aile en L, géométrie irrégulière) est ignoré plutôt que de faire
    échouer tout l'import : voir generer_poutre_depuis_positions_reelles().

    Retour : liste de résultats de generer_poutre_depuis_positions_reelles(),
    un par segment détecté et exploitable. Chaque segment écarté est
    décrit (raison comprise) dans `segments_ignores` si une liste est
    fournie : l'appelant DOIT l'afficher.
    """
    poutres = []
    for poteau in voisins:
        for axe in ("x", "y"):
            voisin, _ = _trouver_voisin_direct(poteau, voisins, axe=axe, sens=+1)
            if voisin is None:
                continue
            try:
                poutres.append(
                    generer_poutre_depuis_positions_reelles(poteau, voisin, axe, voisins, charge_exploitation, hyp=hyp,
                                                            nb_niveaux=nb_niveaux, hauteur_etage=hauteur_etage)
                )
            except ValueError as exc:
                if segments_ignores is not None:
                    segments_ignores.append(
                        f"Poutre entre {_nom_poteau(poteau)} et {_nom_poteau(voisin)} non calculée : {exc}")
    return poutres