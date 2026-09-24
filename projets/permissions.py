from rest_framework import permissions
from rest_framework.permissions import BasePermission

ROLE_ADMIN = 'admin'
ROLE_INGENIEUR = 'ingenieur'

class EstMembreEntreprise(permissions.BasePermission):
    """
    Vérifie que l'utilisateur est authentifié et rattaché à un cabinet d'ingénierie.
    """
    def has_permission(self, request, view):
        # 1. Toujours vérifier d'abord que l'utilisateur est connecté
        if not (request.user and request.user.is_authenticated):
            return False

        # 2. Vérifier de manière sécurisée l'existence du profil et du cabinet
        profil = getattr(request.user, 'profil', None)
        return bool(profil and profil.entreprise is not None)


class EstAdminCabinet(permissions.BasePermission):
    """
    Accès réservé à l'Administrateur du cabinet.
    """
    def has_permission(self, request, view):
        if not (request.user and request.user.is_authenticated):
            return False
        
        profil = getattr(request.user, 'profil', None)
        return bool(profil and profil.role == ROLE_ADMIN)


class PeutValiderElement(permissions.BasePermission):
    """
    Seuls les Admins et Ingénieurs peuvent valider/verrouiller les calculs.
    """
    def has_permission(self, request, view):
        if not (request.user and request.user.is_authenticated):
            return False
            
        profil = getattr(request.user, 'profil', None)
        return bool(profil and profil.role in (ROLE_ADMIN, ROLE_INGENIEUR))

class EstAuthentifieOuDemoMode(BasePermission):
    """
    Permet l'accès si l'utilisateur est authentifié OU si le mode démo est actif.
    """
    def has_permission(self, request, view):
        # Vérifie si le mode démo est actif dans les paramètres ou les vues, 
        # ou adapte selon la logique de ton équipe :
        from django.conf import settings
        if getattr(settings, 'DEMO_MODE', False):
            return True
        return request.user and request.user.is_authenticated

class EstAdminEntreprise(EstAdminCabinet):
    """
    Alias pour compatibilité avec auth_views.py
    """
    pass