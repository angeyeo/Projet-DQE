from rest_framework import serializers
from django.contrib.auth.models import User
from .models import (
    Projet, 
    ElementStructurel, 
    CoucheCharge, 
    PosteComplementaire, 
    EntrepriseParametres, 
    Profil, 
    Entreprise
)


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


class EntrepriseSerializer(serializers.ModelSerializer):
    class Meta:
        model = Entreprise
        fields = ['id', 'nom', 'code_cabinet', 'telephone', 'email', 'adresse']


class ProfilSerializer(serializers.ModelSerializer):
    entreprise = EntrepriseSerializer(read_only=True)
    username = serializers.CharField(source='user.username', read_only=True)
    email = serializers.CharField(source='user.email', read_only=True)

    class Meta:
        model = Profil
        fields = ['id', 'username', 'email', 'role', 'telephone', 'entreprise']


class AdminInviteUserSerializer(serializers.Serializer):
    username = serializers.CharField(required=True)
    email = serializers.EmailField(required=True)
    first_name = serializers.CharField(required=False, allow_blank=True)
    last_name = serializers.CharField(required=False, allow_blank=True)
    role = serializers.ChoiceField(choices=Profil.Role.choices, default=Profil.Role.TECHNICIEN)

    def validate_email(self, value):
        if User.objects.filter(email=value).exists():
            raise serializers.ValidationError("Un utilisateur avec cet email existe déjà.")
        return value