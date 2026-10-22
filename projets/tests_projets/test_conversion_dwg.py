"""Fichiers DWG et PLN (issue #95).

- Sans convertisseur sur le serveur : DWG refusé avec un message d'export.
- .pln : toujours refusé (format fermé), message guidant l'export IFC.
- Avec GNU LibreDWG (dwg2dxf) : le DWG est converti puis lu comme un DXF.
  Ces tests-là ne tournent que si l'outil est installé (DWG2DXF_PATH ou PATH) ;
  le DWG d'essai est fabriqué par dxf2dwg, installé avec dwg2dxf.
"""
import os
import shutil
import subprocess
import tempfile
import unittest
from unittest import mock

import ezdxf
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import override_settings
from rest_framework.test import APITestCase

from moteur_calcul.import_dxf import conversion_dwg
from projets.models import ElementStructurel, Projet
from projets.tests_projets.utils import authentifier

CONVERTISSEUR = os.environ.get("DWG2DXF_PATH") or shutil.which("dwg2dxf")


class BaseImport(APITestCase):
    def setUp(self):
        self.media = tempfile.mkdtemp()
        self.reglage = override_settings(MEDIA_ROOT=self.media)
        self.reglage.enable()
        self.user, self.cabinet = authentifier(self)
        self.projet = Projet.objects.create(nom="Villa", entreprise=self.cabinet, usage_batiment="habitation",
                                            nb_niveaux=2, hauteur_etage=3.0, contrainte_sol_kn_m2=150)
        self.url = f"/api/projets/{self.projet.id}/importer_plan/"

    def tearDown(self):
        self.reglage.disable()
        shutil.rmtree(self.media, ignore_errors=True)

    def deposer(self, nom, contenu, **extra):
        return self.client.post(self.url, {"fichier": SimpleUploadedFile(nom, contenu), **extra}, format="multipart")


@override_settings(DWG2DXF_PATH="/inexistant/dwg2dxf")
class SansConvertisseur(BaseImport):
    def test_dwg_refuse_avec_message_d_export(self):
        r = self.deposer("plan.dwg", b"AC1032 contenu")
        self.assertEqual(r.status_code, 400)
        self.assertIn("Enregistrer sous", r.data["erreur"])
        self.assertIn("DXF", r.data["erreur"])
        self.projet.refresh_from_db()
        self.assertFalse(self.projet.fichier_import_origine)

    def test_pln_refuse_message_ifc(self):
        r = self.deposer("villa.pln", b"\x00\x01")
        self.assertEqual(r.status_code, 400)
        self.assertIn("format fermé", r.data["erreur"])
        self.assertIn("IFC", r.data["erreur"])


class ConversionSimulee(BaseImport):
    """Échecs de l'outil (simulés) : jamais de DXF inventé."""

    def setUp(self):
        super().setUp()
        self.reglage_outil = override_settings(DWG2DXF_PATH="/bin/true")
        self.reglage_outil.enable()

    def tearDown(self):
        self.reglage_outil.disable()
        super().tearDown()

    def test_sortie_vide_refusee(self):
        r = self.deposer("plan.dwg", b"pas un dwg")  # /bin/true ne produit aucun DXF
        self.assertEqual(r.status_code, 400)
        self.assertIn("n'a pas pu être converti", r.data["erreur"])

    def test_delai_depasse(self):
        with mock.patch.object(conversion_dwg.subprocess, "run",
                               side_effect=subprocess.TimeoutExpired(cmd="dwg2dxf", timeout=60)):
            r = self.deposer("plan.dwg", b"x")
        self.assertEqual(r.status_code, 400)
        self.assertIn("dépassé", r.data["erreur"])

    def test_taille_maximale_controlee_avant_conversion(self):
        with mock.patch("projets.views.TAILLE_MAX_PLAN_OCTETS", 10), \
                mock.patch.object(conversion_dwg.subprocess, "run") as run:
            r = self.deposer("plan.dwg", b"x" * 11)
        self.assertEqual(r.status_code, 400)
        self.assertIn("trop volumineux", r.data["erreur"])
        run.assert_not_called()


@unittest.skipUnless(CONVERTISSEUR, "GNU LibreDWG (dwg2dxf) non installé")
class ConversionReelle(BaseImport):
    def setUp(self):
        super().setUp()
        self.reglage_outil = override_settings(DWG2DXF_PATH=CONVERTISSEUR)
        self.reglage_outil.enable()
        dossier = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, dossier, True)
        d = ezdxf.new("R2000")
        d.header["$INSUNITS"] = 6
        b = d.blocks.new("Column_1")
        b.add_lwpolyline([(-0.1, -0.1), (0.1, -0.1), (0.1, 0.1), (-0.1, 0.1)], close=True)
        for i in range(3):
            for j in range(3):
                d.modelspace().add_blockref("Column_1", (4 * i, 4 * j), dxfattribs={"layer": "POTEAUX"})
        d.saveas(f"{dossier}/plan.dxf")
        dxf2dwg = os.path.join(os.path.dirname(CONVERTISSEUR), "dxf2dwg")
        if not os.path.isfile(dxf2dwg):
            self.skipTest("dxf2dwg absent : impossible de fabriquer le DWG d'essai")
        subprocess.run([dxf2dwg, "-y", "-o", f"{dossier}/plan.dwg", f"{dossier}/plan.dxf"],
                       capture_output=True, timeout=60, check=False)
        with open(f"{dossier}/plan.dwg", "rb") as f:
            self.dwg = f.read()

    def tearDown(self):
        self.reglage_outil.disable()
        super().tearDown()

    def test_dwg_converti_puis_lu_comme_un_dxf(self):
        r = self.deposer("villa.dwg", self.dwg)
        self.assertEqual(r.status_code, 200, r.data)
        self.assertEqual(r.data["converti_depuis"], "dwg")
        self.assertIn("converti en DXF", r.data["avertissements"][0])
        self.assertEqual(r.data["nb_poteaux_detectes"], 9)
        self.projet.refresh_from_db()
        self.assertTrue(self.projet.fichier_import_origine.name.endswith(".dxf"))
        self.assertEqual(self.projet.parametres_import["converti_depuis"], "dwg")
        r = self.client.post(self.url, {"confirmer": True}, format="json")
        self.assertEqual(r.status_code, 201, r.data)
        self.assertEqual(self.projet.elements.filter(type_element=ElementStructurel.TypeElement.POTEAU).count(), 9)

    def test_dwg_en_mode_plan_d_architecte(self):
        r = self.deposer("villa.dwg", self.dwg, mode="architecte")
        self.assertEqual(r.status_code, 200, r.data)
        self.assertEqual((r.data["mode"], r.data["converti_depuis"]), ("architecte", "dwg"))
        self.assertGreater(r.data["nb_segments"], 0)
        self.assertEqual(self.projet.elements.count(), 0)

    def test_dwg_endommage(self):
        r = self.deposer("casse.dwg", b"AC1032" + b"\x00" * 200)
        self.assertEqual(r.status_code, 400)
        self.assertIn("DXF", r.data["erreur"])
