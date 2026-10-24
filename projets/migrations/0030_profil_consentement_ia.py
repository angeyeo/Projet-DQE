from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("projets", "0029_merge_journal_tokens")]

    operations = [
        migrations.AddField(
            model_name="profil",
            name="consentement_ia",
            field=models.CharField(
                choices=[
                    ("non_renseigne", "Non renseigné"),
                    ("accepte", "Accepté"),
                    ("refuse", "Refusé"),
                ],
                default="non_renseigne",
                max_length=20,
            ),
        ),
        migrations.AddField(
            model_name="profil",
            name="consentement_ia_version",
            field=models.CharField(blank=True, max_length=40, null=True),
        ),
        migrations.AddField(
            model_name="profil",
            name="consentement_ia_date",
            field=models.DateTimeField(blank=True, null=True),
        ),
    ]
