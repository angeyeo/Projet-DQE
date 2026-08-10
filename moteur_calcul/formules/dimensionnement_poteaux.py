"""
Dimensionnement des poteaux (compression centrée) -- BAEL 91 mod.99.

Formules alignées sur le fichier de référence du technicien BTP
("Mon Métreur" / Metrec, feuille "Poteau_compression simple") :
- pré-dimensionnement rapide + vérification du flambement (déjà en place)
- calcul de la VRAIE section d'acier (théorique + minimum réglementaire
  + vérification du pourcentage maximal)
- sections rectangulaires (Phase 2, module 3) : le flambement est
  vérifié sur l'axe faible (le plus petit côté), Br et le périmètre
  tiennent compte des deux dimensions.
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


def calculer_elancement(hauteur_poteau, cote_cm, lf_sur_l0=None, profondeur_cm=None):
    """
    Élancement lambda d'un poteau, méthode BAEL.

    Rayon de giration : i = h / sqrt(12) suivant l'axe considéré. Pour
    une section rectangulaire, le flambement se produit autour de l'axe
    FAIBLE, donc c'est le PLUS PETIT côté qui gouverne :
        i_min = min(largeur, profondeur) / sqrt(12)

    Longueur de flambement : lf = (lf_sur_l0) x hauteur_poteau
    Élancement : lambda = lf / i_min

    Paramètres
    ----------
    hauteur_poteau : float
        Hauteur libre l0, en mètres.
    cote_cm : float
        Côté du poteau, en cm (largeur si rectangulaire).
    lf_sur_l0 : float, optionnel
        Rapport longueur de flambement / hauteur libre (défaut : voir
        constantes.LF_SUR_L0_DEFAUT).
    profondeur_cm : float, optionnel
        Second côté, en cm. Omis => section carrée.
    """
    if hauteur_poteau is None or hauteur_poteau <= 0:
        raise EntreeInvalide("La hauteur du poteau doit être positive.")
    if cote_cm is None or cote_cm <= 0:
        raise EntreeInvalide("Le côté du poteau doit être positif.")
    if profondeur_cm is not None and profondeur_cm <= 0:
        raise EntreeInvalide("La profondeur du poteau doit être positive.")

    rapport = lf_sur_l0 or LF_SUR_L0_DEFAUT
    cote_faible_m = min(cote_cm, profondeur_cm or cote_cm) / 100
    rayon_giration = cote_faible_m / math.sqrt(12)
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


def verifier_flambement(cote_cm, hauteur_poteau, charge_calculee, resistance_beton=None,
                        lf_sur_l0=None, profondeur_cm=None):
    """
    Vérifie si la section proposée résiste au flambement en ne comptant
    QUE la contribution du béton -- volontairement conservateur : la
    résistance réelle, aciers longitudinaux compris, sera toujours
    supérieure. Si cette vérification passe, le poteau est sûr ; si
    elle échoue, cela ne veut pas dire qu'il est sous-dimensionné, mais
    qu'une vérification complète avec le ferraillage réel est nécessaire.

    Formule (document technicien, section 3.1, version complète) :
        Nu_lim_beton_seul = alpha x (Br x fc28) / (0,9 x gamma_b)
        Br = section réduite = (largeur - 2) x (profondeur - 2)
             (1 cm retiré de chaque face)

    Paramètres
    ----------
    cote_cm : float
        Largeur du poteau, en cm.
    profondeur_cm : float, optionnel
        Second côté, en cm. Omis => section carrée.

    Retour
    ------
    dict : {
        "elancement": float,
        "coefficient_alpha": float,
        "nu_lim_beton_seul_kn": float,
        "verification_beton_seul_suffisante": bool,
    }
    """
    elancement = calculer_elancement(hauteur_poteau, cote_cm, lf_sur_l0, profondeur_cm)
    alpha = calculer_coefficient_flambement(elancement)

    fc28 = resistance_beton or RESISTANCE_BETON_DEFAUT
    fc28_kn_cm2 = fc28 * 0.1  # MPa -> kN/cm²

    # Br : 1 cm retiré de chaque face, sur les deux directions
    br_cm2 = max(cote_cm - 2, 1) * max((profondeur_cm or cote_cm) - 2, 1)

    nu_lim_beton_seul = alpha * (br_cm2 * fc28_kn_cm2) / 0.9 / GAMMA_BETON

    return {
        "elancement": round(elancement, 1),
        "coefficient_alpha": round(alpha, 3),
        "nu_lim_beton_seul_kn": round(nu_lim_beton_seul, 1),
        "verification_beton_seul_suffisante": charge_calculee <= nu_lim_beton_seul,
    }


def calculer_section_acier(charge_calculee, cote_cm, alpha, resistance_beton=None,
                           limite_elastique_acier=None, profondeur_cm=None):
    """
    Calcule la vraie section d'acier longitudinal d'un poteau (carré ou
    rectangulaire), méthode BAEL forfaitaire -- alignée sur le fichier
    de référence du technicien ("Mon Métreur", feuille
    Poteau_compression simple).

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
        Largeur du poteau retenue, en cm.
    alpha : float
        Coefficient de flambement alpha1 (voir calculer_coefficient_flambement).
        Utilisé directement comme alpha2 sous l'hypothèse >90 jours.
    resistance_beton : float, optionnel
        fc28 en MPa.
    limite_elastique_acier : float, optionnel
        fe en MPa.
    profondeur_cm : float, optionnel
        Second côté, en cm. Omis => section carrée.

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
    if profondeur_cm is not None and profondeur_cm <= 0:
        raise EntreeInvalide("La profondeur du poteau doit être positive.")

    profondeur_cm = profondeur_cm or cote_cm

    fc28 = resistance_beton or RESISTANCE_BETON_DEFAUT
    fe = limite_elastique_acier or LIMITE_ELASTIQUE_ACIER

    nu_mn = charge_calculee / 1000  # kN -> MN
    br_cm2 = max(cote_cm - 2, 1) * max(profondeur_cm - 2, 1)
    br_m2 = br_cm2 / 10000  # cm² -> m²

    fsu = fe / GAMMA_ACIER  # MPa

    # alpha2 = alpha (hypothèse >90 jours -- pas de division supplémentaire)
    alpha2 = alpha

    section_theorique_m2 = (nu_mn / alpha2 - br_m2 * fc28 / (0.9 * GAMMA_BETON)) / fsu
    section_theorique_cm2 = section_theorique_m2 * 10000

    b_cm2 = cote_cm * profondeur_cm
    perimetre_m = 2 * 0.01 * (cote_cm + profondeur_cm)
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


def dimensionner_poteau_rectangulaire(
    charge_calculee,
    hauteur_poteau,
    rapport_forme=1.0,
    resistance_beton=None,
    lf_sur_l0=None,
    largeur_imposee_cm=None,
):
    """
    Pré-dimensionnement complet d'un poteau RECTANGULAIRE en compression
    centrée (Phase 2, module 3) : section béton (avec vérification du
    flambement sur l'axe faible) + section d'acier réelle.

    Un poteau 20x30 ou 30x50 est le cas courant en bâtiment (poteau noyé
    dans un mur, poteau d'angle...) ; la version carrée n'en est qu'un
    cas particulier -- dimensionner_poteau() délègue ici avec
    rapport_forme=1,0.

    Paramètres
    ----------
    charge_calculee : float
        Charge ELU cumulée reprise par le poteau, en kN.
    hauteur_poteau : float
        Hauteur libre du poteau, en mètres.
    rapport_forme : float
        Profondeur / largeur souhaitée (>= 1). 1,0 = carré, 1,5 = 20x30,
        2,0 = 20x40... La section théorique est répartie selon ce
        rapport, puis chaque côté est arrondi au multiple de 5 cm
        supérieur (minimum constructif 20 cm). Le rapport est conservé
        même quand le minimum de 20 cm s'applique : on suppose que la
        forme est imposée par l'architecture, pas seulement par la
        charge. Ignoré si largeur_imposee_cm est fourni.
    resistance_beton : float, optionnel
        fc28 en MPa.
    lf_sur_l0 : float, optionnel
        Voir calculer_elancement().
    largeur_imposee_cm : float, optionnel
        Largeur figée par l'architecture (cas très courant : poteau noyé
        dans un mur de 20 cm). Dans ce cas seule la profondeur est
        calculée, et c'est elle qui est augmentée si le flambement ne
        passe pas.

    Retour
    ------
    dict : {
        "largeur_cm": float,          # petit côté (celui qui gouverne le flambement)
        "profondeur_cm": float,       # grand côté
        "rapport_forme_reel": float,  # après arrondi au multiple de 5
        "section_cm2": float,
        "section_theorique_cm2": float,   # section béton théorique, avant flambement
        "elancement", "coefficient_alpha", "nu_lim_beton_seul_kn",
        "verification_beton_seul_suffisante",
        "section_acier_theorique_cm2", "section_acier_min_cm2",
        "section_acier_max_cm2", "section_acier_retenue_cm2",
        "frettage_necessaire", "barres_proposees",
    }

    Note : si la vérification au flambement échoue, c'est le PETIT côté
    qui est augmenté par pas de 5 cm (c'est lui qui gouverne l'axe
    faible), la profondeur suivant pour conserver le rapport de forme,
    jusqu'à une limite de 60 cm au-delà de laquelle une vérification
    manuelle complète est requise. Si la largeur est imposée, c'est la
    profondeur qui est augmentée (jusqu'à 100 cm) -- elle n'améliore
    que la section réduite Br, pas l'élancement.
    """
    if charge_calculee is None or charge_calculee <= 0:
        raise EntreeInvalide("La charge calculée doit être positive.")
    if hauteur_poteau is None or hauteur_poteau <= 0:
        raise EntreeInvalide("La hauteur du poteau doit être positive.")
    if rapport_forme is None or rapport_forme < 1:
        raise EntreeInvalide(
            "Le rapport de forme doit être >= 1 (profondeur / largeur, "
            "le petit côté étant la largeur)."
        )
    if largeur_imposee_cm is not None and largeur_imposee_cm <= 0:
        raise EntreeInvalide("La largeur imposée doit être positive.")

    fc28 = resistance_beton or RESISTANCE_BETON_DEFAUT

    section_theorique_cm2 = (
        charge_calculee / (0.7 * fc28 * 0.1) * COEFFICIENT_SECURITE_POTEAU_RAPIDE
    )

    if largeur_imposee_cm:
        largeur = largeur_imposee_cm
        profondeur = max(20, math.ceil(section_theorique_cm2 / largeur / 5) * 5)
    else:
        largeur_theorique = math.sqrt(section_theorique_cm2 / rapport_forme)
        largeur = max(20, math.ceil(largeur_theorique / 5) * 5)
        # rapport appliqué à la largeur RETENUE, sinon l'arrondi et le
        # minimum de 20 cm écrasent la forme demandée (un 2:1 sous
        # faible charge redeviendrait un carré 20x20)
        profondeur = max(20, math.ceil(largeur * rapport_forme / 5) * 5)

    verification = verifier_flambement(
        largeur, hauteur_poteau, charge_calculee, fc28, lf_sur_l0, profondeur
    )
    while not verification["verification_beton_seul_suffisante"] and (
        (largeur_imposee_cm and profondeur < 100) or (not largeur_imposee_cm and largeur < 60)
    ):
        if largeur_imposee_cm:
            profondeur += 5
        else:
            largeur += 5
            profondeur = max(profondeur, math.ceil(largeur * rapport_forme / 5) * 5)
        verification = verifier_flambement(
            largeur, hauteur_poteau, charge_calculee, fc28, lf_sur_l0, profondeur
        )

    section_acier = calculer_section_acier(
        charge_calculee, largeur, verification["coefficient_alpha"], fc28,
        profondeur_cm=profondeur,
    )

    return {
        "largeur_cm": largeur,
        "profondeur_cm": profondeur,
        "rapport_forme_reel": round(profondeur / largeur, 2),
        "section_cm2": largeur * profondeur,
        "section_theorique_cm2": round(section_theorique_cm2, 1),
        **verification,
        **section_acier,
    }


def dimensionner_poteau(charge_calculee, hauteur_poteau, resistance_beton=None, lf_sur_l0=None):
    """
    Pré-dimensionnement complet d'un poteau CARRÉ en compression centrée :
    section béton (avec vérification du flambement) + vraie section
    d'acier (théorique, minimum réglementaire, vérification du 5% max).

    Cas particulier de dimensionner_poteau_rectangulaire() avec un
    rapport de forme de 1,0. Conservée telle quelle (clé "cote_cm"
    comprise) parce que le reste de l'application l'appelle ainsi
    (projets/services/calculations.py, dqe_calculator.py).

    Retour
    ------
    dict : identique à dimensionner_poteau_rectangulaire(), plus
    "cote_cm" (= largeur_cm = profondeur_cm).
    """
    resultat = dimensionner_poteau_rectangulaire(
        charge_calculee, hauteur_poteau, 1.0, resistance_beton, lf_sur_l0
    )
    return {"cote_cm": resultat["largeur_cm"], **resultat}