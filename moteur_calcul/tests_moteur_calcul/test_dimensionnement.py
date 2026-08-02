"""
Tests du dimensionnement des poteaux, poutres et semelles.
Même logique que test_descente_charges.py : on vérifie le branchement
du squelette maintenant, on active les vraies assertions mercredi.
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
    def test_charge_poteau_negative_rejetee(self):
        with self.assertRaises(EntreeInvalide):
            dimensionner_poteau(charge_calculee=-100, hauteur_poteau=3.0)

    def test_portee_poutre_hors_bornes_rejetee(self):
        with self.assertRaises(EntreeInvalide):
            dimensionner_poutre(portee=50, charge_lineaire=15)  # > PORTEE_MAX_M

    def test_charge_semelle_negative_rejetee(self):
        with self.assertRaises(EntreeInvalide):
            dimensionner_semelle(charge_poteau=-50, taux_travail_sol=2.0)


class TestFormulesEnAttente(SimpleTestCase):
    def test_dimensionnement_poteau_pas_encore_implemente(self):
        entrees = CAS_DIMENSIONNEMENT_POTEAU_1["entrees"]
        with self.assertRaises(NotImplementedError):
            dimensionner_poteau(**entrees)

    def test_dimensionnement_poutre_pas_encore_implemente(self):
        entrees = CAS_DIMENSIONNEMENT_POUTRE_1["entrees"]
        with self.assertRaises(NotImplementedError):
            dimensionner_poutre(**entrees)

    def test_dimensionnement_semelle_pas_encore_implemente(self):
        entrees = CAS_DIMENSIONNEMENT_SEMELLE_1["entrees"]
        with self.assertRaises(NotImplementedError):
            dimensionner_semelle(**entrees)


# --- À activer mercredi, une fois les formules renseignées ---
#
# class TestDimensionnementReel(SimpleTestCase):
#     def test_poteau_cas_1(self):
#         entrees = CAS_DIMENSIONNEMENT_POTEAU_1["entrees"]
#         resultat = dimensionner_poteau(**entrees)
#         self.assertEqual(resultat, CAS_DIMENSIONNEMENT_POTEAU_1["resultat_attendu"])