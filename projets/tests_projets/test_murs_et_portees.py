"""
Murs en maçonnerie placés là où ils existent, et poutres courtes.

Réponses de l'ingénieur BTP (12/10/2026) :
  1. agglo de 15 creux 2,5 kN/m² + enduit 2 cm × 2 faces (0,4 kN/m² par face) = 3,3 kN/m² ;
  2. murs du RDC posés sur les longrines (charge reportée aux semelles) ;
  3. un mur n'est compté que là où il existe (plan des murs, baies déduites) ;
  4. poutre courte : section minimale 20 × 25 cm, vérification à l'effort tranchant.

Cas de référence calculés à la main -- trame 2 × 2 travées de 4 m, R+1
(2 niveaux), hauteur d'étage 3 m, G = 5 kN/m², Q = 1,5 kN/m², toiture en
dalle, sans poids propre de l'ossature (pour isoler l'effet des murs),
p_mur = 3,3 kN/m² :

  poutre de 4 m : h = max(4/8 ; 0,25) = 0,50 m -> h_mur = 2,50 m
  q_mur = 3,3 × 2,50 = 8,25 kN/m

  poteau central (4, 4), murs d'étage sur les 2 tronçons de la file y = 4 :
    G murs d'étage = 2 × (4/2) × 8,25 = 33 kN
    G = 2 × 16 × 5 + (2 − 1) × 33 = 193 kN ; Q = 48 kN
    Nu = 1,35 × 193 + 1,5 × 48 = 332,55 kN ; Ns = 241 kN
"""

from django.test import SimpleTestCase
from rest_framework.test import APITestCase

from moteur_calcul.constantes import POIDS_MUR_REFERENCE_KN_M2
from moteur_calcul.formules.dimensionnement_poutres import dimensionner_poutre
from moteur_calcul.formules.trame import (
    charge_mur_kn_m,
    cle_segment,
    detecter_poutres_adjacentes,
    generer_poteau_depuis_position_reelle,
    generer_poteau_sur_grille,
    generer_poutre_sur_grille,
)
from moteur_calcul.hypotheses import HypothesesCalcul
from projets.models import Projet
from projets.tests_projets.utils import authentifier

FILE_Y4 = frozenset({cle_segment((0, 4), (4, 4)), cle_segment((4, 4), (8, 4))})
AUTOUR_P11 = FILE_Y4 | {cle_segment((4, 0), (4, 4)), cle_segment((4, 4), (4, 8))}


def hyp(**kw):
    base = dict(g_plancher_kn_m2=5.0, origine_g="saisie", q_kn_m2=1.5, origine_q="saisie",
                q_toiture_kn_m2=1.5, inclure_poids_propre_ossature=False, poids_murs_kn_m2=3.3,
                origine_poids_murs="saisie")
    base.update(kw)
    return HypothesesCalcul(**base)


def noeud(h, i=1, j=1, nb_niveaux=2):
    return generer_poteau_sur_grille(i, j, 4.0, 4.0, 2, 2, 1.5, 3.0, nb_niveaux=nb_niveaux,
                                     usage_batiment="habitation", hyp=h)


class ReponsesIngenieur(SimpleTestCase):
    def test_poids_de_reference(self):
        self.assertAlmostEqual(POIDS_MUR_REFERENCE_KN_M2, 3.3)

    def test_cle_de_troncon(self):
        self.assertEqual(cle_segment((4, 0), (0, 0)), "0.00;0.00|4.00;0.00")
        self.assertEqual(cle_segment((0, 0), (4, 0)), cle_segment((4, 0), (0, 0)))
        self.assertEqual(cle_segment((-0.0, 3 * 1.1), (0, 0)), "0.00;0.00|0.00;3.30")


class MursPlaces(SimpleTestCase):
    def test_charge_lineaire_d_un_mur(self):
        q, h_mur = charge_mur_kn_m(4.0, hyp(), 3.0)
        self.assertAlmostEqual(h_mur, 2.5)
        self.assertAlmostEqual(q, 8.25)
        # 20 % de baies : 8,25 × 0,8 = 6,6 kN/m
        self.assertAlmostEqual(charge_mur_kn_m(4.0, hyp(pourcentage_baies_murs=20), 3.0)[0], 6.6)

    def test_murs_d_etage_sur_une_seule_file(self):
        r = noeud(hyp(murs_etages=FILE_Y4))
        self.assertAlmostEqual(r["charge_murs_niveau_kn"], 33.0)
        self.assertAlmostEqual(r["charge_g_cumulee_kn"], 193.0)
        self.assertAlmostEqual(r["charge_elu_kn"], 332.55)
        self.assertAlmostEqual(r["charge_els_kn"], 241.0)
        self.assertAlmostEqual(r["charge_elu_semelle_kn"], 332.55)   # aucun mur au RDC
        self.assertIn("Murs d'étage / niveau", [e["etape"] for e in r["resultat_poteau"]["trace"]])

    def test_baies_deduites(self):
        # q = 6,6 kN/m ; G murs = 2 × 2 × 6,6 = 26,4 ; G = 186,4 ; Nu = 251,64 + 72 = 323,64 kN
        r = noeud(hyp(murs_etages=FILE_Y4, pourcentage_baies_murs=20))
        self.assertAlmostEqual(r["charge_elu_kn"], 323.64)

    def test_murs_du_rdc_reportes_sur_la_semelle(self):
        # 4 tronçons autour du poteau : G murs RDC = 4 × 2 × 8,25 = 66 kN
        # poteau : Nu = 1,35 × 160 + 72 = 288 kN ; semelle : 288 + 1,35 × 66 = 377,1 kN ; Ns = 208 + 66 = 274 kN
        r = noeud(hyp(murs_rdc=AUTOUR_P11))
        self.assertAlmostEqual(r["charge_elu_kn"], 288.0)
        self.assertAlmostEqual(r["charge_murs_rdc_kn"], 66.0)
        self.assertAlmostEqual(r["charge_elu_semelle_kn"], 377.1)
        self.assertAlmostEqual(r["charge_els_semelle_kn"], 274.0)
        self.assertIn("Murs du RDC (longrines → semelle)", [e["etape"] for e in r["resultat_semelle"]["trace"]])

    def test_poteau_d_angle_sur_facades(self):
        # 2 tronçons de façade : G murs = 2 × 2 × 8,25 = 33 ; S = 4 m²
        # G = 2 × 4 × 5 + 33 = 73 ; Q = 12 ; Nu = 98,55 + 18 = 116,55 kN
        facades = frozenset({cle_segment((0, 0), (4, 0)), cle_segment((0, 0), (0, 4))})
        r = noeud(hyp(murs_etages=facades), i=0, j=0)
        self.assertAlmostEqual(r["charge_elu_kn"], 116.55)

    def test_rien_n_est_suppose(self):
        # Poids saisi mais aucun mur placé : rien n'est compté, alerte.
        r = noeud(hyp())
        self.assertAlmostEqual(r["charge_elu_kn"], 288.0)
        self.assertTrue(any(m.startswith("ALERTE : aucun mur placé") for m in r["hypotheses"]))
        # Murs placés mais poids non renseigné : rien n'est compté, alerte.
        r = noeud(hyp(poids_murs_kn_m2=None, origine_poids_murs=None, murs_etages=FILE_Y4))
        self.assertAlmostEqual(r["charge_elu_kn"], 288.0)
        self.assertTrue(any(m.startswith("ALERTE : poids des murs non renseigné") for m in r["hypotheses"]))

    def test_plain_pied_ignore_les_murs_d_etage(self):
        r = noeud(hyp(murs_etages=FILE_Y4), nb_niveaux=1)
        self.assertAlmostEqual(r["charge_elu_kn"], 144.0)   # 1,35 × 80 + 1,5 × 24

    def test_poutre_qui_porte_un_mur(self):
        # largeur 4 m : g = 5 × 4 + 8,25 = 28,25 kN/m ; q = 6 kN/m
        # pu = 1,35 × 28,25 + 1,5 × 6 = 47,1375 kN/m ; pser = 34,25 kN/m
        cle = cle_segment((0, 4), (4, 4))
        r = generer_poutre_sur_grille(4.0, 4.0, 1.5, hyp=hyp(murs_etages=FILE_Y4), nb_niveaux=2,
                                      hauteur_etage=3.0, cle=cle, rive=False)
        self.assertAlmostEqual(r["charge_lineaire_kn_m"], 47.1375)
        self.assertAlmostEqual(r["charge_lineaire_service_kn_m"], 34.25)
        self.assertTrue(r["resultat_poutre"]["mur_etage"])
        self.assertEqual(r["resultat_poutre"]["cle_segment"], cle)
        # Tronçon sans mur : g = 20 kN/m
        sans = generer_poutre_sur_grille(4.0, 4.0, 1.5, hyp=hyp(murs_etages=FILE_Y4), nb_niveaux=2,
                                         hauteur_etage=3.0, cle=cle_segment((0, 0), (4, 0)))
        self.assertAlmostEqual(sans["charge_lineaire_service_kn_m"], 26.0)
        self.assertFalse(sans["resultat_poutre"]["mur_etage"])

    def test_bornes(self):
        with self.assertRaises(ValueError):
            charge_mur_kn_m(4.0, hyp(), 0.4)   # étage plus bas que la poutre (0,50 m)
        for kw in ({"poids_murs_kn_m2": 0}, {"poids_murs_kn_m2": 25}, {"pourcentage_baies_murs": -1},
                   {"pourcentage_baies_murs": 95}):
            with self.subTest(kw=kw), self.assertRaises(ValueError):
                hyp(**kw)


class PoutresCourtes(SimpleTestCase):
    def test_section_minimale_et_effort_tranchant(self):
        # L = 0,8 m, pu = 18 kN/m : h = max(0,1 ; 0,25) = 25 cm
        # Mu = 18 × 0,64 / 8 = 1,44 kN·m ; Vu = 18 × 0,8 / 2 = 7,2 kN
        # tau = 0,0072 / (0,20 × 0,225) = 0,16 MPa <= min(0,2 × 25 / 1,5 ; 5) = 3,333 MPa
        r = dimensionner_poutre(portee=0.8, charge_lineaire=18.0)
        self.assertEqual(r["hauteur_cm"], 25.0)
        self.assertEqual(r["largeur_cm"], 20.0)
        self.assertTrue(r["hauteur_minimale_appliquee"])
        self.assertAlmostEqual(r["moment_flechissant_knm"], 1.44)
        self.assertAlmostEqual(r["effort_tranchant_kn"], 7.2)
        self.assertAlmostEqual(r["contrainte_cisaillement_mpa"], 0.16)
        self.assertAlmostEqual(r["contrainte_cisaillement_limite_mpa"], 3.333)
        self.assertTrue(r["cisaillement_verifie"])

    def test_pas_de_saut_a_1_m(self):
        self.assertEqual(dimensionner_poutre(portee=1.2, charge_lineaire=20.0)["hauteur_cm"], 25.0)
        r = dimensionner_poutre(portee=4.0, charge_lineaire=20.0)
        self.assertEqual(r["hauteur_cm"], 50.0)
        self.assertFalse(r["hauteur_minimale_appliquee"])

    def test_poteaux_superposes_refuses(self):
        with self.assertRaises(ValueError):
            dimensionner_poutre(portee=0.15, charge_lineaire=10.0)


def p(nom, x, y):
    return {"guid": nom, "nom": nom, "x": x, "y": y}


class ImportPorteesCourtes(SimpleTestCase):
    def test_portee_de_0_8_m_calculee(self):
        nuage = [p("A", 0, 0), p("B", 4, 0), p("C", 4.8, 0), p("D", 0, 4), p("E", 4, 4), p("F", 4.8, 4)]
        r = generer_poteau_depuis_position_reelle(nuage[1], nuage, 1.5, 3.0, hyp=hyp())
        self.assertGreater(r["charge_elu_kn"], 0)
        ignores = []
        poutres = detecter_poutres_adjacentes(nuage, 1.5, hyp=hyp(), nb_niveaux=2, hauteur_etage=3.0,
                                              segments_ignores=ignores)
        self.assertEqual(ignores, [])
        courtes = [x for x in poutres if round(x["portee_m"], 2) == 0.8]
        self.assertEqual(len(courtes), 2)
        self.assertEqual(courtes[0]["resultat_poutre"]["hauteur_cm"], 25.0)

    def test_poteaux_superposes_signales(self):
        nuage = [p("A", 0, 0), p("B", 4, 0), p("C", 4.15, 0), p("D", 0, 4), p("E", 4, 4), p("F", 4.15, 4)]
        with self.assertRaises(ValueError) as ctx:
            generer_poteau_depuis_position_reelle(nuage[1], nuage, 1.5, 3.0, hyp=hyp())
        self.assertIn("Poteau B (x = 4 m ; y = 0 m) non calculé", str(ctx.exception))
        self.assertIn("0,15 m (droite)", str(ctx.exception))
        ignores = []
        detecter_poutres_adjacentes(nuage, 1.5, hyp=hyp(), nb_niveaux=2, hauteur_etage=3.0, segments_ignores=ignores)
        self.assertEqual(len(ignores), 2)
        self.assertTrue(all("non calculée" in m and "superposent" in m for m in ignores))


class APIPlanDesMurs(APITestCase):
    def setUp(self):
        self.user, self.cabinet = authentifier(self)
        self.projet = Projet.objects.create(
            nom="Murs", entreprise=self.cabinet, usage_batiment="habitation", nb_niveaux=2, hauteur_etage=3.0,
            nb_travees_x=2, nb_travees_y=2, portee_x=4.0, portee_y=4.0, charge_permanente_kn_m2=5.0,
            charge_exploitation=1.5, inclure_poids_propre_ossature=False)
        self.url = f"/api/projets/{self.projet.id}/"

    def generer(self):
        r = self.client.post(f"{self.url}generer_trame/")
        self.assertEqual(r.status_code, 201, r.data)
        return r

    def test_projet_sans_murs_inchange(self):
        r = self.generer()
        self.assertTrue(any(h.startswith("ALERTE : poids des murs") for h in r.data["hypotheses"]))
        self.assertAlmostEqual(self.projet.elements.get(identifiant="S_1_1").charge_calculee, 288.0)

    def test_trame_avec_plan_des_murs(self):
        r = self.client.patch(self.url, {"poids_murs_kn_m2": 3.3, "murs_etages": sorted(FILE_Y4)}, format="json")
        self.assertEqual(r.status_code, 200, r.data)
        self.generer()
        self.assertAlmostEqual(self.projet.elements.get(identifiant="P_1_1").charge_calculee, 332.55)
        px01 = self.projet.elements.get(identifiant="PX_0_1").resultat_calcul
        self.assertTrue(px01["mur_etage"])
        self.assertFalse(px01["rive"])
        px00 = self.projet.elements.get(identifiant="PX_0_0").resultat_calcul
        self.assertFalse(px00["mur_etage"])
        self.assertTrue(px00["rive"])
        self.assertEqual(px00["cle_segment"], "0.00;0.00|4.00;0.00")

    def test_mur_orphelin_signale(self):
        self.client.patch(self.url, {"poids_murs_kn_m2": 3.3, "murs_etages": ["99.00;0.00|99.00;4.00"]},
                          format="json")
        r = self.generer()
        self.assertTrue(any("ne correspondent plus à aucune poutre" in h for h in r.data["hypotheses"]))

    def test_validations(self):
        for champs in ({"murs_rdc": ["abc"]}, {"murs_etages": "0.00;0.00|4.00;0.00"},
                       {"pourcentage_baies_murs": 95}, {"poids_murs_kn_m2": 50}):
            with self.subTest(champs=champs):
                self.assertEqual(self.client.patch(self.url, champs, format="json").status_code, 400)
        r = self.client.patch(self.url, {"murs_rdc": ["0.00;0.00|4.00;0.00", "0.00;0.00|4.00;0.00"]}, format="json")
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.data["murs_rdc"], ["0.00;0.00|4.00;0.00"])   # doublons retirés

    def test_referentiel_propose_la_valeur_de_l_ingenieur(self):
        r = self.client.get("/api/referentiel/")
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.data["murs"]["reference"]["valeur_kn_m2"], 3.3)
        self.assertIsNone(r.data["murs"]["valeur_par_defaut"])
