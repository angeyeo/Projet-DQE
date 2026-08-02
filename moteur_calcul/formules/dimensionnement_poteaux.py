"""
Dimensionnement des poteaux.
Signature figée -- corps à remplir avec la formule du technicien BTP.
"""

from ..constantes import RESISTANCE_BETON_DEFAUT, LIMITE_ELASTIQUE_ACIER
from ..validators import EntreeInvalide


def dimensionner_poteau(charge_calculee, hauteur_poteau, resistance_beton=None):
    """
    Propose une section de poteau à partir de la charge qu'il doit reprendre.

    Paramètres
    ----------
    charge_calculee : float
        Charge totale reprise par le poteau, en kN.
    hauteur_poteau : float
        Hauteur libre du poteau, en mètres (utile pour le calcul de
        flambement).
    resistance_beton : float, optionnel
        Résistance du béton en MPa. Si non fourni, utilise la valeur
        par défaut du projet.

    Retour
    ------
    dict
        {
            "largeur_cm": float,
            "profondeur_cm": float,
            "section_acier_theorique_cm2": float,
        }

    TODO (technicien BTP) : confirmer la méthode de dimensionnement
    (vérification du flambement incluse ou séparée ?).
    """
    if charge_calculee is None or charge_calculee <= 0:
        raise EntreeInvalide("La charge calculée doit être positive.")
    if hauteur_poteau is None or hauteur_poteau <= 0:
        raise EntreeInvalide("La hauteur du poteau doit être positive.")

    resistance = resistance_beton or RESISTANCE_BETON_DEFAUT
    if resistance is None or LIMITE_ELASTIQUE_ACIER is None:
        raise NotImplementedError(
            "RESISTANCE_BETON_DEFAUT / LIMITE_ELASTIQUE_ACIER non définis dans constantes.py"
        )

    # TODO : formule réelle à injecter (dimensionnement + vérification flambement)
    raise NotImplementedError("Formule à injecter -- en attente du technicien BTP")