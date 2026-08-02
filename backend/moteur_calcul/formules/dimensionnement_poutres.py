"""
Dimensionnement des poutres.
Signature figée -- corps à remplir avec la formule du technicien BTP.
"""

from ..constantes import RESISTANCE_BETON_DEFAUT, LIMITE_ELASTIQUE_ACIER
from ..validators import valider_portee, EntreeInvalide


def dimensionner_poutre(portee, charge_lineaire, resistance_beton=None):
    """
    Propose une section de poutre à partir de sa portée et de la charge
    linéaire qu'elle reprend.

    Paramètres
    ----------
    portee : float
        Portée de la poutre, en mètres.
    charge_lineaire : float
        Charge linéaire répartie sur la poutre, en kN/m.
    resistance_beton : float, optionnel

    Retour
    ------
    dict
        {
            "largeur_cm": float,
            "hauteur_cm": float,
            "section_acier_theorique_cm2": float,
        }

    TODO (technicien BTP) : confirmer si on applique la règle empirique
    hauteur ≈ portee / 10 comme pré-dimensionnement initial avant calcul
    précis, ou si on part directement sur la formule complète.
    """
    valider_portee(portee)
    if charge_lineaire is None or charge_lineaire <= 0:
        raise EntreeInvalide("La charge linéaire doit être positive.")

    resistance = resistance_beton or RESISTANCE_BETON_DEFAUT
    if resistance is None or LIMITE_ELASTIQUE_ACIER is None:
        raise NotImplementedError(
            "RESISTANCE_BETON_DEFAUT / LIMITE_ELASTIQUE_ACIER non définis dans constantes.py"
        )

    # TODO : formule réelle à injecter
    raise NotImplementedError("Formule à injecter -- en attente du technicien BTP")