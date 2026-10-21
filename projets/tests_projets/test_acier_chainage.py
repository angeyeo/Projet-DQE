"""Acier des chaînages identifiés : ratio, jamais présenté comme un calcul
(audit A-02, issue #63).

Cas de référence (calcul à la main) : chaînage CH1 de 10 m, 15 × 20 cm.
  béton  = 0,15 × 0,20 × 10 = 0,30 m³
  acier  = 0,30 × 80 kg/m³ (règle B4) = 24 kg
"""
from django.test import TestCase

from moteur_calcul.formules.postes_ratio import dimensionner_chainage
from projets.models import ElementStructurel, Projet
from projets.services.calculations import calculer_element
from projets.services.dqe_calculator import calculer_element_dqe
from projets.tests_projets.utils import BAREME_TEST


class AcierChainageEstime(TestCase):
    def setUp(self):
        self.projet = Projet.objects.create(nom="Chaînage", usage_batiment="habitation", nb_niveaux=1)

    def chainage(self, resultat):
        return ElementStructurel.objects.create(
            projet=self.projet, type_element=ElementStructurel.TypeElement.CHAINAGE, identifiant="CH1",
            longueur_m=10.0, resultat_calcul=resultat, resultat_valide=resultat,
            statut=ElementStructurel.Statut.VALIDE,
        )

    def acier(self, element):
        return next(l for l in calculer_element_dqe(element, BAREME_TEST) if l["categorie"] == "ACIER")

    def test_moteur_ratio_par_defaut_80(self):
        r = dimensionner_chainage(longueur_m=10)
        self.assertEqual(r["volume_beton_m3"], 0.3)
        self.assertEqual(r["poids_acier_total_kg"], 24.0)
        self.assertTrue(r["hypothese_ratio_acier"])

    def test_ligne_dqe_estimee_et_non_calculee(self):
        el = self.chainage({"largeur_cm": 15, "hauteur_cm": 20})
        el.resultat_calcul = el.resultat_valide = calculer_element(el)
        el.save()
        acier = self.acier(el)
        self.assertEqual(acier["source_quantite"], "ratio_reference")
        self.assertEqual(acier["quantite"], 24.0)
        self.assertIn("80 kg par m³", acier["hypothese"])
        self.assertIn("règle B4", acier["hypothese"])

    def test_ancien_resultat_a_90_kg_m3_recalcule_au_ratio_retenu(self):
        """Un chaînage validé avant la règle B4 porte encore un poids de
        0,30 × 90 = 27 kg dans son résultat figé : le DQE ne le reprend pas
        comme un calcul et applique le ratio retenu (24 kg)."""
        el = self.chainage({"largeur_cm": 15, "hauteur_cm": 20, "volume_beton_m3": 0.3,
                            "poids_acier_total_kg": 27.0, "hypothese_ratio_acier": True})
        acier = self.acier(el)
        self.assertEqual(acier["source_quantite"], "ratio_reference")
        self.assertEqual(acier["quantite"], 24.0)
