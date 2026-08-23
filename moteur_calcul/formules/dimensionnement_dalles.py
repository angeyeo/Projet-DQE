"""
Pré-dimensionnement des dalles -- BAEL 91 mod.99.

Formules du document technicien, section 3.3 :
    Dalle portant dans un sens :   h ~= portee / 25 a 30
    Dalle portant dans deux sens : h ~= portee / 35 a 40
    Epaisseur minimale courante en batiment residentiel : 12 a 16 cm
"""

from ..constantes import (
    RATIO_EPAISSEUR_DALLE_1_SENS,
    RATIO_EPAISSEUR_DALLE_2_SENS,
    EPAISSEUR_DALLE_MIN_CM,
)
from ..validators import valider_portee


def predimensionner_dalle(portee, portant_deux_sens=False):
    """
    Pré-dimensionnement rapide de l'épaisseur d'une dalle.

    Paramètres
    ----------
    portee : float
        Portée de la dalle (la plus petite des deux si portant dans
        les deux sens), en mètres.
    portant_deux_sens : bool
        True si la dalle porte dans les deux sens (dalle sur 4 appuis
        avec un rapport de portées proche de 1), False si elle porte
        dans un seul sens (cas courant, poutres parallèles rapprochées).

    Retour
    ------
    dict : {
        "epaisseur_cm": float,      # retenue, avec le minimum constructif appliqué
        "epaisseur_theorique_cm": float,  # avant application du minimum
        "portant_deux_sens": bool,
    }

    Note : ne calcule pas le ferraillage de la dalle (hors scope du
    pré-dimensionnement rapide du MVP).
    """
    valider_portee(portee)

    ratio_min, ratio_max = (
        RATIO_EPAISSEUR_DALLE_2_SENS if portant_deux_sens else RATIO_EPAISSEUR_DALLE_1_SENS
    )
    # Ratio le plus défavorable (dénominateur le plus petit = dalle la
    # plus épaisse) par prudence pour un pré-dimensionnement.
    epaisseur_theorique_m = portee / ratio_min

    epaisseur_retenue_cm = max(epaisseur_theorique_m * 100, EPAISSEUR_DALLE_MIN_CM)
    # Arrondi au cm supérieur, pratique constructive courante
    epaisseur_retenue_cm = round(epaisseur_retenue_cm + 0.999999) if epaisseur_retenue_cm % 1 else epaisseur_retenue_cm

    return {
        "epaisseur_cm": epaisseur_retenue_cm,
        "epaisseur_theorique_cm": round(epaisseur_theorique_m * 100, 1),
        "portant_deux_sens": portant_deux_sens,
    }