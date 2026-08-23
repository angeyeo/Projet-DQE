"""
Tests d'isolation de moteur_calcul/formules/complements_plan_coffrage.py
-- Phase C (dallage, joints de dilatation), voir
Feuille_de_route_Import_Plan_Automatique.md.

Fonctions pures, testées indépendamment de Django/DXF.
"""

from django.test import SimpleTestCase

from moteur_calcul.formules.complements_plan_coffrage import (
    calculer_contour_dallage,
    calculer_joints_dilatation,
)


class TestCalculerContourDallage(SimpleTestCase):

    def test_rectangle_avec_marge_par_defaut(self):
        positions = [(0, 0), (5, 0), (0, 4), (5, 4)]
        contour = calculer_contour_dallage(positions, marge_m=0.2)

        self.assertEqual(len(contour), 5)
        self.assertEqual(contour[0], contour[-1])  # fermé
        xs = [p[0] for p in contour]
        ys = [p[1] for p in contour]
        self.assertAlmostEqual(min(xs), -0.2)
        self.assertAlmostEqual(max(xs), 5.2)
        self.assertAlmostEqual(min(ys), -0.2)
        self.assertAlmostEqual(max(ys), 4.2)

    def test_marge_nulle_colle_a_l_emprise_des_poteaux(self):
        positions = [(0, 0), (10, 7)]
        contour = calculer_contour_dallage(positions, marge_m=0.0)
        xs = [p[0] for p in contour]
        ys = [p[1] for p in contour]
        self.assertAlmostEqual(min(xs), 0.0)
        self.assertAlmostEqual(max(xs), 10.0)
        self.assertAlmostEqual(min(ys), 0.0)
        self.assertAlmostEqual(max(ys), 7.0)

    def test_positions_vides_leve_value_error(self):
        with self.assertRaises(ValueError):
            calculer_contour_dallage([])

    def test_marge_negative_leve_value_error(self):
        with self.assertRaises(ValueError):
            calculer_contour_dallage([(0, 0), (1, 1)], marge_m=-0.1)

    def test_un_seul_point_donne_un_carre_de_cote_2x_marge(self):
        contour = calculer_contour_dallage([(3, 3)], marge_m=0.5)
        xs = [p[0] for p in contour]
        ys = [p[1] for p in contour]
        self.assertAlmostEqual(max(xs) - min(xs), 1.0)
        self.assertAlmostEqual(max(ys) - min(ys), 1.0)


class TestCalculerJointsDilatation(SimpleTestCase):

    def test_batiment_sous_le_seuil_ne_genere_aucun_joint(self):
        positions = [(0, 0), (20, 0), (0, 15), (20, 15)]
        resultat = calculer_joints_dilatation(positions, distance_max_m=25.0)
        self.assertEqual(resultat["joints"], [])
        self.assertEqual(resultat["avertissements"], [])

    def test_batiment_de_60m_en_x_genere_2_joints_en_3_troncons_egaux(self):
        positions = [(0, 0), (60, 0), (0, 10), (60, 10)]
        resultat = calculer_joints_dilatation(positions, distance_max_m=25.0)

        joints_x = [j for j in resultat["joints"] if j["axe"] == "X"]
        self.assertEqual(len(joints_x), 2)
        # Répartition régulière : tronçons de 20 m (60 / 3), pas 25+25+10.
        positions_x = sorted(j["position"] for j in joints_x)
        self.assertAlmostEqual(positions_x[0], 20.0)
        self.assertAlmostEqual(positions_x[1], 40.0)
        self.assertEqual(len(resultat["avertissements"]), 1)

    def test_joint_traverse_toute_la_largeur_avec_marge(self):
        positions = [(0, 0), (60, 0), (0, 10), (60, 10)]
        resultat = calculer_joints_dilatation(positions, distance_max_m=25.0, marge_m=0.2)
        joint = resultat["joints"][0]
        self.assertAlmostEqual(joint["y1"], -0.2)
        self.assertAlmostEqual(joint["y2"], 10.2)

    def test_batiment_long_dans_les_deux_sens_genere_des_joints_sur_les_2_axes(self):
        positions = [(0, 0), (55, 0), (0, 40), (55, 40)]
        resultat = calculer_joints_dilatation(positions, distance_max_m=25.0)
        axes = {j["axe"] for j in resultat["joints"]}
        self.assertEqual(axes, {"X", "Y"})
        self.assertEqual(len(resultat["avertissements"]), 2)

    def test_distance_max_non_positive_leve_value_error(self):
        with self.assertRaises(ValueError):
            calculer_joints_dilatation([(0, 0), (10, 10)], distance_max_m=0)

    def test_positions_vides_leve_value_error(self):
        with self.assertRaises(ValueError):
            calculer_joints_dilatation([])
