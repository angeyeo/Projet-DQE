"""
Tests du dimensionnement des poteaux, poutres et semelles.
"""

from django.test import SimpleTestCase

from moteur_calcul.formules.dimensionnement_poteaux import dimensionner_poteau
from moteur_calcul.formules.dimensionnement_poutres import dimensionner_poutre
from moteur_calcul.formules.dimensionnement_semelles import dimensionner_semelle
from moteur_calcul.validators import EntreeInvalide
from .donnees_test import (
    CAS_DIMENSIONNEMENT_POTEAU_1,
    CAS_DIMENSIONNEMENT_POUTRE_1,
    CAS_DIMENSIONNEMENT_SEMELLE_1,
)


class TestValidationEntreesDimensionnement(SimpleTestCase):
    """Validation des bornes et limites d'entrée."""

    def test_charge_poteau_negative_rejetee(self):
        with self.assertRaises(EntreeInvalide):
            dimensionner_poteau(charge_calculee=-100, hauteur_poteau=3.0)

    def test_portee_poutre_hors_bornes_rejetee(self):
        with self.assertRaises(EntreeInvalide):
            dimensionner_poutre(portee=50, charge_lineaire=15)  # > PORTEE_MAX_M

    def test_charge_semelle_negative_rejetee(self):
        with self.assertRaises(EntreeInvalide):
            dimensionner_semelle(charge_poteau=-50, taux_travail_sol=2.0)


class TestDimensionnementReel(SimpleTestCase):
    """Validation des résultats réels de dimensionnement."""

    def test_poteau_cas_1(self):
        entrees = CAS_DIMENSIONNEMENT_POTEAU_1["entrees"]
        resultat = dimensionner_poteau(**entrees)
        self.assertEqual(resultat, CAS_DIMENSIONNEMENT_POTEAU_1["resultat_attendu"])