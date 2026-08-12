"""
Tests de la descente de charges.
"""

from django.test import SimpleTestCase

from moteur_calcul.formules.descente_charges import (
    calculer_charge_permanente,
    calculer_charge_exploitation,
    calculer_charge_ponderee_elu,
    calculer_charge_totale_niveau,
    coefficient_degression,
    cumuler_charges_exploitation_degressives,
    calculer_charge_permanente_composee,
)
from moteur_calcul.validators import EntreeInvalide
from .donnees_test import (
    CAS_DESCENTE_CHARGES_1,
    CAS_DEGRESSION_R3,
    CAS_PLANCHER_COMPOSE,
)


class TestValidationEntrees(SimpleTestCase):
    """Validation des erreurs de saisie sur les entrées."""

    def test_surface_negative_rejetee(self):
        with self.assertRaises(EntreeInvalide):
            calculer_charge_exploitation(surface=-10, usage_batiment="habitation")

    def test_usage_inconnu_rejete(self):
        with self.assertRaises(EntreeInvalide):
            calculer_charge_exploitation(surface=30, usage_batiment="usage_invente")


class TestDescenteChargesReelle(SimpleTestCase):
    """Validation des résultats avec les vraies formules BTP."""

    def test_charge_permanente_cas_1(self):
        entrees = CAS_DESCENTE_CHARGES_1["entrees"]
        resultat = calculer_charge_permanente(
            surface=entrees["surface"], epaisseur_dalle=entrees["epaisseur_dalle"]
        )
        self.assertAlmostEqual(
            resultat, CAS_DESCENTE_CHARGES_1["charge_permanente_attendue"]
        )

    def test_charge_exploitation_cas_1(self):
        entrees = CAS_DESCENTE_CHARGES_1["entrees"]
        resultat = calculer_charge_exploitation(
            surface=entrees["surface"], usage_batiment=entrees["usage_batiment"]
        )
        self.assertAlmostEqual(
            resultat, CAS_DESCENTE_CHARGES_1["charge_exploitation_attendue"]
        )

    def test_charge_elu_par_niveau_cas_1(self):
        resultat = calculer_charge_ponderee_elu(
            charge_permanente=CAS_DESCENTE_CHARGES_1["charge_permanente_attendue"],
            charge_exploitation=CAS_DESCENTE_CHARGES_1["charge_exploitation_attendue"],
        )
        self.assertAlmostEqual(
            resultat, CAS_DESCENTE_CHARGES_1["charge_elu_par_niveau_attendue"]
        )

    def test_charge_cumulee_deux_niveaux_cas_1(self):
        charge_niveau = CAS_DESCENTE_CHARGES_1["charge_elu_par_niveau_attendue"]
        resultat = calculer_charge_totale_niveau([charge_niveau, charge_niveau])
        self.assertAlmostEqual(
            resultat, CAS_DESCENTE_CHARGES_1["charge_cumulee_2_niveaux_attendue"]
        )


class TestDegressionChargesExploitation(SimpleTestCase):
    """
    Phase 2, module 1. Le seul cas testé jusqu'ici (CAS_DESCENTE_CHARGES_1,
    2 niveaux) ne fait jamais vraiment jouer la dégression -- le
    coefficient à n=1 étage est 1,00, donc un bug dans la formule de
    dégression y passerait inaperçu. Ce cas R+3 (toiture + 3 étages)
    active vraiment les coefficients 0,95 et 0,90 du tableau NF P06-001.
    """

    def test_coefficients_degression_isoles(self):
        # Tableau NF P06-001 (constantes.COEFFICIENTS_DEGRESSION), indexé
        # par (n-1) : n=1 -> 1,00 ; n=2 -> 0,95 ; n=3 -> 0,90 ; n=4 -> 0,85
        self.assertEqual(coefficient_degression(1), 1.00)
        self.assertEqual(coefficient_degression(2), 0.95)
        self.assertEqual(coefficient_degression(3), 0.90)
        self.assertEqual(coefficient_degression(4), 0.85)

    def test_coefficient_degression_au_dela_du_tableau(self):
        # n=5 : formule (3+n)/(2n) = 8/10 = 0,80 -- doit se raccorder
        # sans discontinuité avec la valeur n=4 du tableau (0,90).
        self.assertAlmostEqual(coefficient_degression(5), 0.80)

    def test_cumul_degressif_batiment_r3(self):
        entrees = CAS_DEGRESSION_R3["entrees"]
        resultat = cumuler_charges_exploitation_degressives(
            charge_toiture_kn=entrees["charge_toiture_kn"],
            charges_etages_kn=entrees["charges_etages_kn"],
            usage_batiment=entrees["usage_batiment"],
        )
        self.assertEqual(resultat["cumuls_kn"], CAS_DEGRESSION_R3["cumuls_attendus_kn"])
        self.assertEqual(resultat["coefficients"], CAS_DEGRESSION_R3["coefficients_attendus"])
        self.assertTrue(resultat["degression_appliquee"])

    def test_degression_non_appliquee_pour_commerce(self):
        """
        Un commerce peut être plein à chaque niveau simultanément -- la
        dégression ne doit pas s'appliquer (voir USAGES_AVEC_DEGRESSION).
        """
        entrees = CAS_DEGRESSION_R3["entrees"]
        resultat = cumuler_charges_exploitation_degressives(
            charge_toiture_kn=entrees["charge_toiture_kn"],
            charges_etages_kn=entrees["charges_etages_kn"],
            usage_batiment="commerce",
        )
        self.assertFalse(resultat["degression_appliquee"])
        self.assertAlmostEqual(
            resultat["cumuls_kn"][-1], CAS_DEGRESSION_R3["cumul_sans_degression_kn"]
        )


class TestChargePermanenteComposee(SimpleTestCase):
    """Phase 2, module 2 : plancher réel à plusieurs couches."""

    def test_plancher_compose_charge_totale(self):
        entrees = CAS_PLANCHER_COMPOSE["entrees"]
        resultat = calculer_charge_permanente_composee(entrees["surface"], entrees["couches"])
        self.assertAlmostEqual(
            resultat["charge_totale_kn"], CAS_PLANCHER_COMPOSE["charge_totale_attendue_kn"]
        )
        self.assertAlmostEqual(
            resultat["charge_surfacique_totale_kn_m2"],
            CAS_PLANCHER_COMPOSE["charge_surfacique_totale_attendue_kn_m2"],
        )

    def test_plancher_compose_detail_par_couche(self):
        """Le détail doit lister exactement autant de lignes que de couches fournies."""
        entrees = CAS_PLANCHER_COMPOSE["entrees"]
        resultat = calculer_charge_permanente_composee(entrees["surface"], entrees["couches"])
        self.assertEqual(len(resultat["detail"]), len(entrees["couches"]))

    def test_plancher_sans_couches_rejete(self):
        with self.assertRaises(ValueError):
            calculer_charge_permanente_composee(25, [])

    def test_couche_incomplete_rejetee(self):
        with self.assertRaises(ValueError):
            calculer_charge_permanente_composee(25, [{"designation": "couche mystère"}])