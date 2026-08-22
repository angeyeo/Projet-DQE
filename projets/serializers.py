from rest_framework import serializers
from .models import Projet, ElementStructurel, CoucheCharge, PosteComplementaire, EntrepriseParametres


class CoucheChargeSerializer(serializers.ModelSerializer):
    poids_surfacique_kn_m2 = serializers.ReadOnlyField()

    class Meta:
        model = CoucheCharge
        fields = "__all__"


class ElementStructurelSerializer(serializers.ModelSerializer):
    couches_charges = CoucheChargeSerializer(many=True, read_only=True)

    class Meta:
        model = ElementStructurel
        fields = "__all__"
        read_only_fields = ("statut", "resultat_calcul", "resultat_valide")


class ElementValidationSerializer(serializers.Serializer):
    resultat_valide = serializers.JSONField(required=False)


class PosteComplementaireSerializer(serializers.ModelSerializer):
    class Meta:
        model = PosteComplementaire
        fields = "__all__"


class ProjetSerializer(serializers.ModelSerializer):
    elements = ElementStructurelSerializer(many=True, read_only=True)
    couches_charges = CoucheChargeSerializer(many=True, read_only=True)
    postes_complementaires = PosteComplementaireSerializer(many=True, read_only=True)

    class Meta:
        model = Projet
        fields = "__all__"


class EntrepriseParametresSerializer(serializers.ModelSerializer):
    class Meta:
        model = EntrepriseParametres
        fields = "__all__"
        read_only_fields = ("date_modification",)