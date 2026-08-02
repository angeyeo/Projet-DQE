"""
Dimensionnement des semelles (fondations superficielles).
Signature figée -- corps à remplir avec la formule du technicien BTP.
"""

from ..validators import EntreeInvalide


def dimensionner_semelle(charge_poteau, taux_travail_sol=None):
    """
    Propose des dimensions de semelle à partir de la charge du poteau
    qu'elle supporte et de la portance du sol.

    Paramètres
    ----------
    charge_poteau : float
        Charge transmise par le poteau à la semelle, en kN.
    taux_travail_sol : float, optionnel
        Contrainte admissible du sol, en bars ou kN/m² (à préciser avec
        le technicien BTP -- dépend d'une étude de sol, potentiellement
        variable par projet plutôt qu'une constante globale).

    Retour
    ------
    dict
        {
            "longueur_m": float,
            "largeur_m": float,
            "hauteur_cm": float,
        }

    TODO (technicien BTP) :
    - confirmer si le taux de travail du sol est une donnée d'entrée
      par projet (probable, dépend de l'étude géotechnique) plutôt
      qu'une constante fixe dans constantes.py
    - confirmer la formule de dimensionnement (semelle isolée carrée
      par défaut, ou rectangulaire selon le cas ?)
    """
    if charge_poteau is None or charge_poteau <= 0:
        raise EntreeInvalide("La charge du poteau doit être positive.")
    if taux_travail_sol is None:
        raise NotImplementedError(
            "Le taux de travail du sol doit être fourni (donnée projet, "
            "pas une constante globale -- à confirmer avec le technicien BTP)"
        )

    # TODO : formule réelle à injecter
    raise NotImplementedError("Formule à injecter -- en attente du technicien BTP")