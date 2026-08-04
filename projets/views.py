"""
Vues DRF.

Points clés :
- POST /elements/{id}/calculer/  -> déclenche le calcul via le moteur
- POST /elements/{id}/valider/   -> verrou logiciel : c'est la SEULE
  façon de passer un élément au statut 'valide'. Une fois validé, il
  n'est plus recalculé automatiquement (voir services.recalculer_projet).
- GET  /projets/{id}/generer_dqe/?export=pdf|excel -> génère et
  retourne le DQE (méthode GET, pas POST : c'est un téléchargement de
  fichier, cohérent avec la convention utilisée par le Dev 4 dans son
  walkthrough -- un lien/URL de téléchargement est plus naturel en GET
  qu'en POST pour ce cas d'usage).

MODIFIÉ (Ange) : generer_dqe appelait encore l'ancien TODO/squelette
("Génération du DQE à brancher (Dev 4)") -- le travail réel du Dev 4
(services/dqe_calculator.py, services/dqe_exporters.py) existait dans
le repo mais n'était jamais appelé depuis cette vue. Branché ici.
"""

from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from django.http import HttpResponse

from .models import Projet, ElementStructurel, PosteMainDoeuvre
from .serializers import (
    ProjetSerializer,
    ElementStructurelSerializer,
    ElementValidationSerializer,
    PosteMainDoeuvreSerializer,
)
from .services.calculations import calculer_element, recalculer_projet, CalculNonDisponible
from .services.dqe_calculator import calculer_projet_dqe
from .services.dqe_exporters import exporter_dqe_pdf, exporter_dqe_excel
from moteur_calcul.validators import EntreeInvalide


class ProjetViewSet(viewsets.ModelViewSet):
    queryset = Projet.objects.all()
    serializer_class = ProjetSerializer

    @action(detail=True, methods=["post"])
    def recalculer(self, request, pk=None):
        """Relance le calcul pour tous les éléments non-validés du projet."""
        projet = self.get_object()
        resultats = recalculer_projet(projet)
        return Response(resultats, status=status.HTTP_200_OK)

    @action(detail=True, methods=["get"])
    def generer_dqe(self, request, pk=None):
        """
        Génère le DQE (JSON par défaut, ou fichier PDF/Excel via
        ?export=pdf | ?export=excel) une fois tous les éléments validés.
        """
        projet = self.get_object()
        elements_non_valides = projet.elements.exclude(
            statut=ElementStructurel.Statut.VALIDE
        )
        if elements_non_valides.exists():
            return Response(
                {
                    "erreur": "Tous les éléments doivent être validés avant de générer le DQE.",
                    "elements_en_attente": list(
                        elements_non_valides.values_list("identifiant", flat=True)
                    ),
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        if not projet.elements.exists():
            return Response(
                {"erreur": "Le projet ne contient aucun élément structurel."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        export_format = request.query_params.get("export")

        try:
            dqe_data = calculer_projet_dqe(projet)
        except Exception as exc:
            return Response(
                {"erreur": "Erreur inattendue lors du calcul du DQE.", "detail": str(exc)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

        # Pas de paramètre export -> retourne la structure JSON brute
        # (utile pour debug/tests, comme on vient de le faire).
        if export_format is None:
            return Response(dqe_data, status=status.HTTP_200_OK)

        if export_format not in ("pdf", "excel"):
            return Response(
                {"erreur": f"Format d'export non pris en charge : '{export_format}'. Utilisez 'pdf' ou 'excel'."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        nom_fichier_base = f"DQE_{projet.nom.replace(' ', '_')}_{projet.id}"

        try:
            if export_format == "pdf":
                buffer = exporter_dqe_pdf(dqe_data)
                response = HttpResponse(buffer.getvalue(), content_type="application/pdf")
                response["Content-Disposition"] = f'attachment; filename="{nom_fichier_base}.pdf"'
            else:  # excel
                buffer = exporter_dqe_excel(dqe_data)
                response = HttpResponse(
                    buffer.getvalue(),
                    content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                )
                response["Content-Disposition"] = f'attachment; filename="{nom_fichier_base}.xlsx"'
        except Exception as exc:
            return Response(
                {"erreur": "Erreur lors de la génération du fichier.", "detail": str(exc)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

        return response


class ElementStructurelViewSet(viewsets.ModelViewSet):
    queryset = ElementStructurel.objects.all()
    serializer_class = ElementStructurelSerializer

    def get_queryset(self):
        queryset = super().get_queryset()
        projet_id = self.request.query_params.get("projet")
        if projet_id:
            queryset = queryset.filter(projet_id=projet_id)
        return queryset

    @action(detail=True, methods=["post"])
    def calculer(self, request, pk=None):
        """Déclenche le calcul pour cet élément et stocke le résultat proposé."""
        element = self.get_object()
        try:
            resultat = calculer_element(element)
        except CalculNonDisponible as exc:
            return Response(
                {"erreur": "Moteur de calcul pas encore disponible", "detail": str(exc)},
                status=status.HTTP_503_SERVICE_UNAVAILABLE,
            )
        except EntreeInvalide as exc:
            return Response({"erreur": str(exc)}, status=status.HTTP_400_BAD_REQUEST)

        element.resultat_calcul = resultat
        element.save(update_fields=["resultat_calcul", "date_modification"])
        return Response(ElementStructurelSerializer(element).data)

    @action(detail=True, methods=["post"])
    def valider(self, request, pk=None):
        """
        Verrou logiciel : seule cette action peut faire passer un élément
        au statut VALIDE. Le frontend ne doit jamais écrire directement
        le champ 'statut' via l'update standard du ModelViewSet.
        """
        element = self.get_object()
        serializer = ElementValidationSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        resultat_valide = serializer.validated_data.get(
            "resultat_valide", element.resultat_calcul
        )
        if resultat_valide is None:
            return Response(
                {"erreur": "Aucun résultat de calcul disponible à valider."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        element.resultat_valide = resultat_valide
        element.statut = ElementStructurel.Statut.VALIDE
        element.save(update_fields=["resultat_valide", "statut", "date_modification"])
        return Response(ElementStructurelSerializer(element).data)

    def perform_update(self, serializer):
        """
        Si un élément déjà VALIDE est modifié via l'update standard,
        on le repasse automatiquement à MODIFIE -- il devra être
        revalidé explicitement (verrou logiciel, voir docstring plus haut).
        """
        instance = serializer.instance
        if instance.statut == ElementStructurel.Statut.VALIDE:
            serializer.save(statut=ElementStructurel.Statut.MODIFIE)
        else:
            serializer.save()


class PosteMainDoeuvreViewSet(viewsets.ModelViewSet):
    """
    Postes de main d'œuvre : toujours saisis manuellement par
    l'ingénieur, jamais calculés automatiquement (voir docstring du
    modèle PosteMainDoeuvre).
    """

    queryset = PosteMainDoeuvre.objects.all()
    serializer_class = PosteMainDoeuvreSerializer

    def get_queryset(self):
        queryset = super().get_queryset()
        projet_id = self.request.query_params.get("projet")
        if projet_id:
            queryset = queryset.filter(projet_id=projet_id)
        return queryset