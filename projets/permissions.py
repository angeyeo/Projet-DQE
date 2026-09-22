"""
Permissions du sprint "Comptes & Permissions".

Principe général : tant qu'un utilisateur authentifié n'a pas encore de
Profil (compte créé avant ce sprint, ou onboarding pas encore fait), on
n'applique AUCUNE restriction supplémentaire -- exactement le comportement
qui existait avant. Ça évite de casser les comptes de test existants
(create_user sans Profil, utilisés par la suite de tests IA) le temps que
l'onboarding réel (création de Profil à l'inscription) soit en place.
"""

import os

from rest_framework.permissions import BasePermission


def _demo_mode() -> bool:
    return os.getenv("DEMO_MODE", "False").lower() == "true"


def _entreprise_de(obj):
    """Retrouve l'entreprise propriétaire d'un objet, qu'il porte le champ
    directement (Projet, EntrepriseParametres) ou via une relation `projet`
    (ElementStructurel, CoucheCharge, PosteComplementaire)."""
    if hasattr(obj, "entreprise"):
        return obj.entreprise
    projet = getattr(obj, "projet", None)
    if projet is not None:
        return getattr(projet, "entreprise", None)
    return None


class EstAuthentifieOuDemoMode(BasePermission):
    """Permission par défaut de tout le projet. Généralise à toutes les vues
    ce que chaque vue IA faisait déjà individuellement avant ce sprint."""

    def has_permission(self, request, view):
        if _demo_mode():
            return True
        return bool(request.user and request.user.is_authenticated)


class EstMembreEntreprise(BasePermission):
    """Isolation inter-cabinets au niveau objet : un utilisateur ne peut
    accéder qu'aux objets de sa propre entreprise. Pas de restriction si
    DEMO_MODE, si l'utilisateur n'a pas encore de Profil, ou si l'objet
    lui-même n'a pas encore d'entreprise (données legacy)."""

    message = "Cet objet appartient à une autre entreprise."

    def has_object_permission(self, request, view, obj):
        if _demo_mode():
            return True
        if not request.user or not request.user.is_authenticated:
            return False

        profil = getattr(request.user, "profil", None)
        if profil is None:
            return True

        entreprise_obj = _entreprise_de(obj)
        if entreprise_obj is None:
            return True

        return profil.entreprise_id == entreprise_obj.id


class PeutValider(BasePermission):
    """Verrou d'ingénieur : seul un compte ingénieur ou admin peut valider/
    verrouiller un élément (Étape 3). Un technicien peut tout faire sauf ça."""

    message = "Seul un compte Ingénieur ou Admin peut valider un élément."

    def has_permission(self, request, view):
        if _demo_mode():
            return True
        if not request.user or not request.user.is_authenticated:
            return False

        profil = getattr(request.user, "profil", None)
        if profil is None:
            return True  # pas encore de profil -> comportement legacy

        return profil.peut_valider


class EstAdminEntreprise(BasePermission):
    """Réservé aux comptes Admin du cabinet -- gestion des utilisateurs,
    paramètres entreprise. Pas de fallback permissif ici : la gestion des
    comptes est une fonctionnalité nouvelle, sans utilisateur legacy à
    ménager."""

    message = "Seul un compte Admin peut effectuer cette action."

    def has_permission(self, request, view):
        if _demo_mode():
            return True
        if not request.user or not request.user.is_authenticated:
            return False

        profil = getattr(request.user, "profil", None)
        return bool(profil and profil.est_admin)