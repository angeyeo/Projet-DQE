"""Réunit les migrations métier de dev et les migrations IA historiques.

Les changements des deux branches sont conservés séparément. Cette migration
ne modifie pas le schéma ; elle permet aux bases issues de l'une ou l'autre
branche de rejoindre le même graphe.
"""
from django.db import migrations


class Migration(migrations.Migration):
    dependencies = [
        ("projets", "0034_murs_par_etage"),
        ("projets", "0031_projet_provenance_parametres"),
    ]

    operations = []
