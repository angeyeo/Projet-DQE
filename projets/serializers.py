"""
Serializers DRF.

ElementStructurelSerializer expose resultat_calcul en lecture seule --
il n'est jamais écrit directement par le frontend, seulement produit
par le moteur de calcul (voir services.py).
"""

from rest_framework import serializers

from .models import Projet, ElementStructurel, PosteMainDoeuvre


class ElementStructurelSerializer(serializers.ModelSerializer):
    class Meta:
        model = ElementStructurel
        fields = [
            "id",
            "projet",
            "type_element",
            "identifiant",
            "portee",
            "charge_lineaire",
            "charge_calculee",
            "hauteur_poteau",
            "taux_travail_sol",
            "resultat_calcul",
            "resultat_valide",
            "statut",
            "date_creation",
            "date_modification",
        ]
        read_only_fields = ["resultat_calcul", "date_creation", "date_modification"]


class ElementValidationSerializer(serializers.Serializer):
    """
    Utilisé uniquement pour l'action de validation (voir views.py) --
    l'ingénieur peut ajuster manuellement le résultat avant de valider.
    """

    resultat_valide = serializers.JSONField(required=False)

    def validate(self, data):
        # TODO : ajouter ici une vérification métier si l'ingénieur modifie
        # une valeur (ex. refuser une section inférieure à un minimum
        # réglementaire) -- à définir avec le technicien BTP.
        return data


class PosteMainDoeuvreSerializer(serializers.ModelSerializer):
    montant = serializers.SerializerMethodField()

    class Meta:
        model = PosteMainDoeuvre
        fields = [
            "id",
            "projet",
            "designation",
            "unite",
            "quantite",
            "prix_unitaire",
            "montant",
            "date_creation",
            "date_modification",
        ]
        read_only_fields = ["date_creation", "date_modification"]

    def get_montant(self, obj):
        return obj.montant


class ProjetSerializer(serializers.ModelSerializer):
    elements = ElementStructurelSerializer(many=True, read_only=True)
    postes_main_doeuvre = PosteMainDoeuvreSerializer(many=True, read_only=True)
    nb_elements_valides = serializers.SerializerMethodField()
    nb_elements_total = serializers.SerializerMethodField()
    total_main_doeuvre = serializers.SerializerMethodField()

    class Meta:
        model = Projet
        fields = [
            "id",
            "nom",
            "usage_batiment",
            "nb_niveaux",
            "elements",
            "postes_main_doeuvre",
            "nb_elements_valides",
            "nb_elements_total",
            "total_main_doeuvre",
            "date_creation",
            "date_modification",
        ]

    def get_nb_elements_valides(self, obj):
        return obj.elements.filter(statut=ElementStructurel.Statut.VALIDE).count()

    def get_nb_elements_total(self, obj):
        return obj.elements.count()

    def get_total_main_doeuvre(self, obj):
        return sum(poste.montant for poste in obj.postes_main_doeuvre.all())