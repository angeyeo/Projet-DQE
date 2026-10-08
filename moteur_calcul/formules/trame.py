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
from ..constantes import RESISTANCE_BETON_DEFAUT
from ..unites import cm_vers_m
from .descente_charges import calculer_surface_influence, cumuler_charges_exploitation_degressives
from .dimensionnement_poteaux import dimensionner_poteau
from .dimensionnement_poutres import dimensionner_poutre, predimensionner_hauteur_poutre
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


def poids_propre_poutre_kn_m(portee, hyp: HypothesesCalcul):
    """Poids propre linéique d'une poutre de la trame : b × h(portée) × γ_béton (kN/m),
    avec la MÊME hauteur que celle retenue par dimensionner_poutre()."""
    if not portee:
        return 0.0
    return LARGEUR_POUTRE_M * predimensionner_hauteur_poutre(portee, isostatique=True) * hyp.poids_volumique_beton_kn_m3


def _calcul_noeud(portees, hyp: HypothesesCalcul, nb_niveaux, usage_batiment, hauteur_etage):
    """Descente de charges d'UN poteau (tous niveaux), puis poteau et semelle.

    portees : dict gauche/droite/avant/arriere (m), 0 en rive.
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
    if nb_niveaux > 1:
        trace.append(_etape("Q / étage", "Q = S × q", f"{round(surface, 3)} × {hyp.q_kn_m2}", round(q_niveau, 2), "kN"))
    trace.append(_etape("Q toiture", "Q0 = S × q_toiture", f"{round(surface, 3)} × {hyp.q_toiture_effective}",
                        round(q_toiture, 2), "kN"))

    pp_poutres = 0.0
    if hyp.inclure_poids_propre_ossature:
        # Moitié de chaque poutre aboutissant au poteau.
        pp_poutres = sum((l / 2) * poids_propre_poutre_kn_m(l, hyp) for l in (pg, pd, pa, pr) if l)
        trace.append(_etape(
            "Poids propre poutres / niveau", "Σ (l/2) × b × h(l) × γ, h = l/8",
            " + ".join(f"({l}/2)×{LARGEUR_POUTRE_M}×{round(l / 8, 3)}×{hyp.poids_volumique_beton_kn_m3}"
                       for l in (pg, pd, pa, pr) if l) or "0",
            round(pp_poutres, 2), "kN",
        ))

    q_deg = cumuler_charges_exploitation_degressives(
        charge_toiture_kn=q_toiture, charges_etages_kn=[q_niveau] * (nb_niveaux - 1), usage_batiment=usage_batiment,
    )
    q_cumul = q_deg["cumuls_kn"][-1]
    coef = q_deg["coefficients"][-1]

    cote_cm = COTE_POTEAU_INITIAL_CM
    for _ in range(MAX_ITERATIONS_POIDS_PROPRE):
        pp_poteau = (cm_vers_m(cote_cm) ** 2 * hauteur_etage * hyp.poids_volumique_beton_kn_m3
                     if hyp.inclure_poids_propre_ossature else 0.0)
        g_cumul = nb_niveaux * (g_plancher + pp_poutres + pp_poteau)
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
    trace.append(_etape("G cumulée", "G = n × (G planchers + poids propres)",
                        f"{nb_niveaux} × ({round(g_plancher, 2)} + {round(pp_poutres, 2)} + {round(pp_poteau, 2)})",
                        round(g_cumul, 2), "kN"))
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
    trace_poteau = trace + [
        _etape("Section du poteau", "B ≥ 1,3 Nu / (0,7 fc28), arrondi 5 cm, min 20 cm",
               f"Nu = {round(nu, 2)} kN, fc28 = {RESISTANCE_BETON_DEFAUT} MPa", resultat_poteau["cote_cm"], "cm"),
        _etape("Flambement", "λ = lf / i, i = a/√12 ; α = 0,85/(1+0,2(λ/35)²) si λ ≤ 50",
               f"λ = {resultat_poteau['elancement']}", resultat_poteau["coefficient_alpha"], "—"),
        _etape("Acier longitudinal", "A = max(A_min ; (Nu/α − Br fc28/(0,9 γb)) γs/fe)",
               "Br = (a − 2)² cm²", resultat_poteau["section_acier_retenue_cm2"], "cm²"),
    ]

    resultat_semelle = dimensionner_semelle(
        charge_poteau=nu, taux_travail_sol=hyp.contrainte_sol_kn_m2, cote_poteau_cm=resultat_poteau["cote_cm"],
        charge_service=ns, methode=hyp.methode_semelles, inclure_poids_propre=hyp.inclure_poids_propre_ossature,
    )
    n_dim = resultat_semelle["charge_dimensionnement_kn"]
    trace_semelle = trace + [
        _etape("Côté théorique", f"A = √(N{'u' if hyp.methode_semelles == 'ELU' else 's'} / σsol)",
               f"√({n_dim} / {resultat_semelle['contrainte_sol_kn_m2']})", resultat_semelle["cote_theorique_cm"], "cm"),
        _etape("Côté retenu", "arrondi 5 cm" + (" + poids propre" if hyp.inclure_poids_propre_ossature else ""),
               f"pression sol {resultat_semelle['pression_sol_kn_m2']} ≤ {resultat_semelle['contrainte_sol_kn_m2']} kN/m²",
               resultat_semelle["cote_cm"], "cm"),
        _etape("Hauteur", "d ≥ (A − b)/4 ; h = arrondi5(d + 5), h ≥ 20",
               f"({resultat_semelle['cote_cm']} − {resultat_poteau['cote_cm']})/4", resultat_semelle["hauteur_cm"], "cm"),
        _etape("Acier / direction", "As = Nu (A − b) / (8 d fsu)",
               f"Nu = {round(nu, 2)} kN, d = {resultat_semelle['hauteur_utile_cm']} cm",
               resultat_semelle["section_acier_par_direction_cm2"], "cm²"),
    ]
    resultat_poteau = {**resultat_poteau, "trace": trace_poteau, "hypotheses_calcul": hyp.vers_dict(),
                       "charge_elu_kn": round(nu, 2), "charge_els_kn": round(ns, 2)}
    resultat_semelle = {**resultat_semelle, "trace": trace_semelle, "hypotheses_calcul": hyp.vers_dict(),
                        "charge_elu_kn": round(nu, 2), "charge_els_kn": round(ns, 2)}
    return {
        "charge_elu_kn": nu,
        "charge_els_kn": ns,
        "resultat_poteau": resultat_poteau,
        "resultat_semelle": resultat_semelle,
        "nb_niveaux": nb_niveaux,
        "charge_g_cumulee_kn": round(g_cumul, 2),
        "charge_q_cumulee_kn": q_cumul,
        "coefficient_degression": coef,
        "degression_appliquee": q_deg["degression_appliquee"],
        "surface_influence_m2": round(surface, 4),
        "hypotheses": hyp.messages() + _messages_degression(q_deg, nb_niveaux),
    }


def _virgule(v):
    return f"{v:g}".replace(".", ",")


def _messages_degression(q_deg, nb_niveaux):
    if q_deg.get("au_dela_regle_validee"):
        return [
            f"HYPOTHÈSE : dégression au-delà du 4e étage ({nb_niveaux} niveaux) -- coefficients 0,6 puis 0,5 "
            f"(loi classique) non validés par le technicien BTP, qui a fixé 1 ; 0,9 ; 0,8 ; 0,7. À confirmer."
        ]
    return []


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
    noeud = _calcul_noeud(portees, hyp, nb_niveaux, usage_batiment, hauteur_etage)
    return {"x": i * portee_x, "y": j * portee_y, **noeud}


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
    _, portee_gauche = _trouver_voisin_direct(poteau_ifc, voisins, axe="x", sens=-1)
    _, portee_droite = _trouver_voisin_direct(poteau_ifc, voisins, axe="x", sens=+1)
    _, portee_avant = _trouver_voisin_direct(poteau_ifc, voisins, axe="y", sens=-1)
    _, portee_arriere = _trouver_voisin_direct(poteau_ifc, voisins, axe="y", sens=+1)

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
    noeud = _calcul_noeud(portees, hyp, nb_niveaux, usage_batiment, hauteur_etage)
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


def generer_poutre_sur_grille(portee, largeur_influence, charge_exploitation, hyp=None):
    """
    Poutre reliant deux poteaux adjacents de la grille.

    largeur_influence (m) : largeur de plancher reprise -- portée
    perpendiculaire pour une poutre intérieure (demi-travée de chaque
    côté), moitié pour une poutre de rive.

        g_lin = g × largeur (+ b × h × γ si poids propre inclus)   [kN/m]
        q_lin = q × largeur                                         [kN/m]
        pu = 1,35 g_lin + 1,5 q_lin ; pser = g_lin + q_lin
        γ = pu / pser  (transmis au calcul de la poutre : plus d'estimation 1,45)
    """
    hyp = _hyp(hyp, charge_exploitation, None)
    pp = poids_propre_poutre_kn_m(portee, hyp) if hyp.inclure_poids_propre_ossature else 0.0
    g_lin = hyp.g_plancher_kn_m2 * largeur_influence + pp
    # Mêmes poutres à tous les niveaux (règle validée) : on retient la
    # charge d'exploitation du niveau le plus chargé (étage ou toiture).
    q_poutre = max(hyp.q_kn_m2, hyp.q_toiture_effective)
    q_lin = q_poutre * largeur_influence
    pu = hyp.elu(g_lin, q_lin)
    pser = hyp.els(g_lin, q_lin)
    resultat_poutre = dimensionner_poutre(portee=portee, charge_lineaire=pu, gamma_elu_els=pu / pser)
    trace = [
        _etape("Charge permanente linéique", "g_lin = g × largeur" + (" + b·h·γ" if pp else ""),
               f"{hyp.g_plancher_kn_m2} × {round(largeur_influence, 3)}" + (f" + {round(pp, 2)}" if pp else ""),
               round(g_lin, 2), "kN/m"),
        _etape("Charge d'exploitation linéique", "q_lin = q × largeur (niveau le plus chargé)",
               f"{q_poutre} × {round(largeur_influence, 3)}", round(q_lin, 2), "kN/m"),
        _etape("Charge ELU", f"pu = {hyp.gamma_g_elu} g + {hyp.gamma_q_elu} q",
               f"{hyp.gamma_g_elu} × {round(g_lin, 2)} + {hyp.gamma_q_elu} × {round(q_lin, 2)}", round(pu, 2), "kN/m"),
        _etape("Charge ELS", "pser = g + q", f"{round(g_lin, 2)} + {round(q_lin, 2)}", round(pser, 2), "kN/m"),
        _etape("Hauteur", "h = L / 8 (isostatique, prudent)", f"{portee} / 8", resultat_poutre["hauteur_cm"], "cm"),
        _etape("Moment ELU", "Mu = pu L² / 8", f"{round(pu, 2)} × {portee}² / 8",
               resultat_poutre["moment_flechissant_knm"], "kN·m"),
        _etape("Moment réduit", "µ = Mu / (b d² fbu), d = 0,9 h", "", resultat_poutre["moment_reduit"], "—"),
        _etape("Acier tendu", "As = Mu / (z fsu), z = d(1 − 0,4α)", "",
               resultat_poutre["section_acier_theorique_cm2"], "cm²"),
    ]
    resultat_poutre = {**resultat_poutre, "trace": trace, "hypotheses_calcul": hyp.vers_dict(),
                       "charge_elu_kn_m": round(pu, 2), "charge_els_kn_m": round(pser, 2)}
    return {
        "charge_lineaire_kn_m": pu,
        "charge_lineaire_service_kn_m": pser,
        "resultat_poutre": resultat_poutre,
        "hypotheses": hyp.messages(),
    }


def generer_poutre_depuis_positions_reelles(poteau_a, poteau_b, axe, voisins, charge_exploitation, hyp=None):
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
    )
    resultat["poteau_origine_guid"] = poteau_a.get("guid")
    resultat["poteau_destination_guid"] = poteau_b.get("guid")
    resultat["axe"] = axe
    resultat["portee_m"] = portee
    return resultat


def detecter_poutres_adjacentes(voisins, charge_exploitation, hyp=None):
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
    un par segment détecté et exploitable.
    """
    poutres = []
    for poteau in voisins:
        for axe in ("x", "y"):
            voisin, _ = _trouver_voisin_direct(poteau, voisins, axe=axe, sens=+1)
            if voisin is None:
                continue
            try:
                poutres.append(
                    generer_poutre_depuis_positions_reelles(poteau, voisin, axe, voisins, charge_exploitation, hyp=hyp)
                )
            except ValueError:
                continue
    return poutres