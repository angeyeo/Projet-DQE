"""
Dimensionnement des semelles (fondations superficielles) -- BAEL 91 mod.99.

Deux fonctions :
- dimensionner_semelle() : version simple existante (charge ELU déjà
  cumulée, contrainte du sol) -- gardée pour compatibilité avec le
  reste de l'app (le modèle actuel ne stocke qu'une charge_calculee
  unique, pas G et Q séparés).
- dimensionner_semelle_affinee() : version alignée sur le fichier de
  référence du technicien BTP ("Mon Métreur", feuille "Semelle
  isolée_section béton") -- prend G et Q séparément, la profondeur du
  bon sol, et les dimensions réelles (rectangulaires) du poteau ;
  soustrait le poids du sol au-dessus de la semelle, arrondit au
  multiple de 5cm, et vérifie la pression réelle avec le poids propre
  de la semelle inclus.
"""

import math

from ..constantes import CONTRAINTE_SOL_DEFAUT
from ..validators import EntreeInvalide


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