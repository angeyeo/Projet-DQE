import os
import logging
from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated, AllowAny
from rest_framework.response import Response
from rest_framework.throttling import ScopedRateThrottle
from rest_framework.views import APIView
from django.http import HttpResponse
from django.shortcuts import get_object_or_404

from .models import Projet, ElementStructurel, CoucheCharge, PosteComplementaire
from .serializers import (
    ProjetSerializer,
    ElementStructurelSerializer,
    ElementValidationSerializer,
    CoucheChargeSerializer,
    PosteComplementaireSerializer,
)
from .services import calculer_element, recalculer_projet, CalculNonDisponible
from .services.dqe_calculator import calculer_projet_dqe
from .services.dqe_exporters import exporter_dqe_pdf, exporter_dqe_excel
from .services.assistant_ia.parser import structurer_description_projet
from .services.assistant_ia.explanations import expliquer_resultat_element
from .services.assistant_ia.client import LLMServiceError
from moteur_calcul.validators import EntreeInvalide

logger = logging.getLogger(__name__)


class ProjetViewSet(viewsets.ModelViewSet):
    queryset = Projet.objects.all()
    serializer_class = ProjetSerializer

    @action(detail=True, methods=["post"])
    def recalculer(self, request, pk=None):
        projet = self.get_object()
        resultats = recalculer_projet(projet)
        return Response(resultats, status=status.HTTP_200_OK)

    @action(detail=True, methods=["get"])
    def chainage_suggere(self, request, pk=None):
        projet = self.get_object()
        try:
            from moteur_calcul.formules.postes_ratio import calculer_longueur_chainage

            longueur = calculer_longueur_chainage(
                projet.nb_travees_x,
                projet.nb_travees_y,
                projet.portee_x,
                projet.portee_y,
            )
        except (ImportError, ModuleNotFoundError, AttributeError):
            longueur = 2 * (
                projet.nb_travees_x * projet.portee_x
                + projet.nb_travees_y * projet.portee_y
            )
        return Response({"longueur_m": longueur}, status=status.HTTP_200_OK)

    @action(detail=True, methods=["post"])
    def generer_trame(self, request, pk=None):
        projet = self.get_object()
        elements_crees = []

        try:
            from moteur_calcul.formules.trame import generer_poteau_sur_grille
        except (ImportError, ModuleNotFoundError):
            generer_poteau_sur_grille = None

        charge_exp = projet.charge_exploitation or 1.5

        for i in range(projet.nb_travees_x + 1):
            for j in range(projet.nb_travees_y + 1):
                x = i * projet.portee_x
                y = j * projet.portee_y

                if generer_poteau_sur_grille:
                    donnees = generer_poteau_sur_grille(
                        i,
                        j,
                        projet.portee_x,
                        projet.portee_y,
                        projet.nb_travees_x,
                        projet.nb_travees_y,
                        charge_exp,
                        projet.hauteur_etage,
                    )
                    charge_elu = donnees.get("charge_elu_kn", 100.0)
                    res_poteau = donnees.get("resultat_poteau")
                    res_semelle = donnees.get("resultat_semelle")
                else:
                    charge_elu = 150.0
                    res_poteau = {"cote_cm": 25, "acier_cm2": 4.5}
                    res_semelle = {"cote_cm": 120, "hauteur_cm": 30}

                poteau = ElementStructurel.objects.create(
                    projet=projet,
                    identifiant=f"P_{i}_{j}",
                    type_element=ElementStructurel.TypeElement.POTEAU,
                    position=ElementStructurel.Position.SUPERSTRUCTURE,
                    position_x=x,
                    position_y=y,
                    hauteur_poteau=projet.hauteur_etage,
                    charge_calculee=charge_elu,
                    resultat_calcul=res_poteau,
                )
                elements_crees.append(poteau)

                semelle = ElementStructurel.objects.create(
                    projet=projet,
                    identifiant=f"S_{i}_{j}",
                    type_element=ElementStructurel.TypeElement.SEMELLE,
                    position=ElementStructurel.Position.INFRASTRUCTURE,
                    position_x=x,
                    position_y=y,
                    poteau_associe=poteau,
                    charge_calculee=charge_elu,
                    taux_travail_sol=0.2,
                    resultat_calcul=res_semelle,
                )
                elements_crees.append(semelle)

        serializer = ElementStructurelSerializer(elements_crees, many=True)
        return Response(serializer.data, status=status.HTTP_201_CREATED)

    @action(detail=True, methods=["get"])
    def plan_fondation(self, request, pk=None):
        projet = self.get_object()
        export_format = request.query_params.get("format")

        semelles = projet.elements.filter(
            type_element=ElementStructurel.TypeElement.SEMELLE
        )

        if export_format == "dxf":
            try:
                from moteur_calcul.formules.dxf import generer_plan_fondation_dxf

                buffer = generer_plan_fondation_dxf(semelles)
                content = buffer.getvalue()
            except (ImportError, ModuleNotFoundError, AttributeError):
                content = b"0\nSECTION\n2\nHEADER\n0\nENDSEC\n0\nEOF\n"

            response = HttpResponse(content, content_type="application/dxf")
            response["Content-Disposition"] = (
                f'attachment; filename="Plan_fondation_{projet.id}.dxf"'
            )
            return response

        serializer = ElementStructurelSerializer(semelles, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)

    @action(detail=True, methods=["post"])
    def valider_plan_fondation(self, request, pk=None):
        projet = self.get_object()
        projet.plan_fondation_valide = True
        projet.save(update_fields=["plan_fondation_valide"])
        return Response(
            {"status": "Plan de fondation validé."}, status=status.HTTP_200_OK
        )

    @action(
        detail=True,
        methods=["get", "post"],
        url_path="generer-dqe",
        url_name="generer-dqe",
    )
    def generer_dqe(self, request, pk=None):
        projet = self.get_object()

        if not projet.elements.exists():
            return Response(
                {"erreur": "Le projet ne contient aucun élément structurel."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        elements_non_valides = projet.elements.exclude(
            statut=ElementStructurel.Statut.VALIDE
        )
        if elements_non_valides.exists():
            return Response(
                {
                    "erreur": "Tous les éléments doivent être validés.",
                    "elements_en_attente": list(
                        elements_non_valides.values_list("identifiant", flat=True)
                    ),
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        export_format = request.query_params.get("export") or (
            request.data.get("export") if isinstance(request.data, dict) else None
        )
        dqe_data = calculer_projet_dqe(projet)

        if export_format is None:
            return Response(dqe_data, status=status.HTTP_200_OK)

        nom_fichier_base = f"DQE_{projet.nom.replace(' ', '_')}_{projet.id}"
        if export_format == "pdf":
            buffer = exporter_dqe_pdf(dqe_data)
            response = HttpResponse(buffer.getvalue(), content_type="application/pdf")
            response["Content-Disposition"] = (
                f'attachment; filename="{nom_fichier_base}.pdf"'
            )
        elif export_format == "excel":
            buffer = exporter_dqe_excel(dqe_data)
            response = HttpResponse(
                buffer.getvalue(),
                content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            )
            response["Content-Disposition"] = (
                f'attachment; filename="{nom_fichier_base}.xlsx"'
            )
        else:
            return Response(
                {"erreur": f"Format d'export invalide: {export_format}"},
                status=status.HTTP_400_BAD_REQUEST,
            )
        return response


class ElementStructurelViewSet(viewsets.ModelViewSet):
    queryset = ElementStructurel.objects.all()
    serializer_class = ElementStructurelSerializer

    @action(detail=True, methods=["post"])
    def calculer(self, request, pk=None):
        element = self.get_object()
        try:
            resultat = calculer_element(element)
        except CalculNonDisponible as exc:
            return Response(
                {"erreur": "Moteur indisponible", "detail": str(exc)},
                status=status.HTTP_503_SERVICE_UNAVAILABLE,
            )
        except EntreeInvalide as exc:
            return Response({"erreur": str(exc)}, status=status.HTTP_400_BAD_REQUEST)

        element.resultat_calcul = resultat
        element.save(update_fields=["resultat_calcul", "date_modification"])
        return Response(ElementStructurelSerializer(element).data)

    @action(detail=True, methods=["post"])
    def valider(self, request, pk=None):
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
        instance = serializer.instance
        if instance.statut == ElementStructurel.Statut.VALIDE:
            serializer.save(statut=ElementStructurel.Statut.MODIFIE)
        else:
            serializer.save()


class CoucheChargeViewSet(viewsets.ModelViewSet):
    queryset = CoucheCharge.objects.all()
    serializer_class = CoucheChargeSerializer


class PosteComplementaireViewSet(viewsets.ModelViewSet):
    queryset = PosteComplementaire.objects.all()
    serializer_class = PosteComplementaireSerializer

    def perform_create(self, serializer):
        mode = serializer.validated_data.get("mode")
        type_poste = serializer.validated_data.get("type_poste")
        geometrie = serializer.validated_data.get("geometrie")

        lignes = None
        if mode == PosteComplementaire.Mode.RATIO and type_poste and geometrie:
            try:
                from moteur_calcul.formules.postes_ratio import calculer_poste_ratio

                lignes = calculer_poste_ratio(type_poste, geometrie)
            except (ImportError, ModuleNotFoundError):
                lignes = [
                    {"designation": f"Ratio {type_poste}", "quantite": 1, "pu": 1000}
                ]

        serializer.save(lignes_calculees=lignes)


class AssistantStructurerView(APIView):
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "assistant_structurer"

    def get_permissions(self):
        if os.getenv("DEMO_MODE", "False").lower() == "true":
            return [AllowAny()]
        return [IsAuthenticated()]

    def post(self, request):
        description = request.data.get("description", "").strip()
        if not description:
            return Response(
                {"detail": "La description du projet est requise."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        if len(description) > 1000:
            return Response(
                {"detail": "La description ne doit pas dépasser 1000 caractères."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        try:
            res = structurer_description_projet(description)
            return Response(res, status=status.HTTP_200_OK)
        except LLMServiceError as exc:
            return Response(
                {"detail": str(exc), "code": exc.code},
                status=exc.status_code,
            )
        except Exception as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)


class AssistantExpliquerView(APIView):
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "assistant_expliquer"

    def get_permissions(self):
        if os.getenv("DEMO_MODE", "False").lower() == "true":
            return [AllowAny()]
        return [IsAuthenticated()]

    def post(self, request):
        element_id = request.data.get("element_id")
        if not element_id:
            return Response(
                {"detail": "Le champ element_id est requis."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        element = get_object_or_404(ElementStructurel, id=element_id)
        if element.resultat_calcul is None:
            return Response(
                {"detail": "Cet élément n'a aucun calcul disponible à expliquer."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        try:
            elem_payload = {
                "repere": element.identifiant,
                "type_element": element.type_element,
                "parametres": {
                    "hauteur_poteau": element.hauteur_poteau,
                    "charge_calculee": element.charge_calculee,
                    "portee": element.portee,
                    "charge_lineaire": element.charge_lineaire,
                    "taux_travail_sol": element.taux_travail_sol,
                },
                "resultats": element.resultat_calcul or {},
            }
            res = expliquer_resultat_element(elem_payload)
            return Response(res, status=status.HTTP_200_OK)
        except LLMServiceError as exc:
            return Response(
                {"detail": str(exc), "code": exc.code},
                status=exc.status_code,
            )
        except Exception as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)