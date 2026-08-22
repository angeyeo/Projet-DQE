from django.urls import path, include
from rest_framework.routers import DefaultRouter
from projets.views import (
    ProjetViewSet,
    ElementStructurelViewSet,
    CoucheChargeViewSet,
    PosteComplementaireViewSet,
    AssistantStructurerView,
    AssistantExpliquerView,
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
    # Routes Assistant IA
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
    # Support DQE (underscore et tiret)
    path(
        "projets/<int:pk>/generer_dqe/",
        ProjetViewSet.as_view({"get": "generer_dqe", "post": "generer_dqe"}),
    ),
    path(
        "projets/<int:pk>/generer-dqe/",
        ProjetViewSet.as_view({"get": "generer_dqe", "post": "generer_dqe"}),
        name="projet-generer-dqe",
    ),
    # Support Analyse Plan Vision (underscore et tiret)
    path(
        "projets/<int:pk>/analyser_plan_image/",
        ProjetViewSet.as_view({"post": "analyser_plan_image"}),
        name="projet-analyser-plan-image",
    ),
    path(
        "projets/<int:pk>/analyser-plan-image/",
        ProjetViewSet.as_view({"post": "analyser_plan_image"}),
    ),
    path("", include(router.urls)),
]