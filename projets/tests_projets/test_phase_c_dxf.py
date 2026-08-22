"""
Tests Phase C -- liaison poteau_origine/poteau_destination sur les
ouvrages linéaires (poutres, longrines, chaînages identifiés) et tracé
DXF correspondant. Couvre les deux chemins de création (generer_trame/
et importer_plan/ confirmé) ainsi que _ouvrages_lineaires_pour_dxf().
"""

import ifcopenshell
import ifcopenshell.api
from django.core.files.uploadedfile import SimpleUploadedFile
from rest_framework.test import APITestCase

from projets.models import Projet, ElementStructurel
from projets.views import _ouvrages_lineaires_pour_dxf

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


class TestPoteauOrigineDestinationGenererTrame(APITestCase):
    """generer_trame/ doit relier chaque poutre à ses 2 poteaux exacts."""

    def setUp(self):
        self.projet = Projet.objects.create(
            nom="Villa test", nb_travees_x=2, nb_travees_y=1, portee_x=5.0, portee_y=4.0,
        )

    def test_poutres_px_relient_les_bons_poteaux_en_x(self):
        self.client.post(f"/api/projets/{self.projet.id}/generer_trame/", {}, format="json")

        poutre_px = ElementStructurel.objects.get(identifiant="PX_0_0")
        self.assertIsNotNone(poutre_px.poteau_origine)
        self.assertIsNotNone(poutre_px.poteau_destination)
        self.assertEqual(poutre_px.poteau_origine.identifiant, "P_0_0")
        self.assertEqual(poutre_px.poteau_destination.identifiant, "P_1_0")

    def test_poutres_py_relient_les_bons_poteaux_en_y(self):
        self.client.post(f"/api/projets/{self.projet.id}/generer_trame/", {}, format="json")

        poutre_py = ElementStructurel.objects.get(identifiant="PY_0_0")
        self.assertEqual(poutre_py.poteau_origine.identifiant, "P_0_0")
        self.assertEqual(poutre_py.poteau_destination.identifiant, "P_0_1")


class TestPoteauOrigineDestinationImporterPlan(APITestCase):
    """importer_plan/ (confirmation) doit aussi relier les poutres réelles."""

    def setUp(self):
        self.projet = Projet.objects.create(nom="Villa test", hauteur_etage=3.0, nb_niveaux=1)
        self.ifc_bytes = _construire_ifc_bytes(xs=[0.0, 5.0], ys=[0.0, 4.0])

    def test_poutre_reelle_a_ses_2_poteaux_renseignes(self):
        fichier = SimpleUploadedFile("plan.ifc", self.ifc_bytes, content_type="application/octet-stream")
        self.client.post(f"/api/projets/{self.projet.id}/importer_plan/", {"fichier": fichier}, format="multipart")
        self.client.post(f"/api/projets/{self.projet.id}/importer_plan/", {"confirmer": True}, format="json")

        poutres = ElementStructurel.objects.filter(
            projet=self.projet, type_element=ElementStructurel.TypeElement.POUTRE
        )
        self.assertGreater(poutres.count(), 0)
        for poutre in poutres:
            self.assertIsNotNone(poutre.poteau_origine)
            self.assertIsNotNone(poutre.poteau_destination)
            self.assertNotEqual(poutre.poteau_origine_id, poutre.poteau_destination_id)


class TestOuvragesLineairesPourDxf(APITestCase):
    """Adaptateur _ouvrages_lineaires_pour_dxf() et export DXF de bout en bout."""

    def setUp(self):
        self.projet = Projet.objects.create(
            nom="Villa test", nb_travees_x=1, nb_travees_y=1, portee_x=4.0, portee_y=3.0,
        )

    def test_adaptateur_regroupe_par_type_avec_coordonnees_des_2_poteaux(self):
        self.client.post(f"/api/projets/{self.projet.id}/generer_trame/", {}, format="json")

        ouvrages = _ouvrages_lineaires_pour_dxf(self.projet.elements.all())
        self.assertIn("poutres", ouvrages)
        self.assertIn("longrines", ouvrages)
        self.assertIn("chainages_identifies", ouvrages)
        self.assertGreater(len(ouvrages["poutres"]), 0)
        self.assertEqual(len(ouvrages["longrines"]), 0)  # aucune créée par generer_trame

        premiere = ouvrages["poutres"][0]
        for cle in ("identifiant", "x1", "y1", "x2", "y2"):
            self.assertIn(cle, premiere)

    def test_ouvrage_sans_poteau_origine_est_ignore_sans_erreur(self):
        # Poutre "historique" créée avant l'ajout des champs -- ne doit
        # pas faire planter l'adaptateur, juste être absente du résultat.
        ElementStructurel.objects.create(
            projet=self.projet,
            identifiant="PX_ancien",
            type_element=ElementStructurel.TypeElement.POUTRE,
            position_x=1.0,
            position_y=1.0,
        )
        ouvrages = _ouvrages_lineaires_pour_dxf(self.projet.elements.all())
        identifiants = [o["identifiant"] for o in ouvrages["poutres"]]
        self.assertNotIn("PX_ancien", identifiants)

    def test_export_dxf_complet_ne_plante_pas_avec_poutres(self):
        self.client.post(f"/api/projets/{self.projet.id}/generer_trame/", {}, format="json")

        response = self.client.get(f"/api/projets/{self.projet.id}/plan_fondation/?export=dxf")
        self.assertEqual(response.status_code, 200)
        contenu = response.content.decode("utf-8", errors="ignore")
        self.assertIn("POUTRES", contenu)

    def test_ancien_parametre_format_dxf_declenche_toujours_un_404_drf(self):
        # Non-régression inverse : "format" reste intercepté par la
        # négociation de contenu de DRF avant même d'atteindre la vue
        # (voir docstring de plan_fondation) -- impossible à contourner
        # depuis la vue elle-même, d'où le renommage vers "export".
        # Ce test documente le piège pour ne pas le réintroduire.
        self.client.post(f"/api/projets/{self.projet.id}/generer_trame/", {}, format="json")
        response = self.client.get(f"/api/projets/{self.projet.id}/plan_fondation/?format=dxf")
        self.assertEqual(response.status_code, 404)