"""
Dimensionnement des poteaux (compression centrée) -- BAEL 91 mod.99.

Formule simplifiée de pré-dimensionnement (document technicien, section
3.1), complétée par une vérification du flambement (méthode forfaitaire
BAEL, valable jusqu'à un élancement de 70).
"""

import math

from ..constantes import (
    RESISTANCE_BETON_DEFAUT,
    LIMITE_ELASTIQUE_ACIER,
    GAMMA_BETON,
    COEFFICIENT_SECURITE_POTEAU_RAPIDE,
    LF_SUR_L0_DEFAUT,
    ELANCEMENT_MAX_METHODE_SIMPLIFIEE,
)
from ..validators import EntreeInvalide


def calculer_elancement(hauteur_poteau, cote_cm, lf_sur_l0=None):
    """
    Élancement lambda d'un poteau carré, méthode BAEL.

    Rayon de giration (section carrée) : i = cote / sqrt(12)
    Longueur de flambement : lf = (lf_sur_l0) x hauteur_poteau
    Élancement : lambda = lf / i

    Paramètres
    ----------
    hauteur_poteau : float
        Hauteur libre du poteau (l0), en mètres.
    cote_cm : float
        Côté du poteau carré, en cm.
    lf_sur_l0 : float, optionnel
        Rapport longueur de flambement / hauteur libre. Par défaut :
        1,0 (hypothèse prudente d'un poteau articulé aux deux
        extrémités -- voir constantes.LF_SUR_L0_DEFAUT). À réduire à
        0,7 si le technicien confirme un encastrement efficace par les
        planchers.

    Retour : élancement lambda (sans dimension).
    """
    if hauteur_poteau is None or hauteur_poteau <= 0:
        raise EntreeInvalide("La hauteur du poteau doit être positive.")
    if cote_cm is None or cote_cm <= 0:
        raise EntreeInvalide("Le côté du poteau doit être positif.")

    rapport = lf_sur_l0 or LF_SUR_L0_DEFAUT
    cote_m = cote_cm / 100
    rayon_giration = cote_m / math.sqrt(12)
    longueur_flambement = rapport * hauteur_poteau
    return longueur_flambement / rayon_giration


def calculer_coefficient_flambement(elancement):
    """
    Coefficient alpha de réduction pour flambement, méthode forfaitaire
    BAEL :
        lambda <= 50 : alpha = 0,85 / (1 + 0,2 x (lambda/35)^2)
        50 < lambda <= 70 : alpha = 0,6 x (50/lambda)^2
        lambda > 70 : méthode forfaitaire non applicable

    Lève NotImplementedError si lambda > 70 -- une vérification de
    flambement détaillée (hors méthode simplifiée) devient nécessaire,
    à faire réaliser par l'ingénieur structure, pas par ce moteur.
    """
    if elancement <= 50:
        return 0.85 / (1 + 0.2 * (elancement / 35) ** 2)
    elif elancement <= ELANCEMENT_MAX_METHODE_SIMPLIFIEE:
        return 0.6 * (50 / elancement) ** 2
    else:
        raise NotImplementedError(
            f"Élancement calculé ({elancement:.1f}) dépasse la limite de la "
            f"méthode forfaitaire BAEL ({ELANCEMENT_MAX_METHODE_SIMPLIFIEE}). "
            f"Une vérification de flambement détaillée par l'ingénieur "
            f"structure est nécessaire -- ce moteur ne peut pas conclure "
            f"automatiquement dans ce cas."
        )


def verifier_flambement(cote_cm, hauteur_poteau, charge_calculee, resistance_beton=None, lf_sur_l0=None):
    """
    Vérifie si la section proposée résiste au flambement, en ne
    comptant QUE la contribution du béton (conservateur : la vraie
    résistance avec les aciers longitudinaux sera toujours supérieure
    à ce calcul -- donc si cette vérification passe, le poteau est
    sûr ; si elle échoue, cela ne veut pas forcément dire que le
    poteau est sous-dimensionné, juste qu'une vérification complète
    avec le ferraillage réel est nécessaire).

    Formule (document technicien, section 3.1, version complète) :
        Nu_lim_beton_seul = alpha x (Br x fc28) / (0,9 x gamma_b)
        Br = section réduite = (cote_cm - 2)^2 (1 cm retiré de chaque face)

    Retour
    ------
    dict : {
        "elancement": float,
        "coefficient_alpha": float,
        "nu_lim_beton_seul_kn": float,
        "verification_beton_seul_suffisante": bool,
    }
    """
    elancement = calculer_elancement(hauteur_poteau, cote_cm, lf_sur_l0)
    alpha = calculer_coefficient_flambement(elancement)

    fc28 = resistance_beton or RESISTANCE_BETON_DEFAUT
    fc28_kn_cm2 = fc28 * 0.1  # MPa -> kN/cm²

    cote_reduit_cm = max(cote_cm - 2, 1)  # Br : 1 cm retiré de chaque face
    br_cm2 = cote_reduit_cm ** 2

    nu_lim_beton_seul = alpha * (br_cm2 * fc28_kn_cm2) / 0.9 / GAMMA_BETON

    return {
        "elancement": round(elancement, 1),
        "coefficient_alpha": round(alpha, 3),
        "nu_lim_beton_seul_kn": round(nu_lim_beton_seul, 1),
        "verification_beton_seul_suffisante": charge_calculee <= nu_lim_beton_seul,
    }


def dimensionner_poteau(charge_calculee, hauteur_poteau, resistance_beton=None, lf_sur_l0=None):
    """
    Pré-dimensionnement rapide d'un poteau carré en compression centrée,
    avec vérification du flambement (méthode forfaitaire BAEL).

    Paramètres
    ----------
    charge_calculee : float
        Charge ELU cumulée reprise par le poteau, en kN.
    hauteur_poteau : float
        Hauteur libre du poteau, en mètres.
    resistance_beton : float, optionnel
        fc28 en MPa. Par défaut : constante du projet (25 MPa).
    lf_sur_l0 : float, optionnel
        Voir calculer_elancement() -- rapport longueur de flambement /
        hauteur libre.

    Retour
    ------
    dict : {
        "cote_cm": float,
        "section_cm2": float,
        "section_theorique_cm2": float,
        "elancement": float,
        "coefficient_alpha": float,
        "nu_lim_beton_seul_kn": float,
        "verification_beton_seul_suffisante": bool,
    }

    Si la vérification béton seul n'est pas suffisante, le côté est
    augmenté progressivement (par pas de 5 cm) jusqu'à ce qu'elle le
    soit, ou jusqu'à une limite raisonnable au-delà de laquelle une
    vérification manuelle complète (avec ferraillage réel) est requise.
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

    cote_theorique = math.sqrt(section_theorique_cm2)
    cote_retenu = max(20, math.ceil(cote_theorique / 5) * 5)

    # Vérification du flambement -- si insuffisante, on augmente le
    # côté par pas de 5 cm (jusqu'à 60 cm, au-delà une vérification
    # manuelle complète est nécessaire plutôt que de laisser le moteur
    # boucler indéfiniment).
    verification = verifier_flambement(cote_retenu, hauteur_poteau, charge_calculee, fc28, lf_sur_l0)
    while not verification["verification_beton_seul_suffisante"] and cote_retenu < 60:
        cote_retenu += 5
        verification = verifier_flambement(cote_retenu, hauteur_poteau, charge_calculee, fc28, lf_sur_l0)

    return {
        "cote_cm": cote_retenu,
        "section_cm2": cote_retenu ** 2,
        "section_theorique_cm2": round(section_theorique_cm2, 1),
        **verification,
    }