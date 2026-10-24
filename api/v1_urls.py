"""Routes canoniques v1. Les vues métier sont partagées avec l'API legacy."""

from django.urls import include, path
from rest_framework_simplejwt.views import TokenObtainPairView, TokenRefreshView, TokenVerifyView

from projets.views import MeView


urlpatterns = [
    path("api/v1/token/", TokenObtainPairView.as_view(), name="token_obtain_pair"),
    path("api/v1/token/refresh/", TokenRefreshView.as_view(), name="token_refresh"),
    path("api/v1/token/verify/", TokenVerifyView.as_view(), name="token_verify"),
    path("api/v1/me/", MeView.as_view(), name="user-me"),
    path("api/v1/", include("api.urls")),
]
