"""Serializers de requête utilisés pour décrire les endpoints ad hoc.

Ils ne pilotent pas la validation métier : les vues et serializers existants
restent la seule source du comportement API.
"""

from rest_framework import serializers


class DescriptionIARequest(serializers.Serializer):
    description = serializers.CharField()


class ElementIARequest(serializers.Serializer):
    element_id = serializers.IntegerField()


class DecisionConsentementRequest(serializers.Serializer):
    decision = serializers.ChoiceField(choices=("accepte", "refuse"))


class InscriptionRequest(serializers.Serializer):
    nom_entreprise = serializers.CharField()
    username = serializers.CharField()
    email = serializers.CharField(required=False, allow_blank=True)
    mot_de_passe = serializers.CharField()


class InvitationRequest(serializers.Serializer):
    email = serializers.CharField()
    role = serializers.CharField(required=False)


class ActivationRequest(serializers.Serializer):
    uid = serializers.CharField()
    token = serializers.CharField()
    mot_de_passe = serializers.CharField()


class MotDePasseRequest(serializers.Serializer):
    ancien_mot_de_passe = serializers.CharField()
    nouveau_mot_de_passe = serializers.CharField()


class DemandeReinitialisationRequest(serializers.Serializer):
    email = serializers.CharField()


class ConfirmationReinitialisationRequest(serializers.Serializer):
    uid = serializers.CharField()
    token = serializers.CharField()
    nouveau_mot_de_passe = serializers.CharField()


class LogoutRequest(serializers.Serializer):
    refresh = serializers.CharField()


class UploadFichierRequest(serializers.Serializer):
    fichier = serializers.FileField()


class ImportPlanJSONRequest(serializers.Serializer):
    plan = serializers.CharField(required=False)
    confirmer = serializers.BooleanField(required=False)


class ImportBibliothequeRequest(serializers.Serializer):
    fichier = serializers.FileField()


class ConfirmerImportBibliothequeRequest(serializers.Serializer):
    lignes = serializers.ListField(child=serializers.DictField())
    source_prix = serializers.CharField(required=False, allow_blank=True)
    date_prix = serializers.DateField(required=False, allow_null=True)


class VariantesRequest(serializers.Serializer):
    variantes = serializers.ListField(child=serializers.DictField())


class ExportRequest(serializers.Serializer):
    """Corps JSON facultatif accepté par POST generer-dqe."""
    export = serializers.ChoiceField(choices=("pdf", "excel"), required=False)


class ProfilMembreResponse(serializers.Serializer):
    id = serializers.IntegerField()
    username = serializers.CharField()
    email = serializers.EmailField(allow_blank=True)
    role = serializers.CharField()
    role_display = serializers.CharField()
    actif = serializers.BooleanField()
    entreprise_id = serializers.IntegerField(allow_null=True)
    date_creation = serializers.DateTimeField()


class ConsentementIAProfilResponse(serializers.Serializer):
    id = serializers.IntegerField()
    username = serializers.CharField()
    email = serializers.CharField(allow_blank=True)
    role = serializers.CharField()
    role_display = serializers.CharField()
    actif = serializers.BooleanField()
    entreprise_id = serializers.IntegerField(allow_null=True)
    date_creation = serializers.DateTimeField()
    consentement_ia = serializers.CharField(allow_null=True)
    consentement_ia_version = serializers.CharField(allow_null=True)
    consentement_ia_date = serializers.DateTimeField(allow_null=True)
    consentement_ia_valide = serializers.BooleanField()


class StructurationDonneesResponse(serializers.Serializer):
    nombre_niveaux = serializers.IntegerField(allow_null=True)
    configuration = serializers.CharField(allow_null=True)
    usage = serializers.CharField(allow_null=True)
    usage_batiment = serializers.CharField(allow_null=True)
    portee_m = serializers.FloatField(allow_null=True)
    portee_x_m = serializers.FloatField(allow_null=True)
    portee_y_m = serializers.FloatField(allow_null=True)
    hauteur_niveau_m = serializers.FloatField(allow_null=True)
    contrainte_sol_kn_m2 = serializers.FloatField(allow_null=True)


class StructurationIAResponse(serializers.Serializer):
    donnees = StructurationDonneesResponse()
    donnees_manquantes = serializers.ListField(child=serializers.CharField())
    avertissements = serializers.ListField(child=serializers.CharField())
    confirmation_requise = serializers.BooleanField()
    source = serializers.CharField()
    preuve_proposition = serializers.CharField(allow_null=True)


class ExplicationIAResponse(serializers.Serializer):
    explication = serializers.CharField()
    source = serializers.CharField()
    explication_technique_disponible = serializers.BooleanField()
    validation_humaine_requise = serializers.BooleanField()


class SuggestionPosteResponse(serializers.Serializer):
    designation = serializers.CharField()
    unite = serializers.CharField()
    lot_suggere = serializers.CharField()
    confiance = serializers.CharField()


class SuggestionIAResponse(serializers.Serializer):
    suggestion = SuggestionPosteResponse(allow_null=True)
    source = serializers.CharField()
    validation_humaine_requise = serializers.BooleanField()
    message = serializers.CharField(required=False)
    message_validation = serializers.CharField(required=False)


class AnnotationVisionResponse(serializers.Serializer):
    texte_lu = serializers.CharField()
    repere = serializers.CharField()
    type_normalise = serializers.CharField(allow_null=True)
    dimensions_parsees = serializers.JSONField(allow_null=True)


class VisionResponse(serializers.Serializer):
    annotations_lues = AnnotationVisionResponse(many=True)
    textes_non_classes = serializers.ListField(child=serializers.CharField())
    source = serializers.CharField()
    validation_humaine_requise = serializers.BooleanField()
    message = serializers.CharField(required=False)
