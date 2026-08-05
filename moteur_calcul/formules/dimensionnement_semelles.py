"""
Dimensionnement des semelles (fondations superficielles) -- BAEL 91 mod.99.

Formules du document technicien, section 3.4.
"""

from ..constantes import CONTRAINTE_SOL_DEFAUT
from ..validators import EntreeInvalide


def dimensionner_semelle(charge_poteau, taux_travail_sol=None, cote_poteau_cm=None):
    """
    Dimensionnement d'une semelle isolée carrée (document technicien,
    section 3.4).

    Surface (m²) = Charge poteau (kN) / Contrainte admissible du sol (kN/m²)
    Hauteur (méthode des bielles) : h >= (A - a) / 4
        A = côté de la semelle, a = côté du poteau

    Paramètres
    ----------
    charge_poteau : float
        Charge ELU transmise par le poteau, en kN.
    taux_travail_sol : float, optionnel
        Contrainte admissible du sol, en kN/m². Si non fourni, utilise
        la valeur par défaut du projet (180 kN/m² -- HYPOTHÈSE, à
        remplacer par une étude géotechnique réelle).
    cote_poteau_cm : float, optionnel
        Côté réel du poteau porté par cette semelle, en cm -- à
        transmettre depuis le résultat de dimensionner_poteau() pour
        une méthode des bielles correcte. Si non fourni, une valeur
        constructive courante de 25 cm est utilisée par défaut, avec
        un signalement explicite (voir "hypothese_cote_poteau" dans le
        retour) pour que l'ingénieur sache que ce n'est qu'une
        approximation à vérifier.

    Retour
    ------
    dict : {
        "cote_cm": float,
        "surface_m2": float,
        "hauteur_cm": float,
        "hypothese_sol": bool,
        "hypothese_cote_poteau": bool,
    }
    """
    if charge_poteau is None or charge_poteau <= 0:
        raise EntreeInvalide("La charge du poteau doit être positive.")

    hypothese_sol = taux_travail_sol is None
    contrainte_sol = taux_travail_sol or CONTRAINTE_SOL_DEFAUT

    surface_m2 = charge_poteau / contrainte_sol
    cote_m = surface_m2 ** 0.5

    hypothese_cote_poteau = cote_poteau_cm is None
    cote_poteau_m = (cote_poteau_cm / 100) if cote_poteau_cm else 0.25

    hauteur_m = max((cote_m - cote_poteau_m) / 4, 0.20)  # 20 cm mini constructif

    return {
        "cote_cm": round(cote_m * 100, 1),
        "surface_m2": round(surface_m2, 2),
        "hauteur_cm": round(hauteur_m * 100, 1),
        "hypothese_sol": hypothese_sol,
        "hypothese_cote_poteau": hypothese_cote_poteau,
    }