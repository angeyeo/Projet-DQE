"""
Tests de la descente de charges.

Tant que les formules ne sont pas injectées, ces tests vérifient surtout
que les fonctions lèvent bien NotImplementedError -- ça confirme que le
squelette est branché correctement. Une fois les formules ajoutées
(mercredi), remplacer les assertions par les vraies valeurs attendues.
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
    """Ces tests-là sont valables dès maintenant, indépendamment des formules."""

    def test_surface_negative_rejetee(self):
        with self.assertRaises(EntreeInvalide):
            calculer_charge_exploitation(surface=-10, usage_batiment="habitation")

    def test_usage_inconnu_rejete(self):
        with self.assertRaises(EntreeInvalide):
            calculer_charge_exploitation(surface=30, usage_batiment="usage_invente")


class TestFormulesEnAttente(SimpleTestCase):
    """
    Ces tests documentent que le calcul réel n'est pas encore branché.
    À remplacer mercredi par de vraies assertions sur les résultats
    (voir donnees_test.py).
    """

    def test_charge_permanente_calcul(self):
        val = calculer_charge_permanente(surface=30, epaisseur_dalle=0.2)
        self.assertAlmostEqual(val, 150.0)

    def test_charge_totale_calcul(self):
        val = calculer_charge_totale_niveau([100.0, 50.0])
        self.assertAlmostEqual(val, 150.0)


# --- À activer mercredi, une fois les constantes + formules renseignées ---
#
# class TestDescenteChargesReelle(SimpleTestCase):
#     def test_cas_1(self):
#         entrees = CAS_DESCENTE_CHARGES_1["entrees"]
#         resultat = calculer_charge_exploitation(
#             surface=entrees["surface"], usage_batiment=entrees["usage_batiment"]
#         )
#         self.assertAlmostEqual(resultat, CAS_DESCENTE_CHARGES_1["resultat_attendu"])