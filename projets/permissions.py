"""
Permissions DRF du projet DQE.

Principe : l'isolation entre cabinets repose sur le Profil de
l'utilisateur (Profil.entreprise -> EntrepriseParametres). Un utilisateur
sans Profil n'a accès à aucune donnée métier : il doit d'abord être
rattaché à un cabinet (admin Django ou invitation).

Le DEMO_MODE (accès anonyme à toutes les vues) a été supprimé : il
ouvrait l'ensemble des projets de tous les cabinets à un visiteur non
authentifié dès que la variable d'environnement valait "True".
"""

from rest_framework import permissions

ROLE_ADMIN = 'admin'
ROLE_INGENIEUR = 'ingenieur'


def entreprise_de(user):
    """Cabinet (EntrepriseParametres) de l'utilisateur, ou None."""
    if not (user and user.is_authenticated):
        return None
    profil = getattr(user, 'profil', None)
    return getattr(profil, 'entreprise', None) if profil else None


class EstMembreEntreprise(permissions.BasePermission):
    """Utilisateur authentifié ET rattaché à un cabinet."""

    message = (
        "Votre compte n'est rattaché à aucun cabinet : contactez "
        "l'administrateur de votre cabinet."
    )

    def has_permission(self, request, view):
        return entreprise_de(request.user) is not None


class EstAdminCabinet(permissions.BasePermission):
    """Accès réservé à l'administrateur du cabinet."""

    message = "Action réservée à l'administrateur du cabinet."

    def has_permission(self, request, view):
        if entreprise_de(request.user) is None:
            return False
        return request.user.profil.role == ROLE_ADMIN


class PeutValiderElement(permissions.BasePermission):
    """Seuls les admins et ingénieurs peuvent valider / déverrouiller."""

    message = "Seul un ingénieur ou l'administrateur du cabinet peut valider ou déverrouiller un calcul."

    def has_permission(self, request, view):
        if entreprise_de(request.user) is None:
            return False
        return request.user.profil.role in (ROLE_ADMIN, ROLE_INGENIEUR)


class EstStaff(permissions.BasePermission):
    """Équipe interne du produit (is_staff) -- analytics commerciales."""

    message = "Accès réservé à l'équipe interne."

    def has_permission(self, request, view):
        return bool(request.user and request.user.is_authenticated and request.user.is_staff)


# Alias conservé pour auth_views.py
class EstAdminEntreprise(EstAdminCabinet):
    pass
