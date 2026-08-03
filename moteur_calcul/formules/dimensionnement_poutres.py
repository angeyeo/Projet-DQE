"""
Dimensionnement des poutres (flexion simple) -- BAEL 91 mod.99.

Formules du document technicien, section 3.2 : pré-dimensionnement
rapide de la hauteur, puis calcul du moment réduit et de la section
d'acier pour le cas pivot A (section simplement armée -- cas courant
en bâtiment résidentiel).
"""

import math

from ..constantes import (
    RESISTANCE_BETON_DEFAUT,
    LIMITE_ELASTIQUE_ACIER,
    GAMMA_BETON,
    GAMMA_ACIER,
    MU_LIMITE_PIVOT_AB,
    RATIO_HAUTEUR_POUTRE_ISOSTATIQUE,
)
from ..validators import valider_portee, EntreeInvalide


def predimensionner_hauteur_poutre(portee, isostatique=True):
    """
    Pré-dimensionnement rapide de la hauteur (document technicien,
    section 3.2) :
        h ≈ portée / 10 à 12   (poutre continue)
        h ≈ portée / 8 à 10    (poutre isostatique)

    Retourne la hauteur en mètres, en prenant le ratio le plus
    défavorable (dénominateur le plus petit = poutre la plus haute)
    de la fourchette, par prudence pour un pré-dimensionnement.
    """
    valider_portee(portee)
    ratio_min, ratio_max = RATIO_HAUTEUR_POUTRE_ISOSTATIQUE if isostatique else (10, 12)
    return portee / ratio_min  # ratio_min -> hauteur la plus grande de la fourchette


def calculer_moment_flechissant(charge_lineaire, portee):
    """
    Moment fléchissant à mi-travée pour une poutre simplement appuyée
    sous charge uniformément répartie (document technicien, section 3.2) :
        Mu = charge_repartie x portee² / 8

    Paramètres
    ----------
    charge_lineaire : float
        Charge linéaire répartie (déjà pondérée ELU), en kN/m.
    portee : float
        Portée de la poutre, en mètres.

    Retour : moment fléchissant en kN.m
    """
    valider_portee(portee)
    if charge_lineaire is None or charge_lineaire <= 0:
        raise EntreeInvalide("La charge linéaire doit être positive.")
    return charge_lineaire * portee ** 2 / 8


def dimensionner_poutre(portee, charge_lineaire, largeur=0.20, resistance_beton=None):
    """
    Dimensionnement complet simplifié d'une poutre rectangulaire en
    flexion simple, méthode BAEL (document technicien, section 3.2).

    Étapes :
    1. Pré-dimensionnement de la hauteur (h ≈ portée/8 à 10)
    2. Calcul du moment fléchissant Mu
    3. Calcul du moment réduit µbu
    4. Vérification pivot A (µbu <= 0,186) -- sinon lever une erreur
       explicite (section doublement armée non gérée dans le MVP)
    5. Calcul de la section d'acier tendu

    Paramètres
    ----------
    portee : float
        En mètres.
    charge_lineaire : float
        Charge linéaire déjà pondérée ELU, en kN/m.
    largeur : float, optionnel
        Largeur de la poutre en mètres. Valeur constructive courante
        par défaut : 0,20 m (20 cm).
    resistance_beton : float, optionnel
        fc28 en MPa.

    Retour
    ------
    dict : {
        "hauteur_cm": float,
        "largeur_cm": float,
        "moment_flechissant_knm": float,
        "moment_reduit": float,
        "section_acier_theorique_cm2": float,
    }
    """
    hauteur = predimensionner_hauteur_poutre(portee, isostatique=True)
    hauteur_utile = 0.9 * hauteur  # d ≈ 0,9h, approximation courante

    moment_flechissant = calculer_moment_flechissant(charge_lineaire, portee)
    moment_flechissant_mn = moment_flechissant / 1000  # kN.m -> MN.m

    fc28 = resistance_beton or RESISTANCE_BETON_DEFAUT
    fbu = 0.85 * fc28 / (1.0 * GAMMA_BETON)  # theta=1 (durée > 24h, cas courant)

    moment_reduit = moment_flechissant_mn / (largeur * hauteur_utile ** 2 * fbu)

    if moment_reduit > MU_LIMITE_PIVOT_AB:
        raise NotImplementedError(
            f"Moment réduit ({moment_reduit:.3f}) dépasse la limite pivot A/B "
            f"({MU_LIMITE_PIVOT_AB}) -- section doublement armée nécessaire, "
            f"non gérée par ce pré-dimensionnement simplifié. Revoir la "
            f"hauteur de poutre ou consulter le technicien BTP."
        )

    alpha = 1.25 * (1 - math.sqrt(1 - 2 * moment_reduit))
    bras_de_levier = hauteur_utile * (1 - 0.4 * alpha)

    fsu = LIMITE_ELASTIQUE_ACIER / GAMMA_ACIER
    section_acier_m2 = moment_flechissant_mn / (bras_de_levier * fsu)
    section_acier_cm2 = section_acier_m2 * 10_000

    return {
        "hauteur_cm": round(hauteur * 100, 1),
        "largeur_cm": round(largeur * 100, 1),
        "moment_flechissant_knm": round(moment_flechissant, 2),
        "moment_reduit": round(moment_reduit, 4),
        "section_acier_theorique_cm2": round(section_acier_cm2, 2),
    }