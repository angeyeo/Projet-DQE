"""
Tests de la méthode de Caquot (poutres continues).

Comme test_dimensionnement.py : les résultats "riches" (dimensionner_poutre_continue)
sont vérifiés champ par champ, pas par égalité stricte du dict entier.
"""

from django.test import SimpleTestCase

from moteur_calcul.formules.methode_caquot import (
    calculer_moments_caquot,
    calculer_moment_appui_caquot,
    calculer_moment_travee_caquot,
    portees_reduites_caquot,
    valider_donnees_caquot,
)
from moteur_calcul.formules.dimensionnement_poutres import dimensionner_poutre_continue
from moteur_calcul.validators import EntreeInvalide


class TestValidationEntreesCaquot(SimpleTestCase):
    def test_moins_de_deux_travees_rejete(self):
        with self.assertRaises(EntreeInvalide):
            valider_donnees_caquot([5.0], [20.0])

    def test_listes_de_longueurs_differentes_rejetees(self):
        with self.assertRaises(EntreeInvalide):
            valider_donnees_caquot([5.0, 4.0], [20.0])

    def test_charge_negative_rejetee(self):
        with self.assertRaises(EntreeInvalide):
            valider_donnees_caquot([5.0, 4.0], [20.0, -5.0])

    def test_portee_hors_bornes_rejetee(self):
        with self.assertRaises(EntreeInvalide):
            valider_donnees_caquot([5.0, 50.0], [20.0, 20.0])


class TestPorteesReduites(SimpleTestCase):
    def test_travees_de_rive_non_reduites(self):
        # 3 travées : seule celle du milieu (indice 1) est réduite.
        reduites = portees_reduites_caquot([4.0, 5.0, 4.0], minore=True)
        self.assertEqual(reduites, [4.0, 4.0, 4.0])

    def test_non_minore_garde_portees_reelles_partout(self):
        reduites = portees_reduites_caquot([4.0, 5.0, 4.0], minore=False)
        self.assertEqual(reduites, [4.0, 5.0, 4.0])


class TestMomentsCaquot(SimpleTestCase):
    def test_deux_travees_egales_formule_classique(self):
        """
        Cas de référence vérifiable à la main : 2 travées égales de 5 m,
        même charge 20 kN/m des deux côtés -> portées non réduites
        (travées de rive des deux côtés), moment d'appui central :
            M = -(q.l³ + q.l³) / (8,5 x 2l) = -q.l²/8.5
        """
        resultat = calculer_moments_caquot([5.0, 5.0], [20.0, 20.0])
        attendu = -20.0 * 5.0 ** 2 / 8.5
        self.assertAlmostEqual(resultat["moments_appuis_knm"][1], attendu, places=1)
        self.assertEqual(resultat["moments_appuis_knm"][0], 0.0)
        self.assertEqual(resultat["moments_appuis_knm"][-1], 0.0)

    def test_moment_appui_isole_coherent_avec_calculer_moments_caquot(self):
        m_direct = calculer_moment_appui_caquot(20.0, 5.0, 20.0, 5.0)
        resultat = calculer_moments_caquot([5.0, 5.0], [20.0, 20.0])
        self.assertAlmostEqual(m_direct, resultat["moments_appuis_knm"][1], places=1)

    def test_symetrie_charge_donne_moments_travees_egaux(self):
        """3 travées symétriques (4/5/4), même charge -> travées de rive identiques."""
        resultat = calculer_moments_caquot([4.0, 5.0, 4.0], [25.0, 25.0, 25.0])
        self.assertAlmostEqual(
            resultat["moments_travees_knm"][0], resultat["moments_travees_knm"][2], places=1
        )

    def test_travee_isolee_position_max_au_milieu_si_appuis_symetriques(self):
        """Moments d'appui égaux des deux côtés -> le max en travée est à l/2."""
        moment, position = calculer_moment_travee_caquot(5.0, 20.0, -50.0, -50.0)
        self.assertAlmostEqual(position, 2.5, places=2)

    def test_reduction_moment_travee_par_rapport_isostatique(self):
        """
        La continuité réduit toujours le moment en travée par rapport au
        cas isostatique équivalent (ql²/8) : les appuis reprennent une
        partie de la flexion.
        """
        resultat = calculer_moments_caquot([5.0, 5.0], [20.0, 20.0])
        moment_isostatique = 20.0 * 5.0 ** 2 / 8
        self.assertLess(resultat["moments_travees_knm"][0], moment_isostatique)


class TestDimensionnerPoutreContinue(SimpleTestCase):
    def test_structure_resultat(self):
        resultat = dimensionner_poutre_continue(
            portees=[4.0, 5.0, 4.0], charges_lineaires=[25.0, 25.0, 25.0], largeur=0.20,
        )
        self.assertEqual(len(resultat["resultats_travees"]), 3)
        self.assertEqual(len(resultat["resultats_appuis"]), 4)
        # Appuis de rive = None (pas de chapeau à ferrailler)
        self.assertIsNone(resultat["resultats_appuis"][0])
        self.assertIsNone(resultat["resultats_appuis"][-1])
        # Appuis intermédiaires = un dict de ferraillage
        self.assertIsNotNone(resultat["resultats_appuis"][1])
        self.assertIn("barres_proposees", resultat["resultats_appuis"][1])

    def test_hauteur_basee_sur_la_plus_grande_portee(self):
        resultat = dimensionner_poutre_continue(
            portees=[3.0, 6.0, 3.0], charges_lineaires=[20.0, 20.0, 20.0],
        )
        # ratio poutre continue : portée / 10 à 12 -> h = 6.0/10 = 0.60 m = 60 cm
        self.assertAlmostEqual(resultat["hauteur_cm"], 60.0, places=1)

    def test_chaque_travee_a_un_ferraillage_non_fragile(self):
        resultat = dimensionner_poutre_continue(
            portees=[4.0, 5.0, 4.0], charges_lineaires=[25.0, 25.0, 25.0],
        )
        for travee in resultat["resultats_travees"]:
            self.assertTrue(travee["non_fragilite_respectee"])

    def test_moins_de_deux_travees_rejete(self):
        with self.assertRaises(EntreeInvalide):
            dimensionner_poutre_continue(portees=[5.0], charges_lineaires=[20.0])