from django.db.models.signals import post_save
from django.dispatch import receiver
from django.contrib.auth.models import User
from .models import Profil, EntrepriseParametres


@receiver(post_save, sender=User)
def creer_profil_utilisateur(sender, instance, created, **kwargs):
    if created:
        # Récupération sécurisée du singleton EntrepriseParametres
        try:
            # Si le projet utilise django-solo (get_solo)
            if hasattr(EntrepriseParametres, "get_solo"):
                entreprise_defaut = EntrepriseParametres.get_solo()
            else:
                # Sinon on prend le premier ou on en crée un avec un ID forcé à 1
                entreprise_defaut = EntrepriseParametres.objects.first()
                if not entreprise_defaut:
                    entreprise_defaut = EntrepriseParametres.objects.create(pk=1, nom="Cabinet Principal")
        except Exception:
            # Fallback de secours absolu pour ne jamais bloquer la création d'un user en test
            entreprise_defaut, _ = EntrepriseParametres.objects.get_or_create(
                defaults={"nom": "Cabinet Principal"}
            )
        
        # Création ou récupération du profil associé
        Profil.objects.get_or_create(
            user=instance,
            defaults={
                "entreprise": entreprise_defaut,
                "role": Profil.Role.ADMIN if instance.is_superuser else Profil.Role.INGENIEUR
            }
        )