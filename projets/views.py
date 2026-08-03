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

from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response

from .models import Projet, ElementStructurel, PosteMainDoeuvre
from .serializers import (
    ProjetSerializer,
    ElementStructurelSerializer,
    ElementValidationSerializer,
    PosteMainDoeuvreSerializer,
)
from .services import calculer_element, recalculer_projet, CalculNonDisponible
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

    @action(detail=True, methods=["post"])
    def generer_dqe(self, request, pk=None):
        """
        Squelette en attente du module DQE (Dev 4).
        Vérifie d'abord que tous les éléments sont validés -- c'est la
        condition obligatoire avant de générer un devis.
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
        # TODO (Dev 4 - DQE+IA) : appeler ici le module de génération du DQE
        # une fois prêt, ex. : dqe.generer(projet)
        return Response(
            {"info": "Tous les éléments sont validés. Génération du DQE à brancher (Dev 4)."},
            status=status.HTTP_501_NOT_IMPLEMENTED,
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