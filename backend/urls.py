from django.contrib import admin
from django.urls import path, include
from projets.views import AssistantStructurerView, AssistantExpliquerView

urlpatterns = [
    path("admin/", admin.site.urls),
    path("api/", include("api.urls")),
    # Routes directes pour les tests de l'Assistant IA (sans /api/)
    path("assistant/structurer/", AssistantStructurerView.as_view(), name="assistant-structurer"),
    path("assistant/expliquer/", AssistantExpliquerView.as_view(), name="assistant-expliquer"),
    path("assistant/structurer", AssistantStructurerView.as_view()),
    path("assistant/expliquer", AssistantExpliquerView.as_view()),
]