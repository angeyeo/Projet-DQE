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
    """Combinaison ELU : Nu = 1,35 G + 1,5 Q"""
    if charge_permanente is None or charge_exploitation is None:
        raise ValueError("Charges permanente et exploitation requises.")
    return COEFFICIENT_G_ELU * charge_permanente + COEFFICIENT_Q_ELU * charge_exploitation


def calculer_charge_ponderee_els(charge_permanente, charge_exploitation):
    """Combinaison ELS : Ns = G + Q"""
    if charge_permanente is None or charge_exploitation is None:
        raise ValueError("Charges permanente et exploitation requises.")
    return charge_permanente + charge_exploitation


def calculer_charge_totale_niveau(charges_par_niveau_elu):
    """
    Cumule la charge ELU descendant sur un appui, niveau par niveau.

    Paramètres
    ----------
    charges_par_niveau_elu : list[float]
        Charges ELU (kN) de chaque niveau au-dessus de l'appui, déjà
        calculées via calculer_charge_ponderee_elu.

    Retour : charge ELU cumulée totale en kN.

    Note : somme directe, pas de dégression des charges d'exploitation
    pour les niveaux élevés -- à confirmer avec le technicien si le
    bâtiment dépasse quelques niveaux.
    """
    if not charges_par_niveau_elu:
        raise ValueError("La liste des charges par niveau ne peut pas être vide.")
    if any(c is None or c < 0 for c in charges_par_niveau_elu):
        raise ValueError("Toutes les charges par niveau doivent être positives.")
    return sum(charges_par_niveau_elu)


def calculer_descente_charges_complete(
    portee_gauche,
    portee_droite,
    portee_avant,
    portee_arriere,
    epaisseur_dalle,
    usage_batiment,
    nb_niveaux,
):
    """
    Chaîne complète de descente de charges, du plan jusqu'à la charge
    ELU cumulée sur un poteau -- automatise ce que l'exercice de
    vérification faisait à la main (surface d'influence -> G -> Q ->
    ELU par niveau -> cumul sur nb_niveaux).

    Hypothèse simplificatrice : tous les niveaux sont identiques (même
    trame, même épaisseur de dalle, même usage) -- pas de dégression
    des charges d'exploitation (voir note de calculer_charge_totale_niveau).

    Paramètres
    ----------
    portee_gauche, portee_droite, portee_avant, portee_arriere : float
        Portées des travées autour du poteau, en mètres.
    epaisseur_dalle : float
        Épaisseur de la dalle, en mètres (identique à chaque niveau).
    usage_batiment : str
        Usage du bâtiment (voir constantes.CHARGES_EXPLOITATION).
    nb_niveaux : int
        Nombre de niveaux dont la charge descend sur ce poteau.

    Retour
    ------
    dict : {
        "surface_influence_m2": float,
        "charge_permanente_par_niveau_kn": float,
        "charge_exploitation_par_niveau_kn": float,
        "charge_elu_par_niveau_kn": float,
        "charge_elu_cumulee_kn": float,   # à passer à dimensionner_poteau/semelle
    }
    """
    if nb_niveaux is None or nb_niveaux <= 0:
        raise ValueError("Le nombre de niveaux doit être positif.")

    surface = calculer_surface_influence(
        portee_gauche, portee_droite, portee_avant, portee_arriere
    )
    charge_g = calculer_charge_permanente(surface, epaisseur_dalle)
    charge_q = calculer_charge_exploitation(surface, usage_batiment)
    charge_elu_niveau = calculer_charge_ponderee_elu(charge_g, charge_q)
    charge_cumulee = calculer_charge_totale_niveau([charge_elu_niveau] * nb_niveaux)

    return {
        "surface_influence_m2": round(surface, 2),
        "charge_permanente_par_niveau_kn": round(charge_g, 2),
        "charge_exploitation_par_niveau_kn": round(charge_q, 2),
        "charge_elu_par_niveau_kn": round(charge_elu_niveau, 2),
        "charge_elu_cumulee_kn": round(charge_cumulee, 2),
    }