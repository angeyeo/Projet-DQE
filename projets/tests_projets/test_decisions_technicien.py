"""
Décisions métier validées par le technicien BTP le 07/10/2026 -- un test
(au moins) par réponse, chaque valeur attendue calculée à la main.

  1. Semelles isolées à l'ELU : A² ≥ Nu / σsol.
  2. Poids propre des poutres et poteaux ajouté à G par défaut.
  3. G = 5 kN/m² par défaut (plancher courant).
  4. Métré : mêmes sections à tous les niveaux, poutres entre axes,
     emprise des poutres déduite du béton de la dalle.
  5. Semelles : espacement maximal 20 cm, diamètre minimal HA12.
  6. Q de toiture = 1,5 kN/m².
  7. Agglos 15 pleins au m² (testé dans test_dqe / test_postes_ratio).
  8. Dégression 1 ; 0,9 ; 0,8 ; 0,7 (étage par étage).
"""

from django.test import SimpleTestCase, TestCase

from moteur_calcul.constantes import CHARGE_EXPLOITATION_TOITURE_KN_M2
from moteur_calcul.formules.descente_charges import (
    calculer_descente_charges_complete,
    coefficient_degression,
    cumuler_charges_exploitation_degressives,
)
from moteur_calcul.formules.dimensionnement_semelles import dimensionner_semelle
from moteur_calcul.formules.trame import generer_poteau_sur_grille
from moteur_calcul.hypotheses import G_PLANCHER_FORFAITAIRE_KN_M2, HypothesesCalcul
from projets.models import ElementStructurel, Projet
from projets.services.dqe_calculator import calculer_projet_dqe
from projets.tests_projets.utils import BAREME_TEST


class Decision1SemellesELU(SimpleTestCase):
    def test_exemple_du_technicien(self):
        """Villa R+1, Nu = 252 kN, σsol = 150 kN/m² : √(252/150) = 1,296 m -> 130 × 130 cm."""
        r = dimensionner_semelle(charge_poteau=252, taux_travail_sol=150, cote_poteau_cm=20,
                                 charge_service=182, methode="ELU", inclure_poids_propre=False)
        self.assertAlmostEqual(r["cote_theorique_cm"], 129.6)
        self.assertEqual(r["cote_cm"], 130)
        self.assertEqual(r["methode"], "ELU")

    def test_defaut_d_un_nouveau_projet(self):
        self.assertEqual(Projet._meta.get_field("methode_semelles").default, "ELU")


class Decision2PoidsPropre(SimpleTestCase):
    def test_defaut_d_un_nouveau_projet(self):
        self.assertIs(Projet._meta.get_field("inclure_poids_propre_ossature").default, True)


class Decision3ChargePermanente(SimpleTestCase):
    def test_valeur_et_message(self):
        self.assertEqual(G_PLANCHER_FORFAITAIRE_KN_M2, 5.0)
        h = HypothesesCalcul(g_plancher_kn_m2=5.0, origine_g="forfait", q_kn_m2=1.5, origine_q="usage:habitation",
                             inclure_poids_propre_ossature=True)
        self.assertTrue(any("hourdis 16+4" in m and "G = 5 kN/m²" in m for m in h.messages()))

    def test_alerte_si_poids_propre_desactive_avec_le_forfait(self):
        h = HypothesesCalcul(g_plancher_kn_m2=5.0, origine_g="forfait", q_kn_m2=1.5, origine_q="saisie",
                             inclure_poids_propre_ossature=False)
        self.assertTrue(any(m.startswith("ALERTE : le forfait G") for m in h.messages()))


class Decision5FerraillageSemelles(SimpleTestCase):
    def test_ha12_minimum_et_espacement_20_cm(self):
        # Petite semelle (Nu = 100 kN) : l'acier calculé est faible, les minima constructifs gouvernent.
        for nu in (100, 252, 600):
            r = dimensionner_semelle(charge_poteau=nu, taux_travail_sol=150, cote_poteau_cm=20,
                                     charge_service=nu / 1.4, methode="ELU", inclure_poids_propre=False)
            with self.subTest(nu=nu):
                self.assertGreaterEqual(r["barres_proposees"]["diametre_mm"], 12)
                self.assertLessEqual(r["espacement_barres_cm"], 20)
                self.assertGreaterEqual(r["barres_proposees"]["section_reelle_cm2"], r["section_acier_par_direction_cm2"])


class Decision6ChargeToiture(SimpleTestCase):
    def test_bureaux_r_plus_2(self):
        """Bureaux R+2 (3 niveaux), poteau central, portées 4 × 4 m (S = 16 m²), sans poids propre :
          Q0 toiture = 1,5 × 16 = 24 kN ; Q étage = 2,5 × 16 = 40 kN
          Q = 24 + 1 × 40 + 0,9 × 40 = 100 kN ; G = 3 × 5 × 16 = 240 kN
          Nu = 1,35 × 240 + 1,5 × 100 = 474 kN ; Ns = 340 kN
        """
        hyp = HypothesesCalcul(g_plancher_kn_m2=5.0, origine_g="forfait", q_kn_m2=2.5, origine_q="usage:bureau",
                               q_toiture_kn_m2=CHARGE_EXPLOITATION_TOITURE_KN_M2, origine_q_toiture="valide_technicien",
                               inclure_poids_propre_ossature=False, contrainte_sol_kn_m2=150)
        r = generer_poteau_sur_grille(1, 1, 4.0, 4.0, 2, 2, 2.5, 3.0, nb_niveaux=3, usage_batiment="bureau", hyp=hyp)
        self.assertAlmostEqual(r["charge_q_cumulee_kn"], 100.0)
        self.assertAlmostEqual(r["charge_elu_kn"], 474.0)
        self.assertAlmostEqual(r["charge_els_kn"], 340.0)
        etapes = {e["etape"]: e for e in r["resultat_poteau"]["trace"]}
        self.assertEqual(etapes["Q toiture"]["resultat"], 24.0)
        self.assertEqual(etapes["Q cumulée (dégression)"]["calcul"], "24 + 1 × 40 + 0,9 × 40")

    def test_descente_isolee_toiture_par_defaut(self):
        """Élément recalculé isolément sans usage de toiture : Q0 = 1,5 kN/m² (et non Q d'étage)."""
        d = calculer_descente_charges_complete(4, 4, 4, 4, 0.16, "bureau", nb_niveaux=2, avec_degression=True)
        # S = 16 m² : Q0 = 24 kN, Q1 = 40 kN -> 64 kN
        self.assertAlmostEqual(d["charge_exploitation_toiture_kn"], 24.0)
        self.assertAlmostEqual(d["charge_exploitation_cumulee_kn"], 64.0)


class Decision8Degression(SimpleTestCase):
    def test_coefficients_etage_par_etage(self):
        """Q0 = 10, quatre étages de 20 kN : 10 + 20 + 18 + 16 + 14 = 78 kN."""
        r = cumuler_charges_exploitation_degressives(10, [20] * 4, "habitation")
        self.assertEqual(r["coefficients_par_etage"], [1.0, 0.9, 0.8, 0.7])
        self.assertEqual(r["cumuls_kn"], [10, 30, 48, 64, 78])

    def test_equivalence_avec_la_forme_nf_p06_001(self):
        """Étages identiques : Q0 + Σ k_i Q = Q0 + c(n) n Q, c = 1 ; 0,95 ; 0,90 ; 0,85 ; (3+n)/2n."""
        for n in range(1, 13):
            attendu = 1.0 if n == 1 else ([1.0, 0.95, 0.90, 0.85][n - 1] if n <= 4 else (3 + n) / (2 * n))
            with self.subTest(n=n):
                self.assertAlmostEqual(coefficient_degression(n), attendu, places=6)
                r = cumuler_charges_exploitation_degressives(0, [10.0] * n, "habitation")
                self.assertAlmostEqual(r["cumuls_kn"][-1], round(attendu * n * 10.0, 2), places=2)

    def test_au_dela_du_quatrieme_etage_valide_b9(self):
        """Règle B9 confirmée (21/10/2026) : Q0 = 10, six étages de 20 kN :
        10 + 20 + 18 + 16 + 14 + 12 + 10 = 100 kN (coefficients 1 ; 0,9 ; 0,8 ; 0,7 ; 0,6 ; 0,5)."""
        r = cumuler_charges_exploitation_degressives(10, [20] * 6, "habitation")
        self.assertEqual(r["coefficients_par_etage"], [1.0, 0.9, 0.8, 0.7, 0.6, 0.5])
        self.assertEqual(r["cumuls_kn"][-1], 100)
        self.assertNotIn("au_dela_regle_validee", r)
        hyp = HypothesesCalcul(g_plancher_kn_m2=5.0, origine_g="saisie", q_kn_m2=1.5, origine_q="saisie",
                               contrainte_sol_kn_m2=200)
        noeud = generer_poteau_sur_grille(1, 1, 4.0, 4.0, 2, 2, 1.5, 3.0, nb_niveaux=6,
                                          usage_batiment="habitation", hyp=hyp)
        self.assertFalse(any("non validés" in m for m in noeud["hypotheses"]))

    def test_r_plus_1_sans_degression_b9(self):
        """Règle B9 : la dégression ne commence qu'à partir de 2 étages.
        R+1 = toiture + 1 étage : Q0 = 10, Q1 = 20 -> 10 + 1,0 × 20 = 30 kN, sans réduction."""
        r = cumuler_charges_exploitation_degressives(10, [20], "habitation")
        self.assertEqual(r["coefficients_par_etage"], [1.0])
        self.assertEqual(r["cumuls_kn"], [10, 30])
        self.assertFalse(r["degression_appliquee"])

    def test_pas_de_degression_en_commerce(self):
        r = cumuler_charges_exploitation_degressives(10, [20] * 3, "commerce")
        self.assertEqual(r["cumuls_kn"][-1], 70)


class Decision4MetreDallePoutre(TestCase):
    """Emprise des poutres déduite du béton de la dalle."""

    def setUp(self):
        self.projet = Projet.objects.create(nom="Métré", usage_batiment="habitation", nb_niveaux=1)

    def poutre(self, ident, b, h=40, portee=5.0):
        return ElementStructurel.objects.create(
            projet=self.projet, type_element=ElementStructurel.TypeElement.POUTRE, identifiant=ident, portee=portee,
            resultat_calcul={"largeur_cm": b, "hauteur_cm": h}, resultat_valide={"largeur_cm": b, "hauteur_cm": h},
            statut=ElementStructurel.Statut.VALIDE)

    def dalle(self, lx=4.0, ly=5.0, surface=None, e=15):
        return ElementStructurel.objects.create(
            projet=self.projet, type_element=ElementStructurel.TypeElement.DALLE, identifiant="D1",
            portee=lx, longueur_m=ly, surface_m2=surface if surface is not None else lx * ly,
            resultat_calcul={"epaisseur_cm": e}, resultat_valide={"epaisseur_cm": e},
            statut=ElementStructurel.Statut.VALIDE)

    def lignes_dalle(self):
        d = calculer_projet_dqe(self.projet, BAREME_TEST)
        return {l["categorie"]: l for l in d["lignes"] if l["repere"] == "D1"}, d

    def test_deduction_appliquee(self):
        """Panneau 4 × 5 m entre axes, poutres b = 20 cm, e = 15 cm :
        béton = (4 − 0,2) × (5 − 0,2) × 0,15 = 3,8 × 4,8 × 0,15 = 2,736 m³ (au lieu de 3,000) ;
        acier (ratio 90 kg/m³, B4) = 2,736 × 90 = 246,24 kg ; coffrage de sous-face inchangé = 20 m²."""
        self.poutre("PX1", 20)
        self.dalle()
        l, d = self.lignes_dalle()
        self.assertEqual(l["BETON"]["quantite"], 2.736)
        self.assertEqual(l["BETON"]["formule_quantite"], "(Lx − b) × (Ly − b) × e = (4 − 0,2) × (5 − 0,2) × 0,15")
        self.assertIn("règle de métré validée", l["BETON"]["hypothese"])
        self.assertEqual(l["ACIER"]["quantite"], 246.24)
        self.assertEqual(l["COFFRAGE"]["quantite"], 20.0)
        self.assertIn(l["BETON"]["hypothese"], d["hypotheses"])

    def test_sans_poutre_rien_a_deduire(self):
        self.dalle()
        l, _ = self.lignes_dalle()
        self.assertEqual(l["BETON"]["quantite"], 3.0)
        self.assertNotIn("hypothese", l["BETON"])

    def test_largeurs_differentes_non_deduit_et_signale(self):
        self.poutre("PX1", 20)
        self.poutre("PX2", 25)
        self.dalle()
        l, _ = self.lignes_dalle()
        self.assertEqual(l["BETON"]["quantite"], 3.0)
        self.assertIn("NON déduite", l["BETON"]["hypothese"])

    def test_surface_saisie_incoherente_non_deduit(self):
        self.poutre("PX1", 20)
        self.dalle(surface=25.0)
        l, _ = self.lignes_dalle()
        self.assertEqual(l["BETON"]["quantite"], 3.75)
        self.assertIn("NON déduite", l["BETON"]["hypothese"])

    def test_poutre_comptee_sur_toute_sa_hauteur(self):
        """La poutre garde b × h × L entre axes : 0,2 × 0,4 × 5 = 0,4 m³."""
        self.poutre("PX1", 20)
        self.dalle()
        d = calculer_projet_dqe(self.projet, BAREME_TEST)
        beton_poutre = next(l for l in d["lignes"] if l["repere"] == "PX1" and l["categorie"] == "BETON")
        self.assertEqual(beton_poutre["quantite"], 0.4)


class ReponsesIngenieur(SimpleTestCase):
    """Réponses de l'ingénieur BTP du 10/10/2026."""

    def test_sol_au_dela_de_3_bars_signale(self):
        from moteur_calcul.plausibilite import controler_parametres
        self.assertEqual(controler_parametres(contrainte_sol=300), [])
        alertes = controler_parametres(contrainte_sol=350)
        self.assertEqual([a["code"] for a in alertes], ["SOL_INHABITUEL"])
        self.assertIn("étude géotechnique", alertes[0]["message"])

    def test_tva_de_reference_proposee_jamais_appliquee(self):
        from projets.services.dqe_calculator import TAUX_TVA_REFERENCE_PCT
        self.assertEqual(TAUX_TVA_REFERENCE_PCT, 18)


class ToitureCharpente(SimpleTestCase):
    """Toiture en charpente : G = 2,5 kN/m² (ingénieur BTP, 10/10/2026), pas de plancher au dernier niveau."""

    def hyp(self, **kw):
        d = dict(g_plancher_kn_m2=5.0, origine_g="forfait", q_kn_m2=1.5, origine_q="usage:habitation",
                 q_toiture_kn_m2=1.5, origine_q_toiture="valide_technicien", inclure_poids_propre_ossature=True,
                 contrainte_sol_kn_m2=150, type_toiture="charpente", g_toiture_kn_m2=2.5)
        d.update(kw)
        return HypothesesCalcul(**d)

    def test_r_plus_1_calcul_manuel(self):
        """Poteau central R+1, portées 4,0 × 3,5 m (S = 14 m²), poids propre inclus :
          plancher haut RDC : 14 × 5 = 70 kN ; toiture : 14 × 2,5 = 35 kN
          poutres : 2 × (4/2 × 0,2 × 0,5 × 25) + 2 × (3,5/2 × 0,2 × 0,4375 × 25) = 17,65625 kN par niveau
          poteau 20 × 20 × 3 m : 3 kN par niveau
          G = 70 + 35 + 2 × (17,65625 + 3) = 146,3125 kN ; Q = 21 + 21 = 42 kN
          Nu = 1,35 × 146,3125 + 1,5 × 42 = 260,521875 kN ; Ns = 188,3125 kN
        (avec une toiture en dalle : Nu = 307,771875 kN)"""
        r = generer_poteau_sur_grille(1, 1, 4.0, 3.5, 2, 2, 1.5, 3.0, nb_niveaux=2, usage_batiment="habitation",
                                      hyp=self.hyp())
        self.assertAlmostEqual(r["charge_elu_kn"], 260.521875, places=4)
        self.assertAlmostEqual(r["charge_els_kn"], 188.3125, places=4)
        etapes = [e["etape"] for e in r["resultat_poteau"]["trace"]]
        self.assertIn("G toiture (charpente + couverture)", etapes)
        self.assertTrue(any("charpente" in m for m in r["hypotheses"]))
        dalle = generer_poteau_sur_grille(1, 1, 4.0, 3.5, 2, 2, 1.5, 3.0, nb_niveaux=2, usage_batiment="habitation",
                                          hyp=self.hyp(type_toiture="dalle", g_toiture_kn_m2=None))
        self.assertAlmostEqual(dalle["charge_elu_kn"], 307.771875, places=4)

    def test_poutres_d_un_plain_pied_portent_la_charpente(self):
        from moteur_calcul.formules.trame import generer_poutre_sur_grille
        r1 = generer_poutre_sur_grille(4.0, 3.5, 1.5, hyp=self.hyp(inclure_poids_propre_ossature=False), nb_niveaux=1)
        r2 = generer_poutre_sur_grille(4.0, 3.5, 1.5, hyp=self.hyp(inclure_poids_propre_ossature=False), nb_niveaux=2)
        # g_lin = 2,5 × 3,5 = 8,75 kN/m (plain-pied) ; 5 × 3,5 = 17,5 kN/m (un plancher en dessous)
        self.assertAlmostEqual(r1["resultat_poutre"]["charge_els_kn_m"], 8.75 + 1.5 * 3.5)
        self.assertAlmostEqual(r2["resultat_poutre"]["charge_els_kn_m"], 17.5 + 1.5 * 3.5)

    def test_charpente_sans_charge_refusee(self):
        with self.assertRaises(ValueError):
            self.hyp(g_toiture_kn_m2=None)
        with self.assertRaises(ValueError):
            self.hyp(type_toiture="tuile")


class ToitureCharpenteAPI(TestCase):
    def test_projet_et_variante(self):
        from projets.services.parametres_projet import parametres_structure
        from projets.services.variantes import _nettoyer, VarianteInvalide
        p = Projet.objects.create(nom="R+1 charpente", usage_batiment="habitation", nb_niveaux=2, hauteur_etage=3.0,
                                  nb_travees_x=2, nb_travees_y=2, portee_x=4.0, portee_y=3.5, contrainte_sol_kn_m2=150,
                                  type_toiture="charpente")
        hyp = parametres_structure(p, avec_grille=True)["hyp"]
        self.assertEqual((hyp.type_toiture, hyp.g_toiture_kn_m2), ("charpente", 1.5))  # B14, 21/10/2026
        self.assertEqual(Projet._meta.get_field("type_toiture").default, "dalle")
        self.assertEqual(_nettoyer({"type_toiture": "dalle"}), {"type_toiture": "dalle"})
        with self.assertRaises(VarianteInvalide):
            _nettoyer({"type_toiture": "tuile"})
