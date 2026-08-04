"""
Dimensionnement des poteaux (compression centrée) -- BAEL 91 mod.99.

Formule simplifiée de pré-dimensionnement (document technicien, section
3.1) : utilisée pour un premier calibrage rapide, avant vérification
détaillée (flambement, ferraillage précis) qui reste hors scope du MVP.
"""

import math

from ..constantes import (
    RESISTANCE_BETON_DEFAUT,
    LIMITE_ELASTIQUE_ACIER,
    COEFFICIENT_SECURITE_POTEAU_RAPIDE,
)
from ..validators import EntreeInvalide


def dimensionner_poteau(charge_calculee, hauteur_poteau, resistance_beton=None):
    """
    Pré-dimensionnement rapide d'un poteau carré en compression centrée.

    Formule (document technicien, section 3.1, pré-dimensionnement rapide) :
        Section (cm²) = Nu (kN) / (0,7 x fc28 en kN/cm²) x coefficient_securite

    fc28 est converti de MPa en kN/cm² (1 MPa = 0,1 kN/cm²).

    Paramètres
    ----------
    charge_calculee : float
        Charge ELU cumulée reprise par le poteau, en kN.
    hauteur_poteau : float
        Hauteur libre du poteau, en mètres (conservée pour une future
        vérification de flambement -- non calculée ici).
    resistance_beton : float, optionnel
        fc28 en MPa. Par défaut : constante du projet (25 MPa).

    Retour
    ------
    dict : {
        "cote_cm": float,          # côté du poteau carré, arrondi au cm supérieur
        "section_cm2": float,      # section réellement retenue
        "section_theorique_cm2": float,  # section brute issue de la formule
    }

    Note : ne couvre pas la vérification du flambement (élancement) ni
    le calcul détaillé du ferraillage -- ce sont des vérifications
    complémentaires mentionnées dans le document (formule BAEL complète,
    section 3.1) mais hors scope du pré-dimensionnement rapide du MVP.
    """
    if charge_calculee is None or charge_calculee <= 0:
        raise EntreeInvalide("La charge calculée doit être positive.")
    if hauteur_poteau is None or hauteur_poteau <= 0:
        raise EntreeInvalide("La hauteur du poteau doit être positive.")

    fc28 = resistance_beton or RESISTANCE_BETON_DEFAUT
    fc28_kn_cm2 = fc28 * 0.1  # MPa -> kN/cm²

    section_theorique_cm2 = (
        charge_calculee / (0.7 * fc28_kn_cm2) * COEFFICIENT_SECURITE_POTEAU_RAPIDE
    )

    # Poteau carré : côté = racine carrée de la section, arrondi au cm
    # supérieur, avec un minimum constructif courant de 20 cm.
    cote_theorique = math.sqrt(section_theorique_cm2)
    cote_retenu = max(20, math.ceil(cote_theorique / 5) * 5)  # arrondi au multiple de 5 cm

    return {
        "cote_cm": cote_retenu,
        "section_cm2": cote_retenu ** 2,
        "section_theorique_cm2": round(section_theorique_cm2, 1),
    }