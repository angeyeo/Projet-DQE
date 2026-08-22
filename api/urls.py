from django.urls import path, include
from rest_framework.routers import DefaultRouter
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
    path("", include(router.urls)),
]