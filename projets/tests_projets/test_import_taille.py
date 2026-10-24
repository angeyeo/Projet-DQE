"""Plans jusqu'à 50 Mo (issue #90) : limites exposées au frontend, taille
et temps de lecture renvoyés, refus clair au-delà de la limite.

Mesure manuelle (poste de développement, gunicorn) : DXF de 46,7 Mo
(12 poteaux + 285 000 traits) lu en 13,2 s ; DXF de 51,1 Mo refusé en 0,3 s.
"""
import shutil
import tempfile
from unittest import mock

from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import override_settings
from rest_framework.test import APITestCase

from projets.models import Projet
from projets.tests_projets.test_import_dxf import construire_dxf
from projets.tests_projets.utils import authentifier


class Limites(APITestCase):
    def test_limites_dans_le_referentiel(self):
        authentifier(self)
        limites = self.client.get("/api/referentiel/").data["limites_fichiers"]
        self.assertEqual(limites["plan_octets"], 50 * 1024 * 1024)
        self.assertEqual(limites["image_plan_octets"], 5 * 1024 * 1024)


class LectureMesuree(APITestCase):
    def setUp(self):
        self.media = tempfile.mkdtemp()
        self.reglage = override_settings(MEDIA_ROOT=self.media)
        self.reglage.enable()
        self.user, self.cabinet = authentifier(self)
        self.projet = Projet.objects.create(
            nom="Duplex", entreprise=self.cabinet, usage_batiment="habitation", nb_niveaux=1, hauteur_etage=3.0)
        self.url = f"/api/projets/{self.projet.id}/importer_plan/"
        construire_dxf(f"{self.media}/source.dxf")
        with open(f"{self.media}/source.dxf", "rb") as f:
            self.contenu = f.read()

    def tearDown(self):
        self.reglage.disable()
        shutil.rmtree(self.media, ignore_errors=True)

    def deposer(self):
        return self.client.post(self.url, {"fichier": SimpleUploadedFile("plan.dxf", self.contenu)}, format="multipart")

    def test_taille_et_duree_renvoyees(self):
        r = self.deposer()
        self.assertEqual(r.status_code, 200, r.data)
        self.assertEqual(r.data["lecture"]["taille_mo"], round(len(self.contenu) / 1048576, 1))
        self.assertGreaterEqual(r.data["lecture"]["duree_s"], 0)

    def test_mode_architecte_mesure_aussi(self):
        f = SimpleUploadedFile("plan.dxf", self.contenu)
        r = self.client.post(self.url, {"fichier": f, "mode": "architecte"}, format="multipart")
        self.assertEqual(r.status_code, 200, r.data)
        self.assertIn("lecture", r.data)

    def test_au_dela_de_la_limite_refuse_sans_lecture(self):
        with mock.patch("projets.views.TAILLE_MAX_PLAN_OCTETS", 100), \
                mock.patch("projets.views.ProjetViewSet._apercu_dxf") as apercu:
            r = self.deposer()
        self.assertEqual(r.status_code, 400)
        self.assertIn("Mo au maximum", r.data["erreur"])
        apercu.assert_not_called()
        self.projet.refresh_from_db()
        self.assertFalse(self.projet.fichier_import_origine)
