"""
Routeur DRF principal.

Endpoints exposés :
- /api/projets/                      GET, POST
- /api/projets/{id}/                 GET, PUT, PATCH, DELETE
- /api/projets/{id}/recalculer/      POST
- /api/projets/{id}/generer_dqe/     POST
- /api/elements/                     GET, POST  (filtrable par ?projet=<id>)
- /api/elements/{id}/                GET, PUT, PATCH, DELETE
- /api/elements/{id}/calculer/       POST
- /api/elements/{id}/valider/        POST
"""

from rest_framework.routers import DefaultRouter

from projets.views import ProjetViewSet, ElementStructurelViewSet

router = DefaultRouter()
router.register(r"projets", ProjetViewSet, basename="projet")
router.register(r"elements", ElementStructurelViewSet, basename="element")

urlpatterns = router.urls