"""
Vues DRF.

Points clés :
- POST /elements/{id}/calculer/  -> déclenche le calcul via le moteur
- POST /elements/{id}/valider/   -> verrou logiciel : c'est la SEULE
  façon de passer un élément au statut 'valide'. Une fois validé, il
  n'est plus recalculé automatiquement (voir services.recalculer_projet).
- POST /projets/{id}/generer_dqe/ -> squelette en attente du Dev DQE+IA,
  vérifie juste que tous les éléments sont validés avant d'appeler
  (plus tard) le module de génération du DQE.
"""

import logging
from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.throttling import ScopedRateThrottle
from rest_framework.views import APIView
from django.http import HttpResponse
from django.shortcuts import get_object_or_404
from django.utils import timezone
from django.utils.text import slugify

from .models import Projet, ElementStructurel, PosteMainDoeuvre
from .serializers import (
    ProjetSerializer,
    ElementStructurelSerializer,
    ElementValidationSerializer,
    PosteMainDoeuvreSerializer,
)
from .services.assistant_ia.parser import structurer_description_projet
from .services.assistant_ia.explanations import expliquer_resultat_element
from .services.assistant_ia.client import LLMServiceError
from .services import calculer_element, recalculer_projet, CalculNonDisponible
from moteur_calcul.validators import EntreeInvalide

from .services.dqe_calculator import calculer_projet_dqe
from .services.dqe_exporters import exporter_dqe_pdf, exporter_dqe_excel
from .services.assistant_ia import structurer_description_projet, expliquer_resultat_element

logger = logging.getLogger(__name__)

class ProjetViewSet(viewsets.ModelViewSet):
    queryset = Projet.objects.all()
    serializer_class = ProjetSerializer

    @action(detail=True, methods=["post"])
    def recalculer(self, request, pk=None):
        """Relance le calcul pour tous les éléments non-validés du projet."""
        projet = self.get_object()
        resultats = recalculer_projet(projet)
        return Response(resultats, status=status.HTTP_200_OK)

    @action(detail=True, methods=["get", "post"])
    def generer_dqe(self, request, pk=None):
        """
        Génère le devis quantitatif estimatif (DQE) du projet au format PDF ou Excel.
        Vérifie que tous les éléments structurels du projet sont validés avant l'export.
        """
        projet = self.get_object()

        # 1. Vérification que tous les éléments du projet sont validés
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

        # 2. Vérification qu'il y a au moins un élément validé ou un poste de main d'oeuvre
        has_elements = projet.elements.filter(statut=ElementStructurel.Statut.VALIDE).exists()
        has_postes = projet.postes_main_doeuvre.exists()
        if not (has_elements or has_postes):
            return Response(
                {"detail": "Aucun élément validé n'est disponible pour générer le DQE."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # 3. Récupération et validation du format d'export
        export_format = request.query_params.get("export") or request.data.get("export")
        if not export_format or export_format.lower() not in ["pdf", "excel"]:
            return Response(
                {"erreur": "Le format d'export est requis et doit être 'pdf' ou 'excel'."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        export_format = export_format.lower()

        # 4. Calcul du DQE structuré
        try:
            dqe_data = calculer_projet_dqe(projet)
        except Exception as exc:
            logger.exception("Erreur lors du calcul du DQE pour le projet %s", projet.id)
            return Response(
                {"erreur": f"Erreur lors du calcul du DQE : {str(exc)}"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

        # 5. Exportation et envoi du fichier
        try:
            date_str = timezone.now().strftime("%Y-%m-%d")
            nom_projet_slug = slugify(projet.nom).replace("-", "_") or str(projet.id)

            if export_format == "pdf":
                buffer = exporter_dqe_pdf(dqe_data)
                filename = f"DQE_{nom_projet_slug}_{date_str}.pdf"
                response = HttpResponse(buffer.read(), content_type="application/pdf")
                response["Content-Disposition"] = f'attachment; filename="{filename}"'
                return response

            elif export_format == "excel":
                buffer = exporter_dqe_excel(dqe_data)
                filename = f"DQE_{nom_projet_slug}_{date_str}.xlsx"
                response = HttpResponse(
                    buffer.read(),
                    content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
                )
                response["Content-Disposition"] = f'attachment; filename="{filename}"'
                return response

        except Exception as exc:
            logger.exception("Erreur lors de la génération du fichier DQE %s pour le projet %s", export_format, projet.id)
            return Response(
                {"erreur": f"Erreur lors de la génération du fichier d'export : {str(exc)}"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )


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


class AssistantStructurerView(APIView):
    permission_classes = [IsAuthenticated]
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "assistant_structurer"

    def post(self, request):
        description = request.data.get("description")
        if not isinstance(description, str) or not description.strip():
            return Response(
                {"detail": "La description du projet est requise."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        description = description.strip()
        if len(description) > 1000:
            return Response(
                {"detail": "La description ne doit pas dépasser 1000 caractères."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            res = structurer_description_projet(description)
            return Response(res, status=status.HTTP_200_OK)
        except ValueError as exc:
            return Response(
                {"detail": str(exc), "code": "LLM_INVALID_INPUT"},
                status=status.HTTP_400_BAD_REQUEST,
            )
        except LLMServiceError as exc:
            return Response(
                {"detail": str(exc), "code": exc.code},
                status=exc.status_code,
            )
        except Exception as exc:
            return Response(
                {"detail": "Une erreur inattendue est survenue.", "code": "LLM_INVALID_RESPONSE", "erreur": str(exc)},
                status=status.HTTP_502_BAD_GATEWAY,
            )


class AssistantExpliquerView(APIView):
    permission_classes = [IsAuthenticated]
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "assistant_expliquer"

    def post(self, request):
        element_id = request.data.get("element_id")
        if not element_id:
            return Response(
                {"detail": "Le champ element_id est requis."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        element = get_object_or_404(ElementStructurel, id=element_id)

        # Vérification qu'il y a un résultat de calcul
        if element.resultat_calcul is None:
            return Response(
                {"detail": "Cet élément n'a aucun calcul de pré-dimensionnement disponible à expliquer."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Extraction des paramètres d'entrée et de sortie selon le type d'élément
        parametres = {}
        if element.type_element == ElementStructurel.TypeElement.POTEAU:
            parametres = {
                "hauteur_poteau": element.hauteur_poteau,
                "charge_calculee": element.charge_calculee
            }
        elif element.type_element == ElementStructurel.TypeElement.POUTRE:
            parametres = {
                "portee": element.portee,
                "charge_lineaire": element.charge_lineaire
            }
        elif element.type_element == ElementStructurel.TypeElement.SEMELLE:
            parametres = {
                "charge_calculee": element.charge_calculee,
                "taux_travail_sol": element.taux_travail_sol
            }

        elem_data = {
            "repere": element.identifiant,
            "type_element": element.type_element,
            "parametres": parametres,
            "resultats": element.resultat_calcul
        }

        try:
            result = expliquer_resultat_element(elem_data)
            return Response(result, status=status.HTTP_200_OK)
        except ValueError as exc:
            return Response(
                {"detail": str(exc), "code": "LLM_INVALID_INPUT"},
                status=status.HTTP_400_BAD_REQUEST,
            )
        except LLMServiceError as exc:
            return Response(
                {"detail": str(exc), "code": exc.code},
                status=exc.status_code,
            )
        except Exception as exc:
            return Response(
                {"detail": "Une erreur inattendue est survenue.", "code": "LLM_INVALID_RESPONSE", "erreur": str(exc)},
                status=status.HTTP_502_BAD_GATEWAY,
            )