from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.urls import include, path
from rest_framework_simplejwt.views import (
    TokenObtainPairView,
    TokenRefreshView,
    TokenVerifyView,
)

from projets.views import MeView

# Toutes les routes métier sont sous /api/ (api/urls.py). Les anciens
# alias à la racine (/auth/..., /assistant/...) ajoutés "pour stopper les
# 404 des tests" ont été retirés : ils doublaient la surface d'API, et
# /assistant/vision pointait vers une action de détail sans identifiant
# de projet (toujours en erreur).
urlpatterns = [
    path("admin/", admin.site.urls),
    path("api/token/", TokenObtainPairView.as_view(), name="token_obtain_pair"),
    path("api/token/refresh/", TokenRefreshView.as_view(), name="token_refresh"),
    path("api/token/verify/", TokenVerifyView.as_view(), name="token_verify"),
    path("api/me/", MeView.as_view(), name="user-me"),
    path("api/", include("api.urls")),
]

# Fichiers médias servis par Django uniquement en développement.
if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)