"""Aide commune aux tests d'API : authentification multi-tenant.

Depuis le sprint Comptes & Permissions, les endpoints projets/éléments
exigent un utilisateur authentifié rattaché à un cabinet
(permissions.EstMembreEntreprise). Les tests d'API ne doivent donc pas
dépendre d'un DEMO_MODE lu dans le .env local : ils s'authentifient
explicitement avec ce helper.
"""

from django.contrib.auth import get_user_model

from projets.models import EntrepriseParametres, Profil

User = get_user_model()


def authentifier_membre_cabinet(client, username="membre_cabinet_test", role=Profil.Role.INGENIEUR):
    """Crée un cabinet + un utilisateur avec Profil, authentifie `client`.

    Retourne (utilisateur, entreprise) ; les projets créés par le test
    doivent recevoir `entreprise=entreprise` pour rester visibles (le
    queryset de ProjetViewSet est filtré par cabinet).
    """
    entreprise = EntrepriseParametres.objects.create(nom=f"Cabinet {username}")
    utilisateur = User.objects.create_user(username=username, password="MotDePasseTest2026!")
    Profil.objects.create(utilisateur=utilisateur, entreprise=entreprise, role=role)
    client.force_authenticate(user=utilisateur)
    return utilisateur, entreprise
