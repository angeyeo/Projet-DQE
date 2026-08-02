"""
Descente de charges.

Chaque fonction ci-dessous a sa signature figée pour que le backend (DRF)
puisse déjà être branché dessus sans attendre le contenu réel de la formule.
Le corps de chaque fonction sera rempli avec la formule fournie par le
technicien BTP (norme BAEL ou Eurocode -- à confirmer).
"""

from ..constantes import CHARGES_EXPLOITATION, POIDS_VOLUMIQUE_BETON
from ..validators import valider_portee, valider_usage_batiment, valider_surface


def calculer_charge_permanente(surface, epaisseur_dalle, poids_volumique_beton=None):
    """
    Calcule la charge permanente (poids propre) d'un niveau.

    Paramètres
    ----------
    surface : float
        Surface du niveau en m².
    epaisseur_dalle : float
        Épaisseur de la dalle en mètres.
    poids_volumique_beton : float, optionnel
        Poids volumique du béton en kN/m³. Si non fourni, utilise la
        constante par défaut du projet.

    Retour
    ------
    float
        Charge permanente en kN.

    TODO (technicien BTP) : confirmer la formule exacte -- inclut-on le
    poids des cloisons/finitions ici, ou séparément ?
    """
    valider_surface(surface)
    poids_volumique = poids_volumique_beton or POIDS_VOLUMIQUE_BETON
    if poids_volumique is None:
        raise NotImplementedError(
            "POIDS_VOLUMIQUE_BETON n'est pas encore défini dans constantes.py"
        )
    # TODO : formule réelle à injecter (ex. surface * epaisseur_dalle * poids_volumique)
    raise NotImplementedError("Formule à injecter -- en attente du technicien BTP")


def calculer_charge_exploitation(surface, usage_batiment):
    """
    Calcule la charge d'exploitation selon l'usage du bâtiment.

    Paramètres
    ----------
    surface : float
        Surface du niveau en m².
    usage_batiment : str
        'habitation' | 'commerce' | 'bureau' | 'industriel'

    Retour
    ------
    float
        Charge d'exploitation en kN.
    """
    valider_surface(surface)
    valider_usage_batiment(usage_batiment)
    charge_unitaire = CHARGES_EXPLOITATION[usage_batiment]
    if charge_unitaire is None:
        raise NotImplementedError(
            f"CHARGES_EXPLOITATION['{usage_batiment}'] n'est pas encore défini"
        )
    return surface * charge_unitaire


def calculer_charge_totale_niveau(
    charge_permanente, charge_exploitation, nb_niveaux_superieurs=0
):
    """
    Cumule la charge qui descend sur un niveau donné, en tenant compte
    des niveaux situés au-dessus.

    Paramètres
    ----------
    charge_permanente : float
        Charge permanente du niveau, en kN.
    charge_exploitation : float
        Charge d'exploitation du niveau, en kN.
    nb_niveaux_superieurs : int
        Nombre de niveaux situés au-dessus (dont les charges descendent
        aussi sur ce niveau).

    Retour
    ------
    float
        Charge totale cumulée en kN.

    TODO (technicien BTP) : confirmer si on applique un coefficient de
    dégression des charges d'exploitation pour les niveaux élevés
    (pratique courante en descente de charges multi-niveaux).
    """
    if charge_permanente is None or charge_exploitation is None:
        raise NotImplementedError("Charges permanente/exploitation non calculées")
    # TODO : formule réelle à injecter, potentiellement avec dégression
    raise NotImplementedError("Formule à injecter -- en attente du technicien BTP")