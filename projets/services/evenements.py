"""
Enregistrement des événements produit (source unique des analytics
d'adoption -- voir projets.models.EvenementProduit).

Un événement n'est enregistré qu'au moment où l'action a RÉELLEMENT
réussi (après la sauvegarde en base), avec les valeurs mesurées à cet
instant. Aucune reconstitution a posteriori.
"""

from ..models import EvenementProduit
from ..permissions import entreprise_de


def enregistrer_evenement(type_evenement, *, utilisateur=None, entreprise=None, projet=None, **donnees):
    if entreprise is None:
        if projet is not None and projet.entreprise_id:
            entreprise = projet.entreprise
        else:
            entreprise = entreprise_de(utilisateur)
    if utilisateur is not None and not getattr(utilisateur, "is_authenticated", False):
        utilisateur = None
    return EvenementProduit.objects.create(
        type=type_evenement,
        utilisateur=utilisateur,
        entreprise=entreprise,
        projet=projet,
        donnees=donnees,
    )
