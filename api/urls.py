from django.urls import path, include
from rest_framework.routers import DefaultRouter
from rest_framework_simplejwt.views import TokenObtainPairView, TokenRefreshView
from projets.views import (
    ProjetViewSet,
    ElementStructurelViewSet,
    CoucheChargeViewSet,
    PosteComplementaireViewSet,
    AssistantStructurerView,
    AssistantExpliquerView,
    AssistantSuggererPosteView,
    EntrepriseParametresView,
)
from projets.auth_views import (
    InscriptionEntrepriseView,
    InviterUtilisateurView,
    ActiverCompteView,
    MoiView,
    MembresEntrepriseView,
    DesactiverUtilisateurView,
    ChangerMotDePasseView,
    DemanderReinitialisationView,
    ConfirmerReinitialisationView,
    LogoutView,
)

router = DefaultRouter()
router.register(r"projets", ProjetViewSet, basename="projet")
router.register(r"elements", ElementStructurelViewSet, basename="element")
router.register(r"couches-charges", CoucheChargeViewSet, basename="couchecharge")
router.register(
    r"postes-complementaires",
    PosteComplementaireViewSet,
    basename="postecomplementaire",
)

urlpatterns = [
    # Routes exactes attendues par test_ai.py
    path(
        "assistant/structurer-projet/",
        AssistantStructurerView.as_view(),
        name="assistant-structurer-projet",
    ),
    path(
        "assistant/expliquer-element/",
        AssistantExpliquerView.as_view(),
        name="assistant-expliquer-element",
    ),
    # Aliases
    path(
        "assistant/structurer/",
        AssistantStructurerView.as_view(),
        name="assistant-structurer",
    ),
    path(
        "assistant/expliquer/",
        AssistantExpliquerView.as_view(),
        name="assistant-expliquer",
    ),
    # DQE avec tiret et underscore
    path(
        "projets/<int:pk>/generer_dqe/",
        ProjetViewSet.as_view({"get": "generer_dqe", "post": "generer_dqe"}),
    ),
    path(
        "projets/<int:pk>/generer-dqe/",
        ProjetViewSet.as_view({"get": "generer_dqe", "post": "generer_dqe"}),
        name="projet-generer-dqe",
    ),
    # Assistant IA — Suggestion de poste complémentaire
    path(
        "assistant/suggerer-poste/",
        AssistantSuggererPosteView.as_view(),
        name="assistant-suggerer-poste",
    ),
    path(
        "entreprise/",
        EntrepriseParametresView.as_view(),
        name="entreprise-parametres",
    ),

    # --- Auth JWT (sprint Comptes & Permissions) ---
    path("auth/token/", TokenObtainPairView.as_view(), name="token-obtain-pair"),
    path("auth/token/refresh/", TokenRefreshView.as_view(), name="token-refresh"),
    path("auth/logout/", LogoutView.as_view(), name="auth-logout"),

    # --- Comptes & cabinet ---
    path("auth/moi/", MoiView.as_view(), name="auth-moi"),
    path("auth/inscription/", InscriptionEntrepriseView.as_view(), name="auth-inscription"),
    path("auth/inviter/", InviterUtilisateurView.as_view(), name="auth-inviter"),
    path("auth/activer/", ActiverCompteView.as_view(), name="auth-activer"),
    path("auth/membres/", MembresEntrepriseView.as_view(), name="auth-membres"),
    path("auth/membres/<int:user_id>/desactiver/", DesactiverUtilisateurView.as_view(), name="auth-desactiver-membre"),

    # --- Mot de passe ---
    path("auth/changer-mot-de-passe/", ChangerMotDePasseView.as_view(), name="auth-changer-mdp"),
    path("auth/mot-de-passe-oublie/", DemanderReinitialisationView.as_view(), name="auth-mdp-oublie"),
    path("auth/reinitialiser-mot-de-passe/", ConfirmerReinitialisationView.as_view(), name="auth-reinitialiser-mdp"),

    path("", include(router.urls)),
]