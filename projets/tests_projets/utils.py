"""Outils communs aux tests : un cabinet, un membre authentifié, un barème.

Depuis la suppression du DEMO_MODE, toute vue métier exige un utilisateur
authentifié ET rattaché à un cabinet -- les tests d'API doivent donc
s'authentifier comme le ferait le frontend.
"""

from django.contrib.auth.models import User

from projets.models import EntrepriseParametres, Profil

# Barème explicite utilisé par les tests de DQE : ce sont des valeurs DE
# TEST, fournies par le test lui-même (le calculateur n'a plus de prix
# par défaut). Mêmes montants que le DQE de référence CIMBAT pour garder
# des calculs de vérification lisibles.
BAREME_TEST = {
    "beton_m3": 100000,
    "acier_kg": 800,
    "coffrage_m2": 12000,
    "agglos_15_pleins_m2": 9000,
    "agglos_15_creux_m2": 8000,
    "agglos_10_creux_m2": 6000,
    "enduit_m2": 3500,
}


def creer_cabinet(nom="Cabinet Test", bareme=None):
    return EntrepriseParametres.objects.create(nom=nom, prix_unitaires=dict(bareme or {}))


def creer_membre(entreprise, username="membre", role=Profil.Role.INGENIEUR, **kwargs):
    user = User.objects.create_user(username=username, password="MotDePasse-Test-2026!", **kwargs)
    Profil.objects.create(utilisateur=user, entreprise=entreprise, role=role)
    return user


def authentifier(test_case, role=Profil.Role.INGENIEUR, bareme=None, nom_cabinet="Cabinet Test"):
    """Crée cabinet + membre, authentifie test_case.client, renvoie (user, cabinet)."""
    cabinet = creer_cabinet(nom_cabinet, bareme)
    user = creer_membre(cabinet, username=f"{role}_{nom_cabinet}".replace(" ", "_").lower(), role=role)
    test_case.client.force_authenticate(user=user)
    return user, cabinet
