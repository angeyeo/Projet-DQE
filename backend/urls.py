from django.contrib import admin
from django.conf import settings
from django.conf.urls.static import static
from django.urls import path, include
from rest_framework_simplejwt.views import (
    TokenObtainPairView,
    TokenRefreshView,
    TokenVerifyView,
)
from projets.views import (
    AssistantStructurerView, 
    AssistantExpliquerView, 
    MeView,
    ProjetViewSet
)

urlpatterns = [
    path("admin/", admin.site.urls),
    
    # Endpoints d'authentification JWT
    path("api/token/", TokenObtainPairView.as_view(), name="token_obtain_pair"),
    path("api/token/refresh/", TokenRefreshView.as_view(), name="token_refresh"),
    path("api/token/verify/", TokenVerifyView.as_view(), name="token_verify"),
    
    # Endpoint utilisateur courant
    path("api/me/", MeView.as_view(), name="user-me"),
    
    # Routes principales de l'API (projets, éléments, etc.)
    path("api/", include("api.urls")),
    
    # Routes directes pour les tests de l'Assistant IA & Vision
    path("assistant/structurer/", AssistantStructurerView.as_view(), name="assistant-structurer"),
    path("assistant/expliquer/", AssistantExpliquerView.as_view(), name="assistant-expliquer"),
    path("assistant/structurer", AssistantStructurerView.as_view()),
    path("assistant/expliquer", AssistantExpliquerView.as_view()),
    path("assistant/vision/", ProjetViewSet.as_view({"post": "analyser_plan_image"}), name="assistant-vision-direct"),
    path("assistant/vision", ProjetViewSet.as_view({"post": "analyser_plan_image"})),
]

# Gestion des fichiers médias en mode développement
urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)