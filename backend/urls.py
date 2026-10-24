from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.urls import include, path
from drf_spectacular.views import SpectacularAPIView, SpectacularSwaggerView

# Toutes les routes métier sont sous /api/ (api/urls.py). Les anciens
# alias à la racine (/auth/..., /assistant/...) ajoutés "pour stopper les
# 404 des tests" ont été retirés : ils doublaient la surface d'API, et
# /assistant/vision pointait vers une action de détail sans identifiant
# de projet (toujours en erreur).
urlpatterns = [
    path("admin/", admin.site.urls),
    # La documentation est réservée au développement jusqu'à validation
    # d'une politique d'accès pour les environnements déployés.
    *(
        [
            path(
                "api/schema/",
                SpectacularAPIView.as_view(urlconf="api.legacy_urls"),
                name="schema",
            ),
            path("api/docs/", SpectacularSwaggerView.as_view(url_name="schema"), name="swagger-ui"),
            path(
                "api/v1/schema/",
                SpectacularAPIView.as_view(urlconf="api.v1_urls"),
                name="schema-v1",
            ),
            path(
                "api/v1/docs/",
                SpectacularSwaggerView.as_view(url_name="schema-v1"),
                name="swagger-ui-v1",
            ),
        ]
        if settings.DEBUG
        else []
    ),
    # L'URLconf legacy conserve ses noms reverse() historiques sans namespace.
    path("", include("api.legacy_urls")),
    # La v1 réutilise le même api.urls et expose ses reverse() sous api_v1:.
    path("", include(("api.v1_urls", "api_v1"), namespace="api_v1")),
]

# Fichiers médias servis par Django uniquement en développement.
if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
