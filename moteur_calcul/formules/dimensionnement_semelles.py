"""
Dimensionnement des semelles (fondations superficielles) -- BAEL 91 mod.99.

Trois fonctions :
- dimensionner_semelle() : semelle ISOLÉE, version simple existante
  (charge ELU déjà cumulée, contrainte du sol) -- gardée pour
  compatibilité avec le reste de l'app (le modèle actuel ne stocke
  qu'une charge_calculee unique, pas G et Q séparés).
- dimensionner_semelle_affinee() : semelle ISOLÉE, version alignée sur
  le fichier de référence du technicien BTP ("Mon Métreur", feuille
  "Semelle isolée_section béton") -- prend G et Q séparément, la
  profondeur du bon sol, et les dimensions réelles (rectangulaires) du
  poteau ; soustrait le poids du sol au-dessus de la semelle, arrondit
  au multiple de 5cm, et vérifie la pression réelle avec le poids
  propre de la semelle inclus.
- dimensionner_semelle_filante() : semelle CONTINUE sous mur porteur
  (Phase 2, module 4) -- raisonne au mètre linéaire au lieu d'une
  charge ponctuelle, et calcule les aciers transversaux par la méthode
  des bielles.
"""

import math

from ..constantes import (
    CONTRAINTE_SOL_DEFAUT,
    POIDS_VOLUMIQUE_BETON,
    LIMITE_ELASTIQUE_ACIER,
    GAMMA_ACIER,
    LARGEUR_MIN_SEMELLE_FILANTE_CM,
    LARGEUR_MAX_SEMELLE_FILANTE_CM,
    HAUTEUR_MIN_SEMELLE_CM,
    ENROBAGE_SEMELLE_CM,
)
from ..validators import EntreeInvalide
from ..tables_acier import proposer_barres


def dimensionner_semelle(charge_poteau, taux_travail_sol=None, cote_poteau_cm=None):
    """
    Version simple (charge ELU déjà cumulée) -- voir dimensionner_semelle_affinee()
    pour une méthode plus précise si G et Q sont disponibles séparément.
    """
    if charge_poteau is None or charge_poteau <= 0:
        raise EntreeInvalide("La charge du poteau doit être positive.")

    hypothese_sol = taux_travail_sol is None
    contrainte_sol = taux_travail_sol or CONTRAINTE_SOL_DEFAUT

    surface_m2 = charge_poteau / contrainte_sol
    cote_m = surface_m2 ** 0.5

    hypothese_cote_poteau = cote_poteau_cm is None
    cote_poteau_m = (cote_poteau_cm / 100) if cote_poteau_cm else 0.25

    hauteur_m = max((cote_m - cote_poteau_m) / 4, 0.20)

    return {
        "cote_cm": round(cote_m * 100, 1),
        "surface_m2": round(surface_m2, 2),
        "hauteur_cm": round(hauteur_m * 100, 1),
        "hypothese_sol": hypothese_sol,
        "hypothese_cote_poteau": hypothese_cote_poteau,
    }


def dimensionner_semelle_affinee(
    charge_permanente_kn,
    charge_exploitation_kn,
    cote_poteau_b_cm,
    cote_poteau_a_cm,
    contrainte_sol_mpa,
    profondeur_bon_sol_cm=0,
):
    """
    Dimensionnement précis d'une semelle isolée, méthode du fichier
    technicien BTP.

    Étapes :
    1. Aire approchée : Sapp = (G+Q) / (σ-sol - poids_sol_au_dessus)
       (le poids volumique du sol au-dessus de la semelle -- 22 kN/m³
       -- est soustrait de la contrainte admissible, ce qui donne une
       aire légèrement plus grande que le calcul simple)
    2. Dimensions B (grand côté) et A (petit côté), au prorata des
       côtés réels du poteau (b, a), arrondies au multiple de 5 cm
    3. Hauteur utile d = (B-a)/4, hauteur h = arrondi(d, 5) + 5
    4. Vérification : la pression réelle (poids propre de la semelle
       inclus) doit rester inférieure à la contrainte admissible

    Paramètres
    ----------
    charge_permanente_kn, charge_exploitation_kn : float
        G et Q au niveau de la semelle (charges de service, pas ELU),
        en kN.
    cote_poteau_b_cm, cote_poteau_a_cm : float
        Grand et petit côté du poteau, en cm (b >= a). Pour un poteau
        carré, b = a.
    contrainte_sol_mpa : float
        Contrainte admissible du sol, en MPa (attention : pas en kN/m²
        ici, contrairement à dimensionner_semelle() -- 1 MPa = 1000 kN/m²).
    profondeur_bon_sol_cm : float, optionnel
        Profondeur du bon sol depuis la surface, en cm. Sert à
        soustraire le poids du sol au-dessus de la semelle (densité
        supposée 22 kN/m³, valeur du fichier technicien). Par défaut 0
        (pas de soustraction si non renseigné).

    Retour
    ------
    dict : {
        "grand_cote_cm": float,   # B
        "petit_cote_cm": float,   # A
        "hauteur_cm": float,      # h
        "poids_propre_semelle_kn": float,
        "pression_reelle_mpa": float,
        "condition_respectee": bool,   # pression_reelle < contrainte_sol_mpa
    }
    """
    if charge_permanente_kn is None or charge_exploitation_kn is None:
        raise EntreeInvalide("G et Q doivent être fournis.")
    if charge_permanente_kn < 0 or charge_exploitation_kn < 0:
        raise EntreeInvalide("G et Q doivent être positifs ou nuls.")
    if contrainte_sol_mpa is None or contrainte_sol_mpa <= 0:
        raise EntreeInvalide("La contrainte du sol doit être positive.")
    if cote_poteau_b_cm is None or cote_poteau_a_cm is None or cote_poteau_b_cm <= 0 or cote_poteau_a_cm <= 0:
        raise EntreeInvalide("Les côtés du poteau doivent être positifs.")

    charge_totale_n = (charge_permanente_kn + charge_exploitation_kn) * 1000  # kN -> N

    contrainte_effective_pa = contrainte_sol_mpa * 1e6 - 22000 * (profondeur_bon_sol_cm * 1e-2)
    if contrainte_effective_pa <= 0:
        raise EntreeInvalide(
            "La contrainte du sol nette (après déduction du poids du sol "
            "au-dessus) est négative ou nulle -- vérifier la profondeur "
            "renseignée."
        )

    sapp_cm2 = (1e4) * (charge_totale_n / contrainte_effective_pa)

    b_poteau, a_poteau = cote_poteau_b_cm, cote_poteau_a_cm

    grand_cote_cm = math.ceil(math.sqrt(sapp_cm2 * b_poteau / a_poteau) / 5) * 5
    petit_cote_cm = math.ceil(math.sqrt(sapp_cm2 * a_poteau / b_poteau) / 5) * 5

    hauteur_utile_cm = (grand_cote_cm - a_poteau) / 4
    hauteur_cm = math.ceil(hauteur_utile_cm / 5) * 5 + 5

    poids_propre_n = (grand_cote_cm * 1e-2) * (petit_cote_cm * 1e-2) * (hauteur_cm * 1e-2) * 25000
    pression_reelle_pa = (poids_propre_n + charge_totale_n) / ((grand_cote_cm * 1e-2) * (petit_cote_cm * 1e-2))
    pression_reelle_mpa = pression_reelle_pa / 1e6

    return {
        "grand_cote_cm": grand_cote_cm,
        "petit_cote_cm": petit_cote_cm,
        "hauteur_cm": hauteur_cm,
        "poids_propre_semelle_kn": round(poids_propre_n / 1000, 2),
        "pression_reelle_mpa": round(pression_reelle_mpa, 4),
        "condition_respectee": pression_reelle_mpa < contrainte_sol_mpa,
    }


def dimensionner_semelle_filante(
    charge_lineaire_kn_m,
    taux_travail_sol=None,
    epaisseur_mur_cm=None,
    charge_lineaire_service_kn_m=None,
    limite_elastique_acier=None,
):
    """
    Semelle filante (continue) sous mur porteur -- Phase 2, module 4.

    Contrairement à une semelle isolée, on raisonne sur UN MÈTRE
    LINÉAIRE de mur : la charge est linéaire (kN/ml) et la semelle n'a
    qu'une dimension à déterminer, sa largeur.

    Étapes :
    1. Largeur : B = charge_lineaire / contrainte_admissible du sol
       (une largeur en m donne directement une surface en m² par ml)
    2. Arrondi au multiple de 5 cm supérieur, minimum constructif
       (constantes.LARGEUR_MIN_SEMELLE_FILANTE_CM)
    3. Hauteur, méthode des bielles : d >= (B - b) / 4, puis
       h = d + enrobage, arrondie au multiple de 5 cm, minimum 20 cm
    4. Aciers transversaux (perpendiculaires au mur, ceux qui reprennent
       l'effort de traction des bielles) :
            As = Nu x (B - b) / (8 x d x fsu)      [par mètre linéaire]
    5. Aciers de répartition (parallèles au mur) : As / 4 (règle BAEL)
    6. Vérification finale de la pression réelle, poids propre de la
       semelle inclus

    Paramètres
    ----------
    charge_lineaire_kn_m : float
        Charge ELU descendant du mur, en kN par mètre linéaire.
    taux_travail_sol : float, optionnel
        Contrainte admissible du sol, en kN/m² (comme
        dimensionner_semelle(), PAS en MPa). Défaut : hypothèse projet.
    epaisseur_mur_cm : float, optionnel
        Épaisseur du mur porté, en cm. Défaut constructif : 20 cm,
        signalé par "hypothese_epaisseur_mur" dans le retour.
    charge_lineaire_service_kn_m : float, optionnel
        Charge de service (G + Q non pondérées), en kN/ml. C'est
        elle qui devrait servir à comparer à la contrainte admissible
        du sol. Si elle n'est pas fournie, on utilise la charge ELU --
        conservateur (semelle plus large que nécessaire), signalé par
        "hypothese_charge_service".
    limite_elastique_acier : float, optionnel
        fe en MPa.

    Retour
    ------
    dict : {
        "largeur_cm": float,
        "hauteur_cm": float,
        "hauteur_utile_cm": float,
        "surface_par_ml_m2": float,
        "acier_transversal_cm2_ml": float,
        "acier_repartition_cm2_ml": float,
        "barres_transversales": dict | None,   # + "espacement_cm"
        "poids_propre_kn_ml": float,
        "pression_reelle_kn_m2": float,
        "condition_respectee": bool,
        "hypothese_sol": bool,
        "hypothese_epaisseur_mur": bool,
        "hypothese_charge_service": bool,
    }
    """
    if charge_lineaire_kn_m is None or charge_lineaire_kn_m <= 0:
        raise EntreeInvalide("La charge linéaire du mur doit être positive.")
    if taux_travail_sol is not None and taux_travail_sol <= 0:
        raise EntreeInvalide("Le taux de travail du sol doit être positif.")
    if epaisseur_mur_cm is not None and epaisseur_mur_cm <= 0:
        raise EntreeInvalide("L'épaisseur du mur doit être positive.")
    if charge_lineaire_service_kn_m is not None and charge_lineaire_service_kn_m <= 0:
        raise EntreeInvalide("La charge de service doit être positive.")

    hypothese_sol = taux_travail_sol is None
    contrainte_sol = taux_travail_sol or CONTRAINTE_SOL_DEFAUT

    hypothese_epaisseur_mur = epaisseur_mur_cm is None
    epaisseur_mur_m = (epaisseur_mur_cm / 100) if epaisseur_mur_cm else 0.20

    hypothese_charge_service = charge_lineaire_service_kn_m is None
    charge_sol = charge_lineaire_service_kn_m or charge_lineaire_kn_m

    def geometrie(largeur_cm):
        """Hauteur, poids propre et pression réelle pour une largeur donnée."""
        largeur_m = largeur_cm / 100
        hauteur_utile_m = max((largeur_m - epaisseur_mur_m) / 4, 0.10)
        hauteur_cm = max(
            HAUTEUR_MIN_SEMELLE_CM,
            math.ceil((hauteur_utile_m * 100 + ENROBAGE_SEMELLE_CM) / 5) * 5,
        )
        poids_propre = largeur_m * (hauteur_cm / 100) * POIDS_VOLUMIQUE_BETON
        return hauteur_cm, poids_propre, (charge_sol + poids_propre) / largeur_m

    largeur_theorique_m = charge_sol / contrainte_sol
    largeur_cm = max(
        LARGEUR_MIN_SEMELLE_FILANTE_CM,
        math.ceil(largeur_theorique_m * 100 / 5) * 5,
    )

    # Le poids propre de la semelle s'ajoute à la charge du mur : la
    # largeur théorique seule ne suffit pas toujours, on élargit par
    # pas de 5 cm jusqu'à ce que la pression réelle repasse sous la
    # contrainte admissible.
    hauteur_cm, poids_propre_kn_ml, pression_reelle = geometrie(largeur_cm)
    while pression_reelle > contrainte_sol and largeur_cm < LARGEUR_MAX_SEMELLE_FILANTE_CM:
        largeur_cm += 5
        hauteur_cm, poids_propre_kn_ml, pression_reelle = geometrie(largeur_cm)

    if pression_reelle > contrainte_sol:
        raise NotImplementedError(
            f"Largeur nécessaire supérieure à "
            f"{LARGEUR_MAX_SEMELLE_FILANTE_CM} cm pour une charge de "
            f"{charge_sol:.0f} kN/ml sur un sol à {contrainte_sol:.0f} kN/m² : "
            f"une semelle filante n'est plus la bonne solution, il faut "
            f"étudier un radier général (ou des fondations profondes). "
            f"Ce moteur ne les traite pas."
        )

    largeur_m = largeur_cm / 100
    # la hauteur utile réelle découle de la hauteur retenue, pas l'inverse
    hauteur_utile_cm = hauteur_cm - ENROBAGE_SEMELLE_CM
    hauteur_utile_m = hauteur_utile_cm / 100

    fe = limite_elastique_acier or LIMITE_ELASTIQUE_ACIER
    fsu = fe / GAMMA_ACIER  # MPa

    nu_mn_ml = charge_lineaire_kn_m / 1000  # kN/ml -> MN/ml
    acier_transversal_m2 = (nu_mn_ml * (largeur_m - epaisseur_mur_m)) / (
        8 * hauteur_utile_m * fsu
    )
    acier_transversal_cm2 = acier_transversal_m2 * 10_000
    acier_repartition_cm2 = acier_transversal_cm2 / 4

    # Répartition sur 1 ml : 3 à 8 barres, soit un espacement de 33 à
    # 12,5 cm -- la plage constructive courante pour une semelle.
    barres = proposer_barres(
        acier_transversal_cm2,
        diametres_autorises=[8, 10, 12, 14, 16],
        nb_barres_min=3,
        nb_barres_max=8,
    )
    if barres:
        barres = {**barres, "espacement_cm": round(100 / barres["nombre_barres"], 1)}

    return {
        "largeur_cm": largeur_cm,
        "hauteur_cm": hauteur_cm,
        "hauteur_utile_cm": hauteur_utile_cm,
        "surface_par_ml_m2": round(largeur_m, 3),
        "acier_transversal_cm2_ml": round(acier_transversal_cm2, 2),
        "acier_repartition_cm2_ml": round(acier_repartition_cm2, 2),
        "barres_transversales": barres,
        "poids_propre_kn_ml": round(poids_propre_kn_ml, 2),
        "pression_reelle_kn_m2": round(pression_reelle, 1),
        "condition_respectee": pression_reelle <= contrainte_sol,
        "hypothese_sol": hypothese_sol,
        "hypothese_epaisseur_mur": hypothese_epaisseur_mur,
        "hypothese_charge_service": hypothese_charge_service,
    }