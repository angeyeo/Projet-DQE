"""
python manage.py rattacher_projets_orphelins [--dry-run]
python manage.py rattacher_projets_orphelins --cabinet <id> --projets 3 7 12
python manage.py rattacher_projets_orphelins --cabinet <id> --tous

Un projet "orphelin" n'a pas de cabinet (Projet.entreprise IS NULL) :
il est invisible pour tous les utilisateurs depuis l'isolation
multi-cabinet. Cette commande :
  - liste les orphelins (id, nom, auteur, cabinet de l'auteur s'il en a un,
    date) -- c'est le comportement par défaut, sans aucune écriture ;
  - ne rattache QUE sur ordre explicite : --cabinet obligatoire, et
    --projets (liste d'ids) ou --tous. Jamais de choix automatique, même
    quand l'auteur du projet appartient à un cabinet : la suggestion est
    affichée, la décision reste humaine.
"""

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from projets.models import EntrepriseParametres, Projet


class Command(BaseCommand):
    help = "Liste les projets sans cabinet et les rattache explicitement à un cabinet."

    def add_arguments(self, parser):
        parser.add_argument("--dry-run", action="store_true",
                            help="Affiche ce qui serait fait sans rien écrire.")
        parser.add_argument("--cabinet", type=int,
                            help="Id du cabinet (EntrepriseParametres) cible.")
        parser.add_argument("--projets", type=int, nargs="+",
                            help="Ids des projets orphelins à rattacher.")
        parser.add_argument("--tous", action="store_true",
                            help="Rattacher TOUS les orphelins listés au cabinet indiqué.")

    def _lister(self, orphelins):
        self.stdout.write(f"Projets sans cabinet : {orphelins.count()}")
        for p in orphelins:
            auteur = p.cree_par
            profil = getattr(auteur, "profil", None) if auteur else None
            suggestion = (
                f"cabinet de l'auteur : #{profil.entreprise_id} {profil.entreprise.nom!r}"
                if profil else "aucune suggestion (auteur sans cabinet)"
            )
            self.stdout.write(
                f"  #{p.id:<5} {p.nom[:40]:<40} créé le {p.date_creation:%Y-%m-%d} "
                f"par {auteur.username if auteur else '—'} | {suggestion}"
            )

    def handle(self, *args, **opts):
        orphelins = Projet.objects.filter(entreprise__isnull=True).select_related("cree_par").order_by("id")
        self._lister(orphelins)

        if opts["cabinet"] is None:
            if opts["projets"] or opts["tous"]:
                raise CommandError("--cabinet est obligatoire pour rattacher des projets.")
            self.stdout.write("Aucun rattachement demandé (utilisez --cabinet avec --projets ou --tous).")
            return

        if bool(opts["projets"]) == bool(opts["tous"]):
            raise CommandError("Précisez soit --projets <ids>, soit --tous (pas les deux, pas aucun).")

        try:
            cabinet = EntrepriseParametres.objects.get(pk=opts["cabinet"])
        except EntrepriseParametres.DoesNotExist:
            raise CommandError(f"Cabinet #{opts['cabinet']} introuvable.")

        cibles = orphelins
        if opts["projets"]:
            demandes = set(opts["projets"])
            cibles = orphelins.filter(id__in=demandes)
            trouves = set(cibles.values_list("id", flat=True))
            non_orphelins = demandes - trouves
            if non_orphelins:
                raise CommandError(
                    "Ces projets n'existent pas ou ont déjà un cabinet (aucune modification faite) : "
                    + ", ".join(map(str, sorted(non_orphelins)))
                )

        ids = list(cibles.values_list("id", flat=True))
        if not ids:
            self.stdout.write("Rien à rattacher.")
            return

        verbe = "SERAIENT rattachés" if opts["dry_run"] else "rattachés"
        self.stdout.write(f"{len(ids)} projet(s) {verbe} au cabinet #{cabinet.id} {cabinet.nom!r} : {ids}")
        if opts["dry_run"]:
            self.stdout.write(self.style.WARNING("--dry-run : aucune écriture effectuée."))
            return

        with transaction.atomic():
            # Re-filtre sur entreprise IS NULL : ne réécrit jamais un projet
            # rattaché entre-temps.
            n = Projet.objects.filter(id__in=ids, entreprise__isnull=True).update(entreprise=cabinet)
        self.stdout.write(self.style.SUCCESS(f"{n} projet(s) rattaché(s)."))
