"""
Tests de la descente de charges.
"""

from django.test import SimpleTestCase

from moteur_calcul.formules.descente_charges import (
    calculer_charge_permanente,
    calculer_charge_exploitation,
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

    def test_cas_1(self):
        entrees = CAS_DESCENTE_CHARGES_1["entrees"]
        resultat = calculer_charge_exploitation(
            surface=entrees["surface"], usage_batiment=entrees["usage_batiment"]
        )
        self.assertAlmostEqual(resultat, CAS_DESCENTE_CHARGES_1["resultat_attendu"])