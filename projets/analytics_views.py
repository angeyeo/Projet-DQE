"""Endpoints analytics (lecture seule).

GET /api/analytics/cabinet/          -> membre du cabinet (son cabinet uniquement)
GET /api/analytics/projets/<id>/     -> membre du cabinet propriétaire du projet
GET /api/analytics/staff/            -> équipe interne (is_staff) uniquement
"""

from django.shortcuts import get_object_or_404
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import Projet
from .permissions import EstMembreEntreprise, EstStaff
from .services.analytics import analytics_cabinet, analytics_projet, analytics_staff


class AnalyticsCabinetView(APIView):
    permission_classes = [EstMembreEntreprise]

    def get(self, request):
        return Response(analytics_cabinet(request.user.profil.entreprise))


class AnalyticsProjetView(APIView):
    permission_classes = [EstMembreEntreprise]

    def get(self, request, pk):
        projet = get_object_or_404(Projet, pk=pk, entreprise=request.user.profil.entreprise)
        return Response(analytics_projet(projet))


class AnalyticsStaffView(APIView):
    permission_classes = [EstStaff]

    def get(self, request):
        return Response(analytics_staff())
