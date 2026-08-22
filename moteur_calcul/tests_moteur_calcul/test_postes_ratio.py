from django.test import SimpleTestCase

from moteur_calcul.formules.postes_ratio import calculer_poste_ratio


class TestCalculerPosteRatio(SimpleTestCase):
    def test_type_poste_inconnu_leve_une_erreur(self):
        with self.assertRaises(ValueError):
            calculer_poste_ratio("charpente", {"perimetre_batiment_m": 50})

    def test_maconnerie_sans_infos_hauteur_retourne_liste_vide(self):
        """Pas d'erreur si on ne connaît que le périmètre -- juste aucune ligne."""
        lignes = calculer_poste_ratio("maconnerie", {"perimetre_batiment_m": 50})
        self.assertEqual(lignes, [])

    def test_maconnerie_infra_et_elevation(self):
        lignes = calculer_poste_ratio("maconnerie", {
            "perimetre_batiment_m": 50,
            "hauteur_soubassement_m": 0.6,
            "hauteur_etage_m": 3.0,
            "nb_niveaux": 1,
        })
        designations = [l["designation"] for l in lignes]
        self.assertIn("Agglos 15 pleins (infrastructure)", designations)
        self.assertIn("Agglos 15 creux (élévation)", designations)
        infra = next(l for l in lignes if "infrastructure" in l["designation"])
        # 50 * 0.6 * 0.15 = 4.5 m³
        self.assertAlmostEqual(infra["quantite"], 4.5)

    def test_chainage_bas_et_haut(self):
        lignes = calculer_poste_ratio("chainage", {"longueur_chainage_m": 32.0})
        self.assertEqual(len(lignes), 6)  # 3 lignes (béton/acier/coffrage) x 2 (bas + haut)
        beton_bas = next(l for l in lignes if "Béton" in l["designation"] and "bas" in l["designation"])
        # 32 * 0.03 = 0.96 m³
        self.assertAlmostEqual(beton_bas["quantite"], 0.96)

    def test_raidisseur_proportionnel_au_nombre_de_poteaux(self):
        lignes = calculer_poste_ratio("raidisseur", {"nb_poteaux": 6, "hauteur_etage_m": 3.0})
        beton = next(l for l in lignes if "Béton" in l["designation"])
        # 6 * 3.0 * 0.03 = 0.54 m³
        self.assertAlmostEqual(beton["quantite"], 0.54)

    def test_acrotere_utilise_perimetre_batiment_par_defaut(self):
        lignes = calculer_poste_ratio("acrotere", {"perimetre_batiment_m": 50})
        beton = next(l for l in lignes if "Béton" in l["designation"])
        # 50 * 0.05 = 2.5 m³
        self.assertAlmostEqual(beton["quantite"], 2.5)

    def test_enduit_murs_et_sous_plafond(self):
        lignes = calculer_poste_ratio("enduit", {
            "surface_murs_a_enduire_m2": 1400,
            "surface_dalle_m2": 52.5,
        })
        self.assertEqual(len(lignes), 2)

    def test_champ_requis_manquant_leve_key_error(self):
        """Mieux vaut un échec explicite qu'une quantité à zéro silencieuse."""
        with self.assertRaises(KeyError):
            calculer_poste_ratio("chainage", {})
