from django.db.models.signals import post_save
from django.dispatch import receiver
from django.contrib.auth.models import User
from .models import Profil, Entreprise


@receiver(post_save, sender=User)
def creer_profil_utilisateur(sender, instance, created, **kwargs):
    if created:
        # Récupère ou crée une entreprise par défaut de manière sécurisée
        entreprise_defaut, _ = Entreprise.objects.get_or_create(
            nom="Cabinet Principal",
            defaults={"code_cabinet": "DEFAULT"}
        )
        
        Profil.objects.create(
            user=instance,
            entreprise=entreprise_defaut,
            role=Profil.Role.ADMIN if instance.is_superuser else Profil.Role.INGENIEUR
        )