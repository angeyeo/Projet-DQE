"""
Dimensionnement des poutres (flexion simple) -- BAEL 91 mod.99.

Formules alignées sur le fichier de référence du technicien BTP
("Mon Métreur", feuille "Flexion simple_sect rect ELUR") :
- pré-dimensionnement rapide + moment réduit (déjà en place)
- condition de non-fragilité (Amin) -- ajoutée ici
- gestion du Pivot B (µ > 0,186) via le moment critique µc, au lieu de
  rejeter le calcul -- ajoutée ici
- proposition de barres réelles -- ajoutée ici
"""

import math

from ..constantes import (
    RESISTANCE_BETON_DEFAUT,
    LIMITE_ELASTIQUE_ACIER,
    GAMMA_BETON,
    GAMMA_ACIER,
    MU_LIMITE_PIVOT_AB,
    RATIO_HAUTEUR_POUTRE_ISOSTATIQUE,
    DENSITE_ACIER_KG_M3,
    GAMMA_ELU_ELS_SUPPOSE,
)
from ..validators import valider_portee, EntreeInvalide
from ..tables_acier import proposer_barres


def predimensionner_hauteur_poutre(portee, isostatique=True):
    """
    Pré-dimensionnement rapide de la hauteur :
        h ≈ portée / 10 à 12   (poutre continue)
        h ≈ portée / 8 à 10    (poutre isostatique)
    """
    valider_portee(portee)
    ratio_min, ratio_max = RATIO_HAUTEUR_POUTRE_ISOSTATIQUE if isostatique else (10, 12)
    return portee / ratio_min


def calculer_moment_flechissant(charge_lineaire, portee):
    """
    Mu = charge_repartie x portee² / 8  (poutre simplement appuyée,
    charge uniforme).
    """
    valider_portee(portee)
    if charge_lineaire is None or charge_lineaire <= 0:
        raise EntreeInvalide("La charge linéaire doit être positive.")
    return charge_lineaire * portee ** 2 / 8


def calculer_moment_critique_pivot_b(gamma, fc28, fe=500):
    """
    Moment critique réduit µc, méthode BAEL (fichier technicien BTP,
    cas t > 24h, fc28 <= 30 MPa) -- détermine si une section rectangulaire
    sans armature comprimée reste exploitable malgré µbu > 0,186 (Pivot B).

    Paramètres
    ----------
    gamma : float
        Rapport Mu/Mser (moment ultime / moment de service).
    fc28 : float
        Résistance du béton, en MPa (formule valable si fc28 <= 30).
    fe : float
        Limite élastique de l'acier (500 ou 400 MPa -- formule différente
        selon la nuance).

    Retour : µc (moment critique réduit).

    Lève NotImplementedError si fc28 > 30 MPa ou fe hors 400/500 -- cas
    non couvert par cette formule simplifiée du technicien.
    """
    if fc28 > 30:
        raise NotImplementedError(
            f"fc28={fc28} MPa > 30 MPa : la formule du moment critique "
            f"(Pivot B) utilisée ici n'est valable que jusqu'à 30 MPa. "
            f"Vérification manuelle nécessaire."
        )
    if fe == 500:
        return 0.322 * gamma + 0.0051 * fc28 - 0.31
    elif fe == 400:
        return 0.344 * gamma + 0.0049 * fc28 - 0.305
    else:
        raise NotImplementedError(
            f"fe={fe} MPa : formule du moment critique disponible seulement "
            f"pour fe=400 ou fe=500 MPa."
        )


def dimensionner_poutre(portee, charge_lineaire, largeur=0.20, resistance_beton=None, gamma_elu_els=None):
    """
    Dimensionnement complet d'une poutre rectangulaire en flexion
    simple, méthode BAEL -- gère maintenant Pivot A ET Pivot B, plus la
    condition de non-fragilité et une proposition de barres réelles.

    Paramètres
    ----------
    portee : float
        En mètres.
    charge_lineaire : float
        Charge linéaire déjà pondérée ELU, en kN/m.
    largeur : float, optionnel
        Largeur de la poutre en mètres (défaut 0,20 m).
    resistance_beton : float, optionnel
        fc28 en MPa.
    gamma_elu_els : float, optionnel
        Rapport Mu/Mser réel, si connu (nécessaire seulement si on tombe
        en Pivot B). Sinon, valeur supposée (voir constantes.GAMMA_ELU_ELS_SUPPOSE).

    Retour
    ------
    dict : {
        "hauteur_cm", "largeur_cm", "moment_flechissant_knm",
        "moment_reduit", "pivot" ("A" ou "B"),
        "section_acier_theorique_cm2",
        "section_acier_min_cm2",           # condition de non-fragilité
        "non_fragilite_respectee": bool,
        "poids_acier_longitudinal_theorique_kg",
        "barres_proposees": dict | None,   # voir tables_acier.proposer_barres
        "gamma_estime": bool,              # True si gamma_elu_els n'a pas été fourni
    }
    """
    hauteur = predimensionner_hauteur_poutre(portee, isostatique=True)
    hauteur_utile = 0.9 * hauteur

    moment_flechissant = calculer_moment_flechissant(charge_lineaire, portee)
    moment_flechissant_mn = moment_flechissant / 1000

    fc28 = resistance_beton or RESISTANCE_BETON_DEFAUT
    fbu = 0.85 * fc28 / (1.0 * GAMMA_BETON)

    moment_reduit = moment_flechissant_mn / (largeur * hauteur_utile ** 2 * fbu)

    gamma_estime = gamma_elu_els is None
    gamma = gamma_elu_els or GAMMA_ELU_ELS_SUPPOSE

    pivot = "A" if moment_reduit <= MU_LIMITE_PIVOT_AB else "B"

    if pivot == "B":
        moment_critique = calculer_moment_critique_pivot_b(gamma, fc28, LIMITE_ELASTIQUE_ACIER)
        if moment_reduit > moment_critique:
            raise NotImplementedError(
                f"Section de béton mal dimensionnée (µ={moment_reduit:.3f} > "
                f"µc={moment_critique:.3f}) -- il faut augmenter la largeur "
                f"ou la hauteur de la poutre, pas juste ajouter des aciers. "
                f"Revoir le pré-dimensionnement avec des dimensions plus grandes."
            )
        # Sinon : section optimale malgré Pivot B, on continue le calcul normalement

    alpha = 1.25 * (1 - math.sqrt(1 - 2 * moment_reduit))
    bras_de_levier = hauteur_utile * (1 - 0.4 * alpha)

    fsu = LIMITE_ELASTIQUE_ACIER / GAMMA_ACIER
    section_acier_m2 = moment_flechissant_mn / (bras_de_levier * fsu)
    section_acier_cm2 = section_acier_m2 * 10_000

    # Condition de non-fragilité (fichier technicien) :
    # Amin = (ftj/fe) x 0,23 x d x b
    ftj = 0.6 + 0.06 * fc28
    section_min_cm2 = (ftj / LIMITE_ELASTIQUE_ACIER) * 0.23 * (hauteur_utile * 100) * (largeur * 100)

    poids_acier_longitudinal_theorique_kg = section_acier_m2 * portee * DENSITE_ACIER_KG_M3

    barres = proposer_barres(max(section_acier_cm2, section_min_cm2))

    return {
        "hauteur_cm": round(hauteur * 100, 1),
        "largeur_cm": round(largeur * 100, 1),
        "moment_flechissant_knm": round(moment_flechissant, 2),
        "moment_reduit": round(moment_reduit, 4),
        "pivot": pivot,
        "section_acier_theorique_cm2": round(section_acier_cm2, 2),
        "section_acier_min_cm2": round(section_min_cm2, 2),
        "non_fragilite_respectee": section_acier_cm2 >= section_min_cm2,
        "poids_acier_longitudinal_theorique_kg": round(poids_acier_longitudinal_theorique_kg, 2),
        "barres_proposees": barres,
        "gamma_estime": gamma_estime,
    }