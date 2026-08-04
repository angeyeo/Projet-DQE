"""
Descente de charges -- BAEL 91 mod.99 (référentiel par défaut).

Formules basées sur le document "reference_technique_BAEL_EC2_DQE"
(sections 2.2 à 2.4) fourni par le technicien BTP.
"""

from ..constantes import (
    CHARGES_EXPLOITATION,
    POIDS_VOLUMIQUE_BETON,
    COEFFICIENT_G_ELU,
    COEFFICIENT_Q_ELU,
)
from ..validators import valider_surface, valider_usage_batiment


def calculer_surface_influence(portee_gauche, portee_droite, portee_avant, portee_arriere):
    """
    Surface d'influence (aire tributaire) d'un poteau, selon les portées
    des travées qui l'entourent de chaque côté.

    Formule (document technicien, section 2.4) :
        S = (portee_gauche/2 + portee_droite/2) x (portee_avant/2 + portee_arriere/2)

    Paramètres en mètres. Retour en m².
    """
    for p in (portee_gauche, portee_droite, portee_avant, portee_arriere):
        if p is None or p < 0:
            raise ValueError("Toutes les portées doivent être positives ou nulles.")
    largeur = (portee_gauche / 2) + (portee_droite / 2)
    profondeur = (portee_avant / 2) + (portee_arriere / 2)
    return largeur * profondeur


def calculer_charge_permanente(surface, epaisseur_dalle, poids_volumique_beton=None):
    """
    Charge permanente (poids propre) d'un niveau, ramenée à la surface
    d'influence d'un appui.

    G = surface x epaisseur_dalle x poids_volumique_beton

    Paramètres
    ----------
    surface : float
        Surface d'influence en m².
    epaisseur_dalle : float
        Épaisseur de la dalle en mètres.
    poids_volumique_beton : float, optionnel
        kN/m³. Si non fourni, utilise la constante par défaut (25 kN/m³).

    Retour : charge permanente en kN.

    Note : ne couvre pas encore les cloisons/revêtements/étanchéité
    mentionnés dans le document (section 2.1) -- à ajouter comme charge
    complémentaire si le technicien fournit des valeurs de poids
    surfacique pour ces éléments.
    """
    valider_surface(surface)
    if epaisseur_dalle is None or epaisseur_dalle <= 0:
        raise ValueError("L'épaisseur de dalle doit être positive.")
    poids_volumique = poids_volumique_beton or POIDS_VOLUMIQUE_BETON
    return surface * epaisseur_dalle * poids_volumique


def calculer_charge_exploitation(surface, usage_batiment):
    """
    Charge d'exploitation Q, ramenée à la surface d'influence.

    Q = surface x charge_unitaire(usage)

    Valeurs de charge_unitaire : voir constantes.CHARGES_EXPLOITATION
    (document technicien, section 2.2).
    """
    valider_surface(surface)
    valider_usage_batiment(usage_batiment)
    charge_unitaire = CHARGES_EXPLOITATION[usage_batiment]
    if charge_unitaire is None:
        raise NotImplementedError(
            f"CHARGES_EXPLOITATION['{usage_batiment}'] non fournie par le "
            f"technicien -- à demander avant de calculer cet usage."
        )
    return surface * charge_unitaire


def calculer_charge_ponderee_elu(charge_permanente, charge_exploitation):
    """
    Combinaison ELU (document technicien, section 2.3) :
        Nu = 1,35 G + 1,5 Q
    """
    if charge_permanente is None or charge_exploitation is None:
        raise ValueError("Charges permanente et exploitation requises.")
    return COEFFICIENT_G_ELU * charge_permanente + COEFFICIENT_Q_ELU * charge_exploitation


def calculer_charge_ponderee_els(charge_permanente, charge_exploitation):
    """
    Combinaison ELS (document technicien, section 2.3) :
        Ns = G + Q
    """
    if charge_permanente is None or charge_exploitation is None:
        raise ValueError("Charges permanente et exploitation requises.")
    return charge_permanente + charge_exploitation


def calculer_charge_totale_niveau(charges_par_niveau_elu):
    """
    Cumule la charge ELU descendant sur un appui, niveau par niveau,
    du plus haut (toiture) vers la fondation -- principe de l'algorithme
    de descente de charges (document technicien, section 2.4, étapes 1-4).

    Paramètres
    ----------
    charges_par_niveau_elu : list[float]
        Liste des charges ELU (kN) de chaque niveau au-dessus de l'appui
        considéré, dans l'ordre (du niveau le plus haut au plus bas),
        déjà calculées via calculer_charge_ponderee_elu pour chaque
        niveau.

    Retour : charge ELU cumulée totale en kN, à la base de l'appui.

    Note : version simple = somme directe (pas de dégression des
    charges d'exploitation pour les niveaux élevés -- le document ne
    mentionne pas explicitement de coefficient de dégression ; à
    confirmer avec le technicien si le bâtiment dépasse quelques
    niveaux et qu'une dégression réglementaire s'applique).
    """
    if not charges_par_niveau_elu:
        raise ValueError("La liste des charges par niveau ne peut pas être vide.")
    if any(c is None or c < 0 for c in charges_par_niveau_elu):
        raise ValueError("Toutes les charges par niveau doivent être positives.")
    return sum(charges_par_niveau_elu)