"""
Normalise Projet.usage_batiment vers la nomenclature canonique du moteur
(clés de moteur_calcul.constantes.CHARGES_EXPLOITATION).

Variantes rencontrées dans le code avant correction :
  - "commercial"  (frontend Step1_Parametres.jsx)  -> "commerce"
  - "habitations" (repli de views.generer_trame)   -> "habitation"
  - majuscules (assistant IA : "HABITATION", "COMMERCE", "BUREAU",
    "INDUSTRIEL")                                   -> minuscules

Aucune donnée supprimée : seules ces valeurs EXACTES sont réécrites ;
toute autre valeur inconnue est laissée telle quelle (elle sera refusée
à la prochaine modification du projet, avec un message explicite).
La migration inverse est un no-op documenté : les valeurs canoniques
restent valides pour l'ancien code, et la variante d'origine exacte
("commercial" ou "Commercial"...) n'est pas conservée.
"""

from django.db import migrations

CORRESPONDANCES = {
    "commercial": "commerce",
    "Commercial": "commerce",
    "COMMERCIAL": "commerce",
    "habitations": "habitation",
    "HABITATION": "habitation",
    "COMMERCE": "commerce",
    "BUREAU": "bureau",
    "INDUSTRIEL": "industriel",
}


def normaliser(apps, schema_editor):
    Projet = apps.get_model("projets", "Projet")
    for ancien, nouveau in CORRESPONDANCES.items():
        Projet.objects.filter(usage_batiment=ancien).update(usage_batiment=nouveau)


class Migration(migrations.Migration):

    dependencies = [
        ("projets", "0016_cabinet_unique_valeurs_saisies_evenements"),
    ]

    operations = [
        migrations.RunPython(normaliser, migrations.RunPython.noop),
    ]
