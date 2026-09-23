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
    path("assistant/structurer-projet/", AssistantStructurerView.as_view(), name="assistant-structurer-projet"),
    path("assistant/expliquer-element/", AssistantExpliquerView.as_view(), name="assistant-expliquer-element"),
    path("assistant/structurer/", AssistantStructurerView.as_view(), name="assistant-structurer"),
    path("assistant/expliquer/", AssistantExpliquerView.as_view(), name="assistant-expliquer"),
    path("assistant/suggerer-poste/", AssistantSuggererPosteView.as_view(), name="assistant-suggerer-poste"),

    # Paramètres Entreprise
    path("entreprise/", EntrepriseParametresView.as_view(), name="entreprise-parametres"),
    path("parametres/", EntrepriseParametresView.as_view(), name="parametres-entreprise"),

    # Authentification / JWT & Flux Complet Sprint 2
    path("auth/register/", InscriptionEntrepriseView.as_view(), name="auth-register"),
    path("auth/login/", TokenObtainPairView.as_view(), name="auth-login"),
    path("auth/token/", TokenObtainPairView.as_view(), name="token-obtain-pair"),
    path("auth/token/refresh/", TokenRefreshView.as_view(), name="token-refresh"),
    path("auth/invite/", InviterUtilisateurView.as_view(), name="auth-invite"),
    path("auth/activate/", ActiverCompteView.as_view(), name="auth-activate"),
    path("auth/members/", MembresEntrepriseView.as_view(), name="auth-members"),
    path("auth/members/<int:pk>/desactiver/", DesactiverUtilisateurView.as_view(), name="auth-desactiver"),
    path("auth/profil/", gerer_profil_utilisateur, name="profil-utilisateur"),
    path("auth/change-password/", ChangerMotDePasseView.as_view(), name="auth-password-change"),
    path("auth/password-reset-request/", DemanderReinitialisationView.as_view(), name="auth-password-reset-request"),
    path("auth/password-reset-confirm/", ConfirmerReinitialisationView.as_view(), name="auth-password-reset-confirm"),
    path("auth/logout/", LogoutView.as_view(), name="auth-logout"),
    path("auth/forgot-password/", demander_reinitialisation_mdp, name="forgot-password"),

    # Router DRF global
    path("", include(router.urls)),

    # Routes d'authentification / Membres (Support français et anglais pour stopper les 404)
    path("auth/register/", InscriptionEntrepriseView.as_view(), name="auth-register"),
    path("auth/invite/", InviterUtilisateurView.as_view(), name="auth-invite"),
    path("auth/activate/", ActiverCompteView.as_view(), name="auth-activate"),
    path("auth/members/", MembresEntrepriseView.as_view(), name="auth-members"),
    path("auth/membres/", MembresEntrepriseView.as_view(), name="auth-membres-fr"), # <--- Ajouté ici
    path("auth/members/<int:pk>/desactiver/", DesactiverUtilisateurView.as_view(), name="auth-desactiver"),
    path("auth/membres/<int:pk>/desactiver/", DesactiverUtilisateurView.as_view(), name="auth-desactiver-fr"), # <--- Ajouté ici
]