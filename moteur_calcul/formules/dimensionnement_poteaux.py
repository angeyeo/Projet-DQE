"""
Dimensionnement des poteaux (compression centrée) -- BAEL 91 mod.99.

Formules alignées sur le fichier de référence du technicien BTP
("Mon Métreur" / Metrec, feuille "Poteau_compression simple") :
- pré-dimensionnement rapide + vérification du flambement (déjà en place)
- calcul de la VRAIE section d'acier (théorique + minimum réglementaire
  + vérification du pourcentage maximal), ajouté ici.
"""

import math

from ..constantes import (
    RESISTANCE_BETON_DEFAUT,
    LIMITE_ELASTIQUE_ACIER,
    GAMMA_BETON,
    GAMMA_ACIER,
    COEFFICIENT_SECURITE_POTEAU_RAPIDE,
    LF_SUR_L0_DEFAUT,
    ELANCEMENT_MAX_METHODE_SIMPLIFIEE,
)
from ..validators import EntreeInvalide
from ..tables_acier import proposer_barres


def calculer_elancement(hauteur_poteau, cote_cm, lf_sur_l0=None):
    """
    Élancement lambda d'un poteau carré, méthode BAEL.

    Rayon de giration (section carrée) : i = cote / sqrt(12)
    Longueur de flambement : lf = (lf_sur_l0) x hauteur_poteau
    Élancement : lambda = lf / i
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
    Coefficient alpha1 de réduction pour flambement, méthode forfaitaire
    BAEL :
        lambda <= 50 : alpha = 0,85 / (1 + 0,2 x (lambda/35)^2)
        50 < lambda <= 70 : alpha = 0,6 x (50/lambda)^2
        lambda > 70 : méthode forfaitaire non applicable
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
    Vérifie si la section proposée résiste au flambement (béton seul,
    conservateur -- voir docstring détaillée dans les versions
    précédentes de ce module).
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


def calculer_section_acier(charge_calculee, cote_cm, alpha, resistance_beton=None, limite_elastique_acier=None):
    """
    Calcule la vraie section d'acier longitudinal d'un poteau carré,
    méthode BAEL forfaitaire -- alignée sur le fichier de référence du
    technicien ("Mon Métreur", feuille Poteau_compression simple).

    Formule (cas général, hypothèse : majorité des charges appliquée
    après 90 jours -- voir constantes.DELAI_APPLICATION_CHARGES_SUPPOSE) :

        A_théorique = [Nu/alpha2 - Br.fc28/(0,9.gamma_b)] / (fe/gamma_s) x 10^4

    Section minimale réglementaire :
        A(4u) = 4 x périmètre (m)          -- en cm²
        A(0,2%) = 0,2% x section brute B
        A_min = max(A(4u), A(0,2%))

    Section maximale réglementaire :
        A_max = 5% x B

    Paramètres
    ----------
    charge_calculee : float
        Charge ELU (Nu), en kN.
    cote_cm : float
        Côté du poteau carré retenu, en cm.
    alpha : float
        Coefficient de flambement alpha1 (voir calculer_coefficient_flambement).
        Utilisé directement comme alpha2 sous l'hypothèse >90 jours.
    resistance_beton : float, optionnel
        fc28 en MPa.
    limite_elastique_acier : float, optionnel
        fe en MPa.

    Retour
    ------
    dict : {
        "section_acier_theorique_cm2": float,   # peut être négative (béton largement suffisant)
        "section_acier_min_cm2": float,
        "section_acier_max_cm2": float,
        "section_acier_retenue_cm2": float,      # max(theorique, min)
        "frettage_necessaire": bool,             # True si section_retenue > max
    }
    """
    if charge_calculee is None or charge_calculee <= 0:
        raise EntreeInvalide("La charge calculée doit être positive.")
    if cote_cm is None or cote_cm <= 0:
        raise EntreeInvalide("Le côté du poteau doit être positif.")

    fc28 = resistance_beton or RESISTANCE_BETON_DEFAUT
    fe = limite_elastique_acier or LIMITE_ELASTIQUE_ACIER

    nu_mn = charge_calculee / 1000  # kN -> MN
    cote_reduit_cm = max(cote_cm - 2, 1)
    br_m2 = (cote_reduit_cm ** 2) / 10000  # cm² -> m²

    fsu = fe / GAMMA_ACIER  # MPa

    # alpha2 = alpha (hypothèse >90 jours -- pas de division supplémentaire)
    alpha2 = alpha

    section_theorique_m2 = (nu_mn / alpha2 - br_m2 * fc28 / (0.9 * GAMMA_BETON)) / fsu
    section_theorique_cm2 = section_theorique_m2 * 10000

    b_cm2 = cote_cm ** 2
    perimetre_m = 4 * 0.01 * cote_cm  # carré : 4 côtés
    section_4u = 4 * perimetre_m
    section_02pct = 0.002 * b_cm2
    section_min = max(section_4u, section_02pct)
    section_max = 0.05 * b_cm2

    section_retenue = max(section_min, section_theorique_cm2)
    # nb_barres_min=4 : un poteau a structurellement besoin d'au moins
    # une barre à chaque coin, pas juste 2 comme le minimum générique
    # de proposer_barres().
    barres = proposer_barres(section_retenue, diametres_autorises=[12, 14, 16, 20], nb_barres_min=4)

    return {
        "section_acier_theorique_cm2": round(section_theorique_cm2, 2),
        "section_acier_min_cm2": round(section_min, 2),
        "section_acier_max_cm2": round(section_max, 2),
        "section_acier_retenue_cm2": round(section_retenue, 2),
        "frettage_necessaire": section_retenue > section_max,
        "barres_proposees": barres,
    }


def dimensionner_poteau(charge_calculee, hauteur_poteau, resistance_beton=None, lf_sur_l0=None):
    """
    Pré-dimensionnement complet d'un poteau carré en compression centrée :
    section béton (avec vérification du flambement) + vraie section
    d'acier (théorique, minimum réglementaire, vérification du 5% max).

    Retour
    ------
    dict : {
        "cote_cm": float,
        "section_cm2": float,
        "section_theorique_cm2": float,          # section béton théorique (avant flambement)
        "elancement": float,
        "coefficient_alpha": float,
        "nu_lim_beton_seul_kn": float,
        "verification_beton_seul_suffisante": bool,
        "section_acier_theorique_cm2": float,
        "section_acier_min_cm2": float,
        "section_acier_max_cm2": float,
        "section_acier_retenue_cm2": float,
        "frettage_necessaire": bool,
    }
    """
    if charge_calculee is None or charge_calculee <= 0:
        raise EntreeInvalide("La charge calculée doit être positive.")
    if hauteur_poteau is None or hauteur_poteau <= 0:
        raise EntreeInvalide("La hauteur du poteau doit être positive.")

    fc28 = resistance_beton or RESISTANCE_BETON_DEFAUT

    section_theorique_cm2 = (
        charge_calculee / (0.7 * fc28 * 0.1) * COEFFICIENT_SECURITE_POTEAU_RAPIDE
    )

    cote_theorique = math.sqrt(section_theorique_cm2)
    cote_retenu = max(20, math.ceil(cote_theorique / 5) * 5)

    verification = verifier_flambement(cote_retenu, hauteur_poteau, charge_calculee, fc28, lf_sur_l0)
    while not verification["verification_beton_seul_suffisante"] and cote_retenu < 60:
        cote_retenu += 5
        verification = verifier_flambement(cote_retenu, hauteur_poteau, charge_calculee, fc28, lf_sur_l0)

    section_acier = calculer_section_acier(
        charge_calculee, cote_retenu, verification["coefficient_alpha"], fc28
    )

    return {
        "cote_cm": cote_retenu,
        "section_cm2": cote_retenu ** 2,
        "section_theorique_cm2": round(section_theorique_cm2, 1),
        **verification,
        **section_acier,
    }