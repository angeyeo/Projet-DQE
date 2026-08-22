"""
Tests d'isolation de moteur_calcul/import_ifc/lecture_ifc.py -- Phase A
de la feuille de route "Import plan automatique".

Comme test_trame.py, ces fonctions ne touchent pas la base : les
fixtures IFC sont construites en mémoire avec ifcopenshell.api
directement dans les tests, pas de fichier externe à maintenir.
"""

import tempfile
import os

import ifcopenshell
import ifcopenshell.api
from django.test import SimpleTestCase

from moteur_calcul.import_ifc.lecture_ifc import (
    ouvrir_ifc,
    extraire_poteaux,
    extraire_niveaux,
    detecter_parametres_trame,
    analyser_fichier_ifc,
    _clusteriser_1d,
    FichierIFCInvalide,
    AucunPoteauDetecte,
)

run = ifcopenshell.api.run


def _construire_modele_ifc(xs, ys, elevations=(0.0, 3.0)):
    """
    Construit un modèle IFC en mémoire avec un poteau à chaque
    combinaison (x, y) du premier niveau, et les IfcBuildingStorey
    correspondant à `elevations`.
    """
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

    return model


class TestClusteriser1D(SimpleTestCase):
    def test_valeurs_alignees_exactement(self):
        self.assertEqual(_clusteriser_1d([0.0, 5.0, 10.0]), [0.0, 5.0, 10.0])

    def test_valeurs_legerement_decalees_regroupees(self):
        # écarts de 2 à 3 cm : sous la tolérance (15 cm par défaut)
        resultat = _clusteriser_1d([0.0, 0.02, 4.98, 5.03, 9.99])
        self.assertEqual(len(resultat), 3)
        self.assertAlmostEqual(resultat[0], 0.01, places=2)
        self.assertAlmostEqual(resultat[1], 5.005, places=2)

    def test_valeurs_au_dela_de_la_tolerance_separees(self):
        resultat = _clusteriser_1d([0.0, 0.20], tolerance=0.15)
        self.assertEqual(len(resultat), 2)

    def test_liste_vide(self):
        self.assertEqual(_clusteriser_1d([]), [])


class TestExtrairePoteauxEtNiveaux(SimpleTestCase):
    def test_extraire_poteaux_positions_et_niveau(self):
        model = _construire_modele_ifc(xs=[0.0, 5.0], ys=[0.0, 4.0])
        poteaux = extraire_poteaux(model)

        self.assertEqual(len(poteaux), 4)
        positions = {(round(p["x"], 2), round(p["y"], 2)) for p in poteaux}
        self.assertEqual(positions, {(0.0, 0.0), (0.0, 4.0), (5.0, 0.0), (5.0, 4.0)})
        self.assertTrue(all(p["niveau_nom"] == "Niveau 0" for p in poteaux))

    def test_extraire_poteaux_leve_si_aucun_poteau(self):
        model = _construire_modele_ifc(xs=[], ys=[])
        with self.assertRaises(AucunPoteauDetecte):
            extraire_poteaux(model)

    def test_extraire_niveaux_tries_par_elevation(self):
        model = _construire_modele_ifc(xs=[0.0], ys=[0.0], elevations=[6.0, 0.0, 3.0])
        niveaux = extraire_niveaux(model)
        self.assertEqual([n["elevation_m"] for n in niveaux], [0.0, 3.0, 6.0])


class TestDetecterParametresTrame(SimpleTestCase):
    def test_grille_reguliere_5x2(self):
        poteaux = [
            {"x": i * 5.0, "y": j * 4.0, "z": 0, "niveau_nom": "RDC", "niveau_elevation_m": 0.0}
            for i in range(6) for j in range(3)
        ]
        niveaux = [
            {"nom": "RDC", "elevation_m": 0.0, "guid": "1"},
            {"nom": "R+1", "elevation_m": 3.0, "guid": "2"},
        ]
        resultat = detecter_parametres_trame(poteaux, niveaux)

        self.assertEqual(resultat["nb_travees_x"], 5)
        self.assertEqual(resultat["nb_travees_y"], 2)
        self.assertAlmostEqual(resultat["portee_x"], 5.0, places=2)
        self.assertAlmostEqual(resultat["portee_y"], 4.0, places=2)
        self.assertEqual(resultat["nb_niveaux"], 2)
        self.assertAlmostEqual(resultat["hauteur_etage"], 3.0, places=2)
        self.assertEqual(resultat["nb_poteaux_detectes"], 18)
        self.assertEqual(resultat["avertissements"], [])

    def test_grille_legerement_irreguliere_sans_avertissement(self):
        # écarts de quelques cm (relevé réel) : sous le seuil d'irrégularité
        xs = [0.0, 5.02, 9.98, 15.01]
        poteaux = [
            {"x": x, "y": y, "z": 0, "niveau_nom": "RDC", "niveau_elevation_m": 0.0}
            for x in xs for y in [0.0, 4.0]
        ]
        resultat = detecter_parametres_trame(poteaux, niveaux=None)
        self.assertEqual(resultat["nb_travees_x"], 3)
        self.assertAlmostEqual(resultat["portee_x"], 5.0, delta=0.05)
        self.assertEqual(
            [a for a in resultat["avertissements"] if "irrégulières" in a], []
        )

    def test_grille_nettement_irreguliere_avec_avertissement(self):
        poteaux = [
            {"x": 0.0, "y": 0.0, "z": 0, "niveau_nom": "RDC", "niveau_elevation_m": 0.0},
            {"x": 4.0, "y": 0.0, "z": 0, "niveau_nom": "RDC", "niveau_elevation_m": 0.0},
            {"x": 9.5, "y": 0.0, "z": 0, "niveau_nom": "RDC", "niveau_elevation_m": 0.0},
            {"x": 0.0, "y": 4.0, "z": 0, "niveau_nom": "RDC", "niveau_elevation_m": 0.0},
            {"x": 4.0, "y": 4.0, "z": 0, "niveau_nom": "RDC", "niveau_elevation_m": 0.0},
            {"x": 9.5, "y": 4.0, "z": 0, "niveau_nom": "RDC", "niveau_elevation_m": 0.0},
        ]
        resultat = detecter_parametres_trame(poteaux, niveaux=None)
        self.assertTrue(any("irrégulières" in a and "X" in a for a in resultat["avertissements"]))

    def test_un_seul_alignement_pas_de_portee(self):
        poteaux = [
            {"x": 0.0, "y": 0.0, "z": 0, "niveau_nom": "RDC", "niveau_elevation_m": 0.0},
            {"x": 0.0, "y": 4.0, "z": 0, "niveau_nom": "RDC", "niveau_elevation_m": 0.0},
        ]
        resultat = detecter_parametres_trame(poteaux, niveaux=None)
        self.assertEqual(resultat["nb_travees_x"], 0)
        self.assertIsNone(resultat["portee_x"])
        self.assertTrue(any("axe X" in a for a in resultat["avertissements"]))

    def test_nombre_de_poteaux_incoherent_avec_grille_reguliere(self):
        # Grille 2x1 attendue (3x2=6 poteaux) mais un poteau manquant
        poteaux = [
            {"x": 0.0, "y": 0.0, "z": 0, "niveau_nom": "RDC", "niveau_elevation_m": 0.0},
            {"x": 5.0, "y": 0.0, "z": 0, "niveau_nom": "RDC", "niveau_elevation_m": 0.0},
            {"x": 10.0, "y": 0.0, "z": 0, "niveau_nom": "RDC", "niveau_elevation_m": 0.0},
            {"x": 0.0, "y": 4.0, "z": 0, "niveau_nom": "RDC", "niveau_elevation_m": 0.0},
            {"x": 5.0, "y": 4.0, "z": 0, "niveau_nom": "RDC", "niveau_elevation_m": 0.0},
            # (10.0, 4.0) manquant
        ]
        resultat = detecter_parametres_trame(poteaux, niveaux=None)
        self.assertTrue(any("compterait" in a for a in resultat["avertissements"]))


class TestOuvrirEtAnalyserFichier(SimpleTestCase):
    def test_ouvrir_ifc_leve_sur_fichier_invalide(self):
        with tempfile.NamedTemporaryFile(suffix=".ifc", mode="w", delete=False) as f:
            f.write("ceci n'est pas un fichier IFC")
            chemin = f.name
        try:
            with self.assertRaises(FichierIFCInvalide):
                ouvrir_ifc(chemin)
        finally:
            os.unlink(chemin)

    def test_analyser_fichier_ifc_pipeline_complet(self):
        model = _construire_modele_ifc(
            xs=[0.0, 5.0, 10.0], ys=[0.0, 4.0], elevations=[0.0, 3.0, 6.0],
        )
        with tempfile.NamedTemporaryFile(suffix=".ifc", delete=False) as f:
            chemin = f.name
        try:
            model.write(chemin)
            resultat = analyser_fichier_ifc(chemin)

            self.assertEqual(resultat["nb_travees_x"], 2)
            self.assertEqual(resultat["nb_travees_y"], 1)
            self.assertAlmostEqual(resultat["portee_x"], 5.0, places=2)
            self.assertAlmostEqual(resultat["portee_y"], 4.0, places=2)
            self.assertEqual(resultat["nb_niveaux"], 3)
            self.assertAlmostEqual(resultat["hauteur_etage"], 3.0, places=2)
            self.assertEqual(resultat["nb_poteaux_detectes"], 6)
            self.assertIn("poteaux", resultat)  # conservés pour la Phase B
        finally:
            os.unlink(chemin)