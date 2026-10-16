from io import StringIO

from django.core.management import CommandError, call_command
from django.test import TestCase

from projets.models import Projet
from projets.tests_projets.utils import creer_cabinet


class RattacherProjetsOrphelinsTestCase(TestCase):
    def setUp(self):
        self.cabinet = creer_cabinet("Cabinet cible")
        self.autre = creer_cabinet("Autre")
        self.o1 = Projet.objects.create(nom="Orphelin 1")
        self.o2 = Projet.objects.create(nom="Orphelin 2")
        self.rattache = Projet.objects.create(nom="Déjà rattaché", entreprise=self.autre)

    def _run(self, *args):
        out = StringIO()
        call_command("rattacher_projets_orphelins", *args, stdout=out)
        return out.getvalue()

    def test_par_defaut_liste_sans_ecrire(self):
        sortie = self._run()
        self.assertIn("Projets sans cabinet : 2", sortie)
        self.assertIn("Orphelin 1", sortie)
        self.assertEqual(Projet.objects.filter(entreprise__isnull=True).count(), 2)

    def test_dry_run_n_ecrit_rien(self):
        sortie = self._run("--dry-run", "--cabinet", str(self.cabinet.id), "--tous")
        self.assertIn("SERAIENT", sortie)
        self.assertEqual(Projet.objects.filter(entreprise__isnull=True).count(), 2)

    def test_rattachement_explicite_cible(self):
        self._run("--cabinet", str(self.cabinet.id), "--projets", str(self.o1.id))
        self.o1.refresh_from_db()
        self.o2.refresh_from_db()
        self.assertEqual(self.o1.entreprise_id, self.cabinet.id)
        self.assertIsNone(self.o2.entreprise_id)

    def test_jamais_de_reecriture_d_un_projet_deja_rattache(self):
        with self.assertRaises(CommandError):
            self._run("--cabinet", str(self.cabinet.id), "--projets", str(self.rattache.id))
        self.rattache.refresh_from_db()
        self.assertEqual(self.rattache.entreprise_id, self.autre.id)

    def test_cabinet_obligatoire_pour_ecrire(self):
        with self.assertRaises(CommandError):
            self._run("--tous")

    def test_cabinet_inexistant(self):
        with self.assertRaises(CommandError):
            self._run("--cabinet", "99999", "--tous")
