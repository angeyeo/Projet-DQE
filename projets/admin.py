from django.contrib import admin

from .models import Projet, ElementStructurel, Profil, EntrepriseParametres


@admin.register(Projet)
class ProjetAdmin(admin.ModelAdmin):
    list_display = ["nom", "usage_batiment", "nb_niveaux", "entreprise", "cree_par", "date_modification"]
    list_filter = ["usage_batiment", "entreprise"]


@admin.register(ElementStructurel)
class ElementStructurelAdmin(admin.ModelAdmin):
    list_display = ["identifiant", "type_element", "projet", "statut", "date_modification"]
    list_filter = ["type_element", "statut", "projet"]
    search_fields = ["identifiant"]


@admin.register(Profil)
class ProfilAdmin(admin.ModelAdmin):
    list_display = ["utilisateur", "entreprise", "role", "date_creation"]
    list_filter = ["role", "entreprise"]
    search_fields = ["utilisateur__username", "utilisateur__email"]
    autocomplete_fields = ["utilisateur"]


@admin.register(EntrepriseParametres)
class EntrepriseParametresAdmin(admin.ModelAdmin):
    list_display = ["nom", "email", "telephone", "date_modification"]
    search_fields = ["nom"]