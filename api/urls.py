from django.urls import path, include
from rest_framework.routers import DefaultRouter
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework import status
from django.contrib.auth.models import User
from django.contrib.auth.tokens import default_token_generator
from django.utils.http import urlsafe_base64_encode
from django.utils.encoding import force_bytes

from projets.views import (
    ProjetViewSet,
    ElementStructurelViewSet,
    CoucheChargeViewSet,
    PosteComplementaireViewSet,
    AssistantStructurerView,
    AssistantExpliquerView,
    AssistantSuggererPosteView,
    EntrepriseParametresView,
    AdminUserManagementViewSet,
    gerer_profil_utilisateur,
    changer_mot_de_passe
)
from projets.auth_views import (
    InscriptionEntrepriseView,
    InviterUtilisateurView,
    ActiverCompteView,
    MembresEntrepriseView,
    DesactiverUtilisateurView,
    ChangerMotDePasseView,
    DemanderReinitialisationView,
    ConfirmerReinitialisationView,
    LogoutView,
)

@api_view(['POST'])
@permission_classes([AllowAny])
def demander_reinitialisation_mdp(request):
    email = request.data.get('email')
    try:
        user = User.objects.get(email=email)
        token = default_token_generator.make_token(user)
        uid = urlsafe_base64_encode(force_bytes(user.pk))
        reset_url = f"http://localhost:5173/reset-password/{uid}/{token}"
        return Response({
            "detail": "Instructions envoyées.",
            "reset_url": reset_url
        }, status=status.HTTP_200_OK)
    except User.DoesNotExist:
        return Response({
            "detail": "Instructions de réinitialisation envoyées si le compte existe.",
            "reset_url": ""
        }, status=status.HTTP_200_OK)

router = DefaultRouter()
router.register(r"projets", ProjetViewSet, basename="projet")
router.register(r"elements", ElementStructurelViewSet, basename="element")
router.register(r"couches-charges", CoucheChargeViewSet, basename="couchecharge")
router.register(r"charges", CoucheChargeViewSet, basename="charge")
router.register(
    r"postes-complementaires",
    PosteComplementaireViewSet,
    basename="postecomplementaire",
)
router.register(r"admin/utilisateurs", AdminUserManagementViewSet, basename="admin-utilisateurs")

urlpatterns = [
    # Assistant IA & Divers
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
    path(
        "assistant/suggerer-poste/",
        AssistantSuggererPosteView.as_view(),
        name="assistant-suggerer-poste",
    ),

    # Paramètres Entreprise
    path(
        "entreprise/",
        EntrepriseParametresView.as_view(),
        name="entreprise-parametres",
    ),
    path(
        "parametres/",
        EntrepriseParametresView.as_view(),
        name="parametres-entreprise",
    ),

    # Authentification / Profil & Mot de passe
    path(
        "auth/profil/",
        gerer_profil_utilisateur,
        name="profil-utilisateur",
    ),
    path(
        "auth/change-password/",
        changer_mot_de_passe,
        name="change-password",
    ),
    path("auth/forgot-password/", demander_reinitialisation_mdp, name="forgot-password"),
    
    # Router DRF global (gère automatiquement /projets/{pk}/analyser_plan_image/ et /projets/{pk}/generer_dqe/)
    path("", include(router.urls)),
]