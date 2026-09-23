from rest_framework import permissions


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
        return bool(profil and profil.role == 'ADMIN')


class PeutValiderElement(permissions.BasePermission):
    """
    Seuls les Admins et Ingénieurs peuvent valider/verrouiller les calculs.
    """
    def has_permission(self, request, view):
        if not (request.user and request.user.is_authenticated):
            return False
            
        profil = getattr(request.user, 'profil', None)
        return bool(profil and profil.role in ['ADMIN', 'INGENIEUR'])