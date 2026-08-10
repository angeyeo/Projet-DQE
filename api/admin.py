from django.contrib import admin

from .models import Projet, ElementStructurel


@admin.register(Projet)
class ProjetAdmin(admin.ModelAdmin):
    list_display = ["nom", "usage_batiment", "nb_niveaux", "date_modification"]
    list_filter = ["usage_batiment"]


@admin.register(ElementStructurel)
class ElementStructurelAdmin(admin.ModelAdmin):
    list_display = ["identifiant", "type_element", "projet", "statut", "date_modification"]
    list_filter = ["type_element", "statut", "projet"]
    search_fields = ["identifiant"]