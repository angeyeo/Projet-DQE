"""Plans importés : dalles lues dans le DXF et variantes (issue #80).

DXF de test (en mm) : 3 × 3 poteaux à 0 / 4000 / 8000 ;
  - bloc « Slab_1 » : rectangle 0..4000 × 0..3500       -> Lx 3,50 ; Ly 4,00
  - polyligne fermée calque PLANCHER : 4000..8000 × 0..8000 -> Lx 4,00 ; Ly 8,00
  - polyligne fermée calque DALLES en L (aire ≠ rectangle englobant) -> non lue, signalée
"""
import shutil
import tempfile

import ezdxf
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import override_settings
from rest_framework.test import APITestCase

from moteur_calcul.import_dxf.lecture_dxf import analyser_fichier_dxf
from projets.models import ElementStructurel, Profil, Projet
from projets.tests_projets.utils import BAREME_TEST, authentifier

DALLE = ElementStructurel.TypeElement.DALLE


def dxf_avec_dalles(chemin):
    doc = ezdxf.new("R2010")
    doc.header["$INSUNITS"] = 4
    msp = doc.modelspace()
    col = doc.blocks.new("Column")
    col.add_lwpolyline([(-100, -100), (100, -100), (100, 100), (-100, 100)], close=True)
    for x in (0, 4000, 8000):
        for y in (0, 4000, 8000):
            msp.add_blockref("Column", (x, y), dxfattribs={"layer": "POTEAUX"})
    slab = doc.blocks.new("Slab_1")
    slab.add_lwpolyline([(0, 0), (4000, 0), (4000, 3500), (0, 3500)], close=True)
    msp.add_blockref("Slab_1", (0, 0), dxfattribs={"layer": "0"})
    msp.add_lwpolyline([(4000, 0), (8000, 0), (8000, 8000), (4000, 8000)], close=True, dxfattribs={"layer": "PLANCHER"})
    msp.add_lwpolyline([(0, 4000), (4000, 4000), (4000, 6000), (2000, 6000), (2000, 8000), (0, 8000)], close=True,
                       dxfattribs={"layer": "DALLES"})
    doc.saveas(chemin)


class Lecture(APITestCase):
    def test_dalles_rectangulaires_seulement(self):
        d = tempfile.mkdtemp()
        try:
            dxf_avec_dalles(f"{d}/p.dxf")
            r = analyser_fichier_dxf(f"{d}/p.dxf")
        finally:
            shutil.rmtree(d)
        dalles = sorted(r["dalles"], key=lambda x: x["x"])
        self.assertEqual([(x["lx"], x["ly"]) for x in dalles], [(3.5, 4.0), (4.0, 8.0)])
        self.assertEqual((dalles[0]["x"], dalles[0]["y"]), (2.0, 1.75))
        self.assertTrue(any("1 dalle(s) non lue(s)" in a for a in r["avertissements"]))


class ImportEtVariantes(APITestCase):
    def setUp(self):
        self.media = tempfile.mkdtemp()
        self.reglage = override_settings(MEDIA_ROOT=self.media)
        self.reglage.enable()
        self.user, self.cabinet = authentifier(self, role=Profil.Role.ADMIN, bareme=BAREME_TEST)
        self.projet = Projet.objects.create(nom="Import", entreprise=self.cabinet, usage_batiment="habitation",
                                            nb_niveaux=2, hauteur_etage=3.0, contrainte_sol_kn_m2=150)
        self.url = f"/api/projets/{self.projet.id}/importer_plan/"
        dxf_avec_dalles(f"{self.media}/p.dxf")
        with open(f"{self.media}/p.dxf", "rb") as f:
            self.apercu = self.client.post(self.url, {"fichier": SimpleUploadedFile("p.dxf", f.read())},
                                           format="multipart").data

    def tearDown(self):
        self.reglage.disable()
        shutil.rmtree(self.media, ignore_errors=True)

    def test_dalles_proposees_puis_creees_sur_accord(self):
        ids = [d["id"] for d in sorted(self.apercu["dalles_proposees"], key=lambda x: x["x"])]
        self.assertEqual(len(ids), 2)
        self.assertEqual(self.projet.elements.filter(type_element=DALLE).count(), 0)   # rien sans accord
        manuelle = ElementStructurel.objects.create(projet=self.projet, type_element=DALLE, identifiant="DM",
                                                    portee=3, longueur_m=4)
        r = self.client.post(self.url, {"confirmer": True, "dalles": [ids[0]]}, format="json")
        self.assertEqual(r.status_code, 201, r.data)
        d1 = self.projet.elements.get(type_element=DALLE, identifiant="D1")
        self.assertEqual((d1.portee, d1.longueur_m, d1.surface_m2, d1.origine_geometrie), (3.5, 4.0, 14.0, "plan"))
        self.assertIsNotNone(d1.resultat_calcul)
        # Nouvel import sans dalle gardée : les dalles du plan partent, la saisie reste.
        r = self.client.post(self.url, {"confirmer": True, "dalles": []}, format="json")
        self.assertEqual(r.status_code, 201, r.data)
        self.assertEqual(list(self.projet.elements.filter(type_element=DALLE).values_list("identifiant", flat=True)),
                         ["DM"])
        # Sans le champ « dalles » (ancien client) : dalles inchangées.
        self.client.post(self.url, {"confirmer": True, "dalles": [ids[1]]}, format="json")
        self.client.post(self.url, {"confirmer": True}, format="json")
        self.assertEqual(self.projet.elements.filter(type_element=DALLE).count(), 2)
        self.assertTrue(ElementStructurel.objects.filter(pk=manuelle.pk).exists())

    def test_variantes_sur_un_projet_importe(self):
        self.assertEqual(self.client.post(self.url, {"confirmer": True}, format="json").status_code, 201)
        avant = sorted(self.projet.elements.values_list("identifiant", "resultat_calcul"))
        r = self.client.post(f"/api/projets/{self.projet.id}/variantes/", {"variantes": [
            {"nom": "Sol 1 bar", "modifications": {"contrainte_sol_kn_m2": 100}}]}, format="json")
        self.assertEqual(r.status_code, 200, r.data)
        actuel, sol = r.data["variantes"]
        self.assertIsNone(sol["erreur"])
        self.assertGreater(sol["semelle_cote_max_cm"], actuel["semelle_cote_max_cm"])   # sol plus faible
        self.assertIsNotNone(sol["dqe"])
        self.assertEqual(sorted(self.projet.elements.values_list("identifiant", "resultat_calcul")), avant)
        r = self.client.post(f"/api/projets/{self.projet.id}/variantes/", {"variantes": [
            {"modifications": {"portee_x": 5}}]}, format="json")
        self.assertEqual(r.status_code, 400)
        self.assertIn("trame régulière", r.data["erreur"])
