"""
Dimensionnement des semelles (fondations superficielles) -- BAEL 91 mod.99.

Formules du document technicien, section 3.4.
"""

from ..constantes import CONTRAINTE_SOL_DEFAUT
from ..validators import EntreeInvalide


def dimensionner_semelle(charge_poteau, taux_travail_sol=None):
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

    Retour
    ------
    dict : {
        "cote_cm": float,           # côté de la semelle carrée, en cm
        "surface_m2": float,
        "hauteur_cm": float,
        "hypothese_sol": bool,      # True si le taux de travail par défaut a été utilisé
    }
    """
    if charge_poteau is None or charge_poteau <= 0:
        raise EntreeInvalide("La charge du poteau doit être positive.")

    hypothese_sol = taux_travail_sol is None
    contrainte_sol = taux_travail_sol or CONTRAINTE_SOL_DEFAUT

    surface_m2 = charge_poteau / contrainte_sol
    cote_m = surface_m2 ** 0.5

    # On suppose ici un côté de poteau de 25 cm par défaut pour la
    # méthode des bielles -- à affiner : idéalement, cette fonction
    # devrait recevoir le côté réel du poteau (issu de dimensionner_poteau)
    # plutôt qu'une valeur supposée.
    cote_poteau_m = 0.25
    hauteur_m = max((cote_m - cote_poteau_m) / 4, 0.20)  # 20 cm mini constructif

    return {
        "cote_cm": round(cote_m * 100, 1),
        "surface_m2": round(surface_m2, 2),
        "hauteur_cm": round(hauteur_m * 100, 1),
        "hypothese_sol": hypothese_sol,
    }