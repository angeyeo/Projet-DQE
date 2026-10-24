"""Endpoints analytics (lecture seule).

GET /api/analytics/cabinet/          -> membre du cabinet (son cabinet uniquement)
GET /api/analytics/projets/<id>/     -> membre du cabinet propriétaire du projet
GET /api/analytics/staff/            -> équipe interne (is_staff) uniquement
"""

from django.shortcuts import get_object_or_404
from rest_framework.response import Response
from rest_framework.views import APIView
from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import OpenApiResponse, extend_schema

from .models import Projet
from .permissions import EstMembreEntreprise, EstStaff
from .services.analytics import analytics_cabinet, analytics_projet, analytics_staff


class AnalyticsCabinetView(APIView):
    permission_classes = [EstMembreEntreprise]

    @extend_schema(responses={200: OpenApiResponse(response=OpenApiTypes.OBJECT, description="Indicateurs du cabinet connecté uniquement.")}, tags=["Analytics"])
    def get(self, request):
        return Response(analytics_cabinet(request.user.profil.entreprise))


class AnalyticsProjetView(APIView):
    permission_classes = [EstMembreEntreprise]

    @extend_schema(responses={200: OpenApiResponse(response=OpenApiTypes.OBJECT, description="Indicateurs du projet du cabinet courant."),
                              404: OpenApiResponse(description="Projet absent du cabinet courant.")}, tags=["Analytics"])
    def get(self, request, pk):
        projet = get_object_or_404(Projet, pk=pk, entreprise=request.user.profil.entreprise)
        return Response(analytics_projet(projet))


class AnalyticsStaffView(APIView):
    permission_classes = [EstStaff]

    @extend_schema(responses={200: OpenApiResponse(response=OpenApiTypes.OBJECT, description="Indicateurs internes accessibles au staff.")}, tags=["Analytics"])
    def get(self, request):
        return Response(analytics_staff())
