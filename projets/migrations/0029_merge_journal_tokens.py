"""Réunit les migrations distantes et le journal Gemini local.

Les deux branches restent inchangées pour les bases qui ont déjà appliqué
l'une ou l'autre. Aucun changement de données ou de schéma supplémentaire.
"""

from django.db import migrations


class Migration(migrations.Migration):
    dependencies = [
        ("projets", "0016_journalappelia_modele_journalappelia_tokens_entree_and_more"),
        ("projets", "0028_bibliotheque_ouvrages"),
    ]

    operations = []
