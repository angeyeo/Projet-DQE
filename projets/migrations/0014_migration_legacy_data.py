from django.db import migrations


def rattacher_projets_a_entreprise_legacy(apps, schema_editor):
    Entreprise = apps.get_model('projets', 'Entreprise')
    Projet = apps.get_model('projets', 'Projet')

    # 1. Création de l'entreprise par défaut pour la compatibilité existante
    entreprise_legacy, _ = Entreprise.objects.get_or_create(
        nom="Cabinet d'Ingénierie (Legacy)",
        defaults={"code_cabinet": "CAB-LEGACY-001"}
    )

    # 2. Rattachement de tous les projets existants sans entreprise
    projets_sans_cabinet = Projet.objects.filter(entreprise__isnull=True)
    count = projets_sans_cabinet.update(entreprise=entreprise_legacy)
    print(f"\n--> [SUCCESS] {count} projet(s) existant(s) rattaché(s) au Cabinet Legacy.")


def reverse_func(apps, schema_editor):
    pass


class Migration(migrations.Migration):

    dependencies = [
        ('projets', '0013_entreprise_projet_cree_par_and_more'),
    ]

    operations = [
        migrations.RunPython(rattacher_projets_a_entreprise_legacy, reverse_func),
    ]