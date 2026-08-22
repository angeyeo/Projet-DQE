"""
Tests API de ProjetViewSet.importer_plan -- endpoint de Samuel (Phase A
aperçu + Phase B confirmation) de la feuille de route "Import plan
automatique". Réutilise le même constructeur de fixture IFC en mémoire
que moteur_calcul/tests_moteur_calcul/test_ifc.py.
"""

import ifcopenshell
import ifcopenshell.api
from django.core.files.uploadedfile import SimpleUploadedFile
from rest_framework.test import APITestCase

from projets.models import Projet, ElementStructurel

run = ifcopenshell.api.run


def _construire_ifc_bytes(xs, ys, elevations=(0.0, 3.0)):
    model = ifcopenshell.file(schema="IFC4")
    project = run("root.create_entity", model, ifc_class="IfcProject", name="Test")
    run("unit.assign_unit", model, length={"is_metric": True, "raw": "METERS"})

    site = run("root.create_entity", model, ifc_class="IfcSite", name="Site")
    building = run("root.create_entity", model, ifc_class="IfcBuilding", name="Bâtiment")
    run("aggregate.assign_object", model, relating_object=project, products=[site])
    run("aggregate.assign_object", model, relating_object=site, products=[building])

    storeys = []
    for i, elev in enumerate(elevations):
        storey = run("root.create_entity", model, ifc_class="IfcBuildingStorey", name=f"Niveau {i}")
        storey.Elevation = elev
        run("aggregate.assign_object", model, relating_object=building, products=[storey])
        storeys.append(storey)

    for xi, x in enumerate(xs):
        for yi, y in enumerate(ys):
            col = run("root.create_entity", model, ifc_class="IfcColumn", name=f"Poteau_{xi}_{yi}")
            run(
                "geometry.edit_object_placement", model, product=col,
                matrix=[[1, 0, 0, x], [0, 1, 0, y], [0, 0, 1, 0], [0, 0, 0, 1]],
            )
            run("spatial.assign_container", model, relating_structure=storeys[0], products=[col])

    return model.to_string().encode("utf-8")


class TestImporterPlanApercu(APITestCase):
    """Phase A : upload + aperçu, aucun élément créé."""

    def setUp(self):
        self.projet = Projet.objects.create(nom="Villa test")
        self.ifc_bytes = _construire_ifc_bytes(xs=[0.0, 5.0, 10.0], ys=[0.0, 4.0])

    def _url(self):
        return f"/api/projets/{self.projet.id}/importer_plan/"

    def test_apercu_detecte_les_parametres_sans_creer_d_elements(self):
        fichier = SimpleUploadedFile("plan.ifc", self.ifc_bytes, content_type="application/octet-stream")
        response = self.client.post(self._url(), {"fichier": fichier}, format="multipart")

        self.assertEqual(response.status_code, 200, response.data)
        self.assertEqual(response.data["nb_travees_x"], 2)
        self.assertEqual(response.data["nb_travees_y"], 1)
        self.assertAlmostEqual(response.data["portee_x"], 5.0, places=1)
        self.assertAlmostEqual(response.data["portee_y"], 4.0, places=1)
        self.assertNotIn("poteaux", response.data)
        self.assertEqual(ElementStructurel.objects.filter(projet=self.projet).count(), 0)

        self.projet.refresh_from_db()
        self.assertTrue(bool(self.projet.fichier_import_origine))

    def test_sans_fichier_ni_confirmation_renvoie_400(self):
        response = self.client.post(self._url(), {}, format="multipart")
        self.assertEqual(response.status_code, 400)

    def test_fichier_invalide_renvoie_400_pas_500(self):
        fichier = SimpleUploadedFile("plan.ifc", b"pas un ifc", content_type="application/octet-stream")
        response = self.client.post(self._url(), {"fichier": fichier}, format="multipart")
        self.assertEqual(response.status_code, 400)
        self.assertIn("erreur", response.data)


class TestImporterPlanConfirmation(APITestCase):
    """Phase B : confirmation, création réelle des éléments."""

    def setUp(self):
        self.projet = Projet.objects.create(
            nom="Villa test", hauteur_etage=3.0, nb_niveaux=2, charge_exploitation=1.5,
        )
        self.ifc_bytes = _construire_ifc_bytes(xs=[0.0, 5.0, 10.0], ys=[0.0, 4.0])

    def _url(self):
        return f"/api/projets/{self.projet.id}/importer_plan/"

    def test_confirmation_sans_apercu_prealable_renvoie_400(self):
        response = self.client.post(self._url(), {"confirmer": "true"}, format="json")
        self.assertEqual(response.status_code, 400)

    def test_confirmation_cree_poteaux_semelles_et_poutres(self):
        fichier = SimpleUploadedFile("plan.ifc", self.ifc_bytes, content_type="application/octet-stream")
        apercu = self.client.post(self._url(), {"fichier": fichier}, format="multipart")
        self.assertEqual(apercu.status_code, 200, apercu.data)

        response = self.client.post(self._url(), {"confirmer": True}, format="json")
        self.assertEqual(response.status_code, 201, response.data)

        poteaux = ElementStructurel.objects.filter(
            projet=self.projet, type_element=ElementStructurel.TypeElement.POTEAU
        )
        semelles = ElementStructurel.objects.filter(
            projet=self.projet, type_element=ElementStructurel.TypeElement.SEMELLE
        )
        poutres = ElementStructurel.objects.filter(
            projet=self.projet, type_element=ElementStructurel.TypeElement.POUTRE
        )

        # Grille 3x2 -> 6 poteaux réels détectés au niveau bas.
        self.assertEqual(poteaux.count(), 6)
        self.assertEqual(semelles.count(), 6)
        self.assertGreater(poutres.count(), 0)

        for semelle in semelles:
            self.assertIsNotNone(semelle.poteau_associe)
            self.assertIsNotNone(semelle.resultat_calcul)

        for poteau in poteaux:
            self.assertIsNotNone(poteau.resultat_calcul)

    def test_confirmation_est_idempotente(self):
        fichier = SimpleUploadedFile("plan.ifc", self.ifc_bytes, content_type="application/octet-stream")
        self.client.post(self._url(), {"fichier": fichier}, format="multipart")
        self.client.post(self._url(), {"confirmer": True}, format="json")
        self.client.post(self._url(), {"confirmer": True}, format="json")

        self.assertEqual(
            ElementStructurel.objects.filter(
                projet=self.projet, type_element=ElementStructurel.TypeElement.POTEAU
            ).count(),
            6,
        )