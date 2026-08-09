"""
Tests du dimensionnement des poteaux, poutres et semelles.

Important : ces tests vérifient les champs un par un (pas l'égalité du
dict entier) -- le moteur de calcul gagne régulièrement de nouveaux
champs (barres proposées, non-fragilité, etc.), et une égalité stricte
casserait à chaque ajout même quand tout le reste reste correct.
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
            dimensionner_poutre(portee=50, charge_lineaire=15)

    def test_charge_semelle_negative_rejetee(self):
        with self.assertRaises(EntreeInvalide):
            dimensionner_semelle(charge_poteau=-50, taux_travail_sol=180)


class TestDimensionnementReel(SimpleTestCase):
    def test_poteau_cas_1(self):
        entrees = CAS_DIMENSIONNEMENT_POTEAU_1["entrees"]
        attendu = CAS_DIMENSIONNEMENT_POTEAU_1["resultat_attendu"]
        resultat = dimensionner_poteau(**entrees)
        for cle, valeur_attendue in attendu.items():
            if isinstance(valeur_attendue, float):
                self.assertAlmostEqual(resultat[cle], valeur_attendue, places=1, msg=f"champ '{cle}'")
            else:
                self.assertEqual(resultat[cle], valeur_attendue, msg=f"champ '{cle}'")

    def test_poteau_flambement_augmente_section_si_insuffisante(self):
        """
        Cas Villa R+1 (450 kN, hauteur 3m) : la section théorique seule
        (20x20) ne passe pas la vérification de flambement -- le moteur
        doit automatiquement remonter à 25x25.
        """
        resultat = dimensionner_poteau(charge_calculee=450, hauteur_poteau=3.0)
        self.assertEqual(resultat["cote_cm"], 25)
        self.assertTrue(resultat["verification_beton_seul_suffisante"])

    def test_poteau_barres_proposees_coherentes(self):
        """Le poteau doit toujours proposer au moins 4 barres (une par coin)."""
        resultat = dimensionner_poteau(charge_calculee=250, hauteur_poteau=3.0)
        self.assertIsNotNone(resultat["barres_proposees"])
        self.assertGreaterEqual(resultat["barres_proposees"]["nombre_barres"], 4)

    def test_poutre_cas_1(self):
        entrees = CAS_DIMENSIONNEMENT_POUTRE_1["entrees"]
        attendu = CAS_DIMENSIONNEMENT_POUTRE_1["resultat_attendu"]
        resultat = dimensionner_poutre(**entrees)
        for cle, valeur_attendue in attendu.items():
            if isinstance(valeur_attendue, float):
                self.assertAlmostEqual(resultat[cle], valeur_attendue, places=1, msg=f"champ '{cle}'")
            else:
                self.assertEqual(resultat[cle], valeur_attendue, msg=f"champ '{cle}'")

    def test_poutre_pivot_b_reste_exploitable(self):
        """Cas Pivot B (60-80 kN/m environ) : doit rester exploitable, pas d'erreur."""
        resultat = dimensionner_poutre(portee=6.0, charge_lineaire=70, largeur=0.20)
        self.assertEqual(resultat["pivot"], "B")

    def test_poutre_pivot_b_trop_charge_leve_erreur(self):
        """Au-delà du moment critique, même en Pivot B, ça doit rester bloquant."""
        with self.assertRaises(NotImplementedError):
            dimensionner_poutre(portee=6.0, charge_lineaire=200, largeur=0.20)

    def test_semelle_cas_1(self):
        entrees = CAS_DIMENSIONNEMENT_SEMELLE_1["entrees"]
        attendu = CAS_DIMENSIONNEMENT_SEMELLE_1["resultat_attendu"]
        resultat = dimensionner_semelle(**entrees)
        for cle, valeur_attendue in attendu.items():
            self.assertAlmostEqual(resultat[cle], valeur_attendue, places=1, msg=f"champ '{cle}'")