"""Plan des murs propre à chaque étage (issue #81, règle B15 : les étages diffèrent).

CAS DE RÉFÉRENCE (calculé à la main) -- même trame que test_murs_et_portees :
trame 2 × 2 de 4 m, h_étage = 3 m, G = 5 kN/m², sans poids propre, p_mur = 3,3 kN/m²,
q_mur = 3,3 × (3 − 0,50) = 8,25 kN/m. R+2 (3 niveaux), poteau central (4 ; 4), S = 16 m² :
  G planchers = 3 × 16 × 5 = 240 kN
  R+1 : murs sur la file y = 4 (2 tronçons)        -> 2 × (4/2) × 8,25 = 33 kN
  R+2 : murs sur les 4 tronçons autour du poteau   -> 4 × (4/2) × 8,25 = 66 kN
  G = 240 + 33 + 66 = 339 kN   (plan unique R+1 pour tous les étages : 240 + 2 × 33 = 306 kN)
"""
from django.test import SimpleTestCase
from rest_framework.test import APITestCase

from moteur_calcul.formules.trame import cle_segment, generer_poutre_sur_grille
from projets.models import Profil, Projet
from projets.services.dqe_calculator import calculer_projet_dqe
from projets.tests_projets.test_murs_et_portees import AUTOUR_P11, FILE_Y4, hyp, noeud
from projets.tests_projets.utils import BAREME_TEST, authentifier


class ChargesParEtage(SimpleTestCase):
    def test_cas_de_reference_r_plus_2(self):
        identiques = noeud(hyp(murs_etages=FILE_Y4), nb_niveaux=3)
        self.assertAlmostEqual(identiques["charge_g_cumulee_kn"], 306.0)
        r = noeud(hyp(murs_etages=FILE_Y4, murs_etages_specifiques=((2, AUTOUR_P11),)), nb_niveaux=3)
        self.assertAlmostEqual(r["charge_g_cumulee_kn"], 339.0)
        self.assertAlmostEqual(r["charge_murs_etages_kn"], 99.0)
        q = r["charge_q_cumulee_kn"]
        self.assertAlmostEqual(q, identiques["charge_q_cumulee_kn"])   # les murs ne changent pas Q
        self.assertAlmostEqual(r["charge_elu_kn"], 1.35 * 339 + 1.5 * q)
        etapes = [e["etape"] for e in r["resultat_poteau"]["trace"]]
        self.assertIn("Murs du R+1", etapes)
        self.assertIn("Murs du R+2", etapes)
        g = next(e for e in r["resultat_poteau"]["trace"] if e["etape"] == "G cumulée")
        self.assertIn("Σ G murs des étages", g["formule"])
        self.assertIn("(33.0 + 66.0)", g["calcul"])

    def test_etage_sans_mur(self):
        # R+2 avec un plan propre VIDE : seul le R+1 porte des murs -> 240 + 33 = 273 kN
        r = noeud(hyp(murs_etages=FILE_Y4, murs_etages_specifiques=((2, frozenset()),)), nb_niveaux=3)
        self.assertAlmostEqual(r["charge_g_cumulee_kn"], 273.0)

    def test_poutre_portant_un_mur_a_un_seul_etage(self):
        k = cle_segment((0, 0), (4, 0))
        h = hyp(murs_etages=frozenset(), murs_etages_specifiques=((2, frozenset({k})),))
        avec = generer_poutre_sur_grille(4.0, 2.0, 1.5, hyp=h, nb_niveaux=3, hauteur_etage=3.0, cle=k)
        sans = generer_poutre_sur_grille(4.0, 2.0, 1.5, hyp=hyp(), nb_niveaux=3, hauteur_etage=3.0, cle=k)
        # Mêmes poutres à tous les niveaux, niveau le plus chargé : le mur du R+2 compte.
        self.assertAlmostEqual(avec["charge_lineaire_kn_m"] - sans["charge_lineaire_kn_m"], 1.35 * 8.25)


class API(APITestCase):
    def setUp(self):
        self.user, self.cabinet = authentifier(self, role=Profil.Role.ADMIN, bareme=BAREME_TEST)
        self.projet = Projet.objects.create(
            nom="R+2", entreprise=self.cabinet, usage_batiment="habitation", nb_niveaux=3, hauteur_etage=3.0,
            nb_travees_x=2, nb_travees_y=2, portee_x=4.0, portee_y=4.0, contrainte_sol_kn_m2=150,
            poids_murs_kn_m2=3.3, inclure_poids_propre_ossature=False)
        self.url = f"/api/projets/{self.projet.id}/"

    def g_central(self):
        self.assertEqual(self.client.post(f"{self.url}generer_trame/").status_code, 201)
        p = self.projet.elements.get(identifiant="P_1_1")
        return next(e for e in p.resultat_calcul["trace"] if e["etape"] == "G cumulée")["resultat"]

    def test_plan_propre_enregistre_et_calcule(self):
        r = self.client.patch(self.url, {"murs_etages": sorted(FILE_Y4), "murs_par_etage": {"2": sorted(AUTOUR_P11)}},
                              format="json")
        self.assertEqual(r.status_code, 200, r.data)
        self.assertEqual(self.g_central(), 339.0)

    def test_validation(self):
        for mauvais in ({"1": []}, {"x": []}, {"2": ["pas une clé"]}, ["2"]):
            r = self.client.patch(self.url, {"murs_par_etage": mauvais}, format="json")
            self.assertEqual(r.status_code, 400, mauvais)

    def test_plan_d_un_etage_qui_n_existe_plus(self):
        self.client.patch(self.url, {"murs_etages": sorted(FILE_Y4), "murs_par_etage": {"5": sorted(AUTOUR_P11)}},
                          format="json")
        r = self.client.post(f"{self.url}generer_trame/")
        self.assertTrue(any("R+5 ignoré" in h for h in r.data["hypotheses"]))
        p = self.projet.elements.get(identifiant="P_1_1")
        self.assertEqual(next(e for e in p.resultat_calcul["trace"] if e["etape"] == "G cumulée")["resultat"], 306.0)

    def test_metre_des_murs_par_etage(self):
        k = cle_segment((0, 4), (4, 4))
        # mur au R+1 (plan commun) mais pas au R+2 (plan propre sans ce tronçon) : compté 1 fois
        self.client.patch(self.url, {"murs_etages": [k], "murs_par_etage": {"2": []},
                                     "metrer_murs_depuis_plan": True}, format="json")
        self.g_central()
        for e in self.projet.elements.all():
            self.client.post(f"/api/elements/{e.id}/valider/")
        self.projet.refresh_from_db()
        d = calculer_projet_dqe(self.projet, prix_unitaires=self.cabinet.get_prix_unitaires())
        agglos = next(l for l in d["lignes"] if l["designation"] == "Agglos 15 creux — murs du plan")
        self.assertEqual([(t["niveau"], t["nombre"]) for t in agglos["detail_murs"]], [("étages", 1)])
