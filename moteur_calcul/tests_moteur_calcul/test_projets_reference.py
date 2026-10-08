"""
Projets de référence -- valeurs calculées À LA MAIN (détail en commentaire),
indépendamment du moteur, puis comparées au moteur.

Tolérances :
  - efforts (kN, kN·m) : 0,5 % relatif. Les calculs manuels sont exacts ;
    l'écart toléré couvre uniquement les arrondis d'affichage (0,01).
  - dimensions retenues (cm) : égalité stricte. Ce sont des valeurs
    discrètes (arrondi constructif au multiple de 5 cm) : un écart d'un
    cran serait une vraie différence de résultat.
  - sections d'acier (cm²) : 1 % relatif (racines carrées).

Conventions : fc28 = 25 MPa, fe = 500 MPa, γb = 1,5, γs = 1,15,
fbu = 0,85 × 25 / 1,5 = 14,1667 MPa, fsu = 500 / 1,15 = 434,78 MPa,
G forfaitaire 5 kN/m² sauf mention, poids propre non ajouté sauf mention.
"""

from django.test import SimpleTestCase

from moteur_calcul.formules.dimensionnement_dalles import predimensionner_dalle
from moteur_calcul.formules.trame import generer_poteau_sur_grille, generer_poutre_sur_grille
from moteur_calcul.hypotheses import HypothesesCalcul, resoudre_charge_permanente


def hyp(q, sol=None, methode="ELU", g=5.0, origine_g="forfait", pp=False):
    return HypothesesCalcul(g_plancher_kn_m2=g, origine_g=origine_g, q_kn_m2=q, origine_q="saisie",
                            contrainte_sol_kn_m2=sol, methode_semelles=methode, inclure_poids_propre_ossature=pp)


def noeud_central(px, py, q, n, usage, sol=None, methode="ELU", g=5.0, pp=False, h=3.0):
    """Poteau central (1,1) d'une trame 2 x 2 : S = px × py."""
    return generer_poteau_sur_grille(1, 1, px, py, 2, 2, q, h, nb_niveaux=n, usage_batiment=usage,
                                     taux_travail_sol=sol, hyp=hyp(q, sol, methode, g, pp=pp))


class ProjetsReference(SimpleTestCase):
    def assertProche(self, valeur, attendu, rel=0.005):
        self.assertLessEqual(abs(valeur - attendu), abs(attendu) * rel,
                             f"{valeur} ≠ {attendu} (tolérance {rel:.1%})")

    # 1. Villa plain-pied -- trame 4 × 3,5 m, habitation, σsol = 150 kN/m²
    #    S = 4 × 3,5 = 14 m² ; G = 14 × 5 = 70 kN ; Q = 14 × 1,5 = 21 kN
    #    Nu = 1,35 × 70 + 1,5 × 21 = 126 kN ; Ns = 91 kN
    #    Poteau : B = 1,3 × 126 / (0,7 × 2,5) = 93,6 cm² -> a = 9,7 -> min 20 cm
    #    Semelle ELU : √(126/150) = 0,9165 m -> 95 cm ; d ≥ (95 − 20)/4 = 18,75 ; h = arr5(23,75) = 25 cm
    def test_01_villa_plain_pied(self):
        r = noeud_central(4.0, 3.5, 1.5, 1, "habitation", sol=150)
        self.assertProche(r["charge_elu_kn"], 126.0)
        self.assertProche(r["charge_els_kn"], 91.0)
        self.assertEqual(r["resultat_poteau"]["cote_cm"], 20)
        self.assertEqual(r["resultat_semelle"]["cote_cm"], 95)
        self.assertEqual(r["resultat_semelle"]["hauteur_cm"], 25)

    # 2. Villa R+1 (2 niveaux) : dégression c(1) = 1,0 -> Q = 2 × 21 = 42 ; G = 140
    #    Nu = 189 + 63 = 252 kN ; Ns = 182 kN
    def test_02_villa_r_plus_1(self):
        r = noeud_central(4.0, 3.5, 1.5, 2, "habitation", sol=150)
        self.assertProche(r["charge_elu_kn"], 252.0)
        self.assertProche(r["charge_els_kn"], 182.0)

    # 3. R+2 (3 niveaux) : Q = 21 + 0,95 × (21 + 21) = 60,9 ; G = 210
    #    Nu = 283,5 + 91,35 = 374,85 kN
    def test_03_r_plus_2_degression(self):
        r = noeud_central(4.0, 3.5, 1.5, 3, "habitation", sol=150)
        self.assertProche(r["charge_q_cumulee_kn"], 60.9)
        self.assertProche(r["charge_elu_kn"], 374.85)

    # 4. Petit immeuble R+4 (5 niveaux), bureaux, trame 5 × 5 m
    #    S = 25 ; Q/niveau = 62,5 ; c(4) = 0,85 -> Q = 62,5 + 0,85 × 4 × 62,5 = 275
    #    G = 5 × 125 = 625 ; Nu = 843,75 + 412,5 = 1256,25 kN
    #    Poteau : B = 1,3 × 1256,25 / 1,75 = 933,2 cm² -> 30,5 -> 35 cm (le flambement peut l'élargir)
    def test_04_petit_immeuble_bureaux(self):
        r = noeud_central(5.0, 5.0, 2.5, 5, "bureau", sol=200)
        self.assertProche(r["charge_q_cumulee_kn"], 275.0)
        self.assertProche(r["charge_elu_kn"], 1256.25)
        self.assertGreaterEqual(r["resultat_poteau"]["cote_cm"], 35)
        self.assertTrue(r["resultat_poteau"]["verification_beton_seul_suffisante"]
                        or r["resultat_poteau"]["section_acier_retenue_cm2"] > 0)

    # 5. Bâtiment commercial (q = 5 kN/m², PAS de dégression), 2 niveaux, 5 × 5 m
    #    Q = 2 × 125 = 250 ; G = 250 ; Nu = 337,5 + 375 = 712,5 kN
    def test_05_commercial_sans_degression(self):
        r = noeud_central(5.0, 5.0, 5.0, 2, "commerce", sol=200)
        self.assertFalse(r["degression_appliquee"])
        self.assertProche(r["charge_elu_kn"], 712.5)

    # 6. Grande portée : poutre intérieure L = 8 m, largeur reprise 6 m, habitation
    #    g = 30 kN/m, q = 9 kN/m ; pu = 54 ; pser = 39 ; γ = 1,3846
    #    Mu = 54 × 64 / 8 = 432 kN·m ; h = 8/8 = 1,00 m ; d = 0,90 m ; b = 0,20 m
    #    µ = 0,432 / (0,20 × 0,81 × 14,1667) = 0,1882 (pivot B, < µlu = 0,2633)
    #    α = 1,25 (1 − √(1 − 2µ)) = 0,2630 ; z = 0,90 (1 − 0,4α) = 0,8053 m
    #    As = 0,432 / (0,8053 × 434,78) = 12,34 cm²
    def test_06_grande_portee(self):
        r = generer_poutre_sur_grille(8.0, 6.0, 1.5, hyp=hyp(1.5))
        p = r["resultat_poutre"]
        self.assertProche(r["charge_lineaire_kn_m"], 54.0)
        self.assertProche(r["charge_lineaire_service_kn_m"], 39.0)
        self.assertProche(p["moment_flechissant_knm"], 432.0)
        self.assertEqual(p["hauteur_cm"], 100.0)
        self.assertEqual(p["pivot"], "B")
        self.assertProche(p["section_acier_theorique_cm2"], 12.34, rel=0.01)
        self.assertFalse(p["gamma_estime"])

    # 7. Sol faible σ = 75 kN/m² (cas 2 : Nu = 252, Ns = 182)
    #    ELU : √(252/75) = 1,833 m -> 185 cm ; ELS : √(182/75) = 1,558 m -> 160 cm
    def test_07_sol_faible_elu_et_els(self):
        elu = noeud_central(4.0, 3.5, 1.5, 2, "habitation", sol=75, methode="ELU")
        els = noeud_central(4.0, 3.5, 1.5, 2, "habitation", sol=75, methode="ELS")
        self.assertEqual(elu["resultat_semelle"]["cote_cm"], 185)
        self.assertEqual(els["resultat_semelle"]["cote_cm"], 160)
        self.assertEqual(els["resultat_semelle"]["methode"], "ELS")

    # 8. Sol normal σ = 200 : √(252/200) = 1,1225 -> 115 cm ; d ≥ (115 − 20)/4 = 23,75 -> h = 30 cm
    def test_08_sol_normal(self):
        r = noeud_central(4.0, 3.5, 1.5, 2, "habitation", sol=200)
        self.assertEqual(r["resultat_semelle"]["cote_cm"], 115)
        self.assertEqual(r["resultat_semelle"]["hauteur_cm"], 30)

    # 9. Sol très résistant σ = 600 : √(252/600) = 0,648 -> 65 cm ; d = max((65−20)/4 ; 15) = 15 -> h = 20 cm
    def test_09_sol_tres_resistant(self):
        r = noeud_central(4.0, 3.5, 1.5, 2, "habitation", sol=600)
        self.assertEqual(r["resultat_semelle"]["cote_cm"], 65)
        self.assertEqual(r["resultat_semelle"]["hauteur_cm"], 20)

    # 10. Charges importantes : plancher composé + poids propre de l'ossature
    #     Couches : dalle 0,16 × 25 = 4,0 ; chape 0,05 × 20 = 1,0 ; carrelage 0,5 ;
    #     enduit 0,3 ; cloisons 1,0 -> g = 6,8 kN/m²
    #     Trame 5 × 5, 3 niveaux habitation : S = 25 ; G planchers = 170 kN/niveau
    #     Poutres : 4 demi-poutres de 5 m : 4 × 2,5 × 0,20 × 0,625 × 25 = 31,25 kN/niveau
    #     Q = 37,5 + 0,95 × 75 = 108,75 kN
    #     Poteau 30 cm (itération convergée) : 0,3² × 3 × 25 = 6,75 kN/niveau
    #     G = 3 × (170 + 31,25 + 6,75) = 624 kN ; Nu = 842,4 + 163,125 = 1005,525 kN
    def test_10_charges_importantes_couches_et_poids_propre(self):
        couches = [
            {"designation": "dalle", "epaisseur_m": 0.16, "poids_volumique_kn_m3": 25},
            {"designation": "chape", "epaisseur_m": 0.05, "poids_volumique_kn_m3": 20},
            {"type": "carrelage_colle"}, {"type": "enduit_sous_face"}, {"type": "cloisons_legeres"},
        ]
        g, origine, _ = resoudre_charge_permanente(None, couches)
        self.assertEqual(origine, "couches")
        self.assertProche(g, 6.8)
        r = generer_poteau_sur_grille(1, 1, 5.0, 5.0, 2, 2, 1.5, 3.0, nb_niveaux=3, usage_batiment="habitation",
                                      hyp=hyp(1.5, 200, g=g, pp=True))
        self.assertEqual(r["resultat_poteau"]["cote_cm"], 30)
        self.assertProche(r["charge_g_cumulee_kn"], 624.0)
        self.assertProche(r["charge_elu_kn"], 1005.525)

    # 11. Dalles : Lx = 4, Ly = 5 -> α = 0,8 ≥ 0,4 : deux sens, h = 4/35 = 11,4 -> minimum 12 cm
    #     Lx = 6, Ly = 20 -> α = 0,3 : un sens, h = 6/25 = 24 cm
    def test_11_dalles(self):
        self.assertEqual(predimensionner_dalle(4.0, portant_deux_sens=True)["epaisseur_cm"], 12)
        self.assertEqual(predimensionner_dalle(6.0, portant_deux_sens=False)["epaisseur_cm"], 24)

    # 12. Traçabilité : chaque étape de la descente est présente et cohérente
    def test_12_trace_complete(self):
        r = noeud_central(4.0, 3.5, 1.5, 2, "habitation", sol=150)
        etapes = [e["etape"] for e in r["resultat_poteau"]["trace"]]
        # R+1 : un seul étage sous la toiture -> pas de dégression (Q = Q0 + Q1).
        for attendu in ("Surface d'influence", "G planchers / niveau", "Q / étage", "Q toiture", "G cumulée",
                        "Q cumulée", "Effort ELU", "Effort ELS", "Section du poteau"):
            self.assertIn(attendu, etapes)
        elu = next(e for e in r["resultat_poteau"]["trace"] if e["etape"] == "Effort ELU")
        self.assertProche(elu["resultat"], 252.0)
        self.assertEqual(r["resultat_semelle"]["hypotheses_calcul"]["origine_g"], "forfait")
        self.assertTrue(any("HYPOTHÈSE" in m and "G = 5 kN/m²" in m for m in r["hypotheses"]))


class Plausibilite(SimpleTestCase):
    def test_valeurs_courantes_sans_alerte(self):
        from moteur_calcul.plausibilite import controler_parametres
        self.assertEqual(controler_parametres(portee_x=4, portee_y=5, hauteur_etage=3, g=5, q=1.5,
                                              contrainte_sol=150, nb_niveaux=2), [])

    def test_valeur_inhabituelle_signalee_jamais_modifiee(self):
        from moteur_calcul.plausibilite import controler_parametres, controler_resultats
        a = controler_parametres(portee_x=9.5, contrainte_sol=40, nb_niveaux=8)
        codes = {x["code"] for x in a}
        self.assertEqual(codes, {"PORTEE_X_INHABITUELLE", "SOL_INHABITUEL", "NIVEAUX_INHABITUELS"})
        self.assertTrue(all(x["message"].startswith("ALERTE — valeur inhabituelle") for x in a))
        self.assertEqual(next(x for x in a if x["code"] == "PORTEE_X_INHABITUELLE")["valeur"], 9.5)
        r = controler_resultats([("S1", "semelle", {"cote_cm": 320})], portee_min=3.0)
        self.assertEqual({x["code"] for x in r}, {"SEMELLE_INHABITUELLE", "SEMELLES_JOINTIVES"})
