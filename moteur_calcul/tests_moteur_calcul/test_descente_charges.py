"""
Tests de la descente de charges.
"""

from django.test import SimpleTestCase

from moteur_calcul.formules.descente_charges import (
    calculer_charge_permanente,
    calculer_charge_exploitation,
    calculer_charge_ponderee_elu,
    calculer_charge_totale_niveau,
)
from moteur_calcul.validators import EntreeInvalide
from .donnees_test import CAS_DESCENTE_CHARGES_1


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