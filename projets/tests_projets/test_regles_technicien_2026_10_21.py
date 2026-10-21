"""Réponses du technicien BTP aux règles B1 à B15 (issue #64, 21/10/2026).

Cas de référence vérifiés à la main pour les valeurs corrigées :
B4 (ratios d'acier) et B14 (G de la charpente).
"""
from decimal import Decimal

from django.test import SimpleTestCase

from moteur_calcul import constantes as C
from moteur_calcul.formules.postes_ratio import calculer_poste_ratio
from projets.services.dqe_calculator import RATIOS_ACIER_KG_M3


def _acier(lignes, prefixe):
    return next(l for l in lignes if l["designation"].startswith("Acier") and l["designation"].endswith(prefixe))


class RegleB4RatiosAcier(SimpleTestCase):
    def test_ratios_retenus(self):
        self.assertEqual(RATIOS_ACIER_KG_M3["poteau"], Decimal("100.0"))
        self.assertEqual(RATIOS_ACIER_KG_M3["poutre"], Decimal("130.0"))
        self.assertEqual(RATIOS_ACIER_KG_M3["longrine"], Decimal("130.0"))
        self.assertEqual(RATIOS_ACIER_KG_M3["dalle"], Decimal("90.0"))
        self.assertEqual(RATIOS_ACIER_KG_M3["chainage"], Decimal("80.0"))

    def test_ratios_dans_les_fourchettes_de_plausibilite(self):
        for valeur, (mini, maxi) in (
            (C.RATIO_ACIER_POTEAUX_RETENU_KG_M3, C.RATIO_ACIER_POTEAUX_KG_M3),
            (C.RATIO_ACIER_POUTRES_RETENU_KG_M3, C.RATIO_ACIER_POUTRES_KG_M3),
            (C.RATIO_ACIER_DALLES_RETENU_KG_M3, C.RATIO_ACIER_DALLES_KG_M3),
        ):
            self.assertTrue(mini <= valeur <= maxi, (valeur, mini, maxi))

    def test_chainage_80_kg_m3(self):
        """10 m de chaînage 15 × 20 cm : béton = 0,03 × 10 = 0,30 m³ ;
        acier = 0,30 × 80 = 24 kg, pour le chaînage bas comme pour le haut."""
        lignes = calculer_poste_ratio("chainage", {"longueur_chainage_m": 10, "longueur_chainage_haut_m": 10})
        self.assertEqual(_acier(lignes, "chaînage bas")["quantite"], 24.0)
        self.assertEqual(_acier(lignes, "chaînage haut / linteaux")["quantite"], 24.0)

    def test_acrotere_non_concerne_reste_90(self):
        """L'acrotère n'est pas un chaînage : 10 m × 0,05 m² = 0,5 m³ ; 0,5 × 90 = 45 kg."""
        lignes = calculer_poste_ratio("acrotere", {"perimetre_acrotere_m": 10, "perimetre_batiment_m": 10})
        self.assertEqual(_acier(lignes, "acrotère")["quantite"], 45.0)


class RegleB14Charpente(SimpleTestCase):
    def test_g_charpente_1_5(self):
        self.assertEqual(C.G_TOITURE_CHARPENTE_KN_M2, 1.5)
