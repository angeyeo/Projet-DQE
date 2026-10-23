"""Maçonnerie et enduit tirés du plan des murs (issue #73).

CAS DE RÉFÉRENCE recalculé à la main : trame 2 × 2 (portées 4,0 en X et
3,5 en Y), R+1 (nb_niveaux = 2), h_étage = 3,0 m, poteaux 20 × 20.
  k1 = tronçon (0 ; 0)-(4 ; 0) : mur au RDC ET aux étages ; poutre h = max(4/8 ; 0,25) = 0,50 m
       L_net = 4,0 − (0,20 + 0,20)/2 = 3,80 m ; h_mur = 3,0 − 0,50 = 2,50 m -> 9,50 m² par niveau
  k2 = tronçon (0 ; 0)-(0 ; 3,5) : mur aux étages seulement ; h = max(3,5/8 ; 0,25) = 0,4375 m,
       VALIDÉE par le moteur à 43,8 cm (arrondi au mm) : c'est elle qui fait foi (même hauteur que le béton)
       L_net = 3,5 − 0,20 = 3,30 m ; h_mur = 3,0 − 0,438 = 2,562 m -> 8,4546 m²
  S_brute = 9,50 (RDC) + 9,50 (étage) + 8,4546 (étage) = 27,4546 m²
  baies non saisies : × 0,80 (règle B6)  -> agglos 21,96368 -> 21,964 m² ; enduit 2 faces = 2 × 21,964 = 43,928 m²
  baies saisies 15 % : × 0,85            -> agglos 23,33641 -> 23,336 m²
"""
from rest_framework.test import APITestCase

from moteur_calcul.formules.trame import cle_segment
from projets.models import PosteComplementaire, Profil, Projet
from projets.services.dqe_calculator import DQEIncomplet, calculer_projet_dqe
from projets.tests_projets.utils import BAREME_TEST, authentifier

K1 = cle_segment((0, 0), (4, 0))
K2 = cle_segment((0, 0), (0, 3.5))


class MetreMurs(APITestCase):
    def setUp(self):
        self.user, self.cabinet = authentifier(self, role=Profil.Role.ADMIN, bareme=BAREME_TEST)
        self.projet = Projet.objects.create(
            nom="Murs", entreprise=self.cabinet, usage_batiment="habitation", nb_niveaux=2, hauteur_etage=3.0,
            nb_travees_x=2, nb_travees_y=2, portee_x=4.0, portee_y=3.5, contrainte_sol_kn_m2=150,
            poids_murs_kn_m2=3.3, murs_rdc=[K1], murs_etages=[K1, K2])
        self.assertEqual(self.client.post(f"/api/projets/{self.projet.id}/generer_trame/").status_code, 201)
        for e in self.projet.elements.all():
            self.client.post(f"/api/elements/{e.id}/valider/")

    def dqe(self):
        self.projet.refresh_from_db()
        self.cabinet.refresh_from_db()
        return calculer_projet_dqe(self.projet, prix_unitaires=self.cabinet.get_prix_unitaires())

    def lignes_murs(self, d):
        return {l["designation"]: l for l in d["lignes"] if l["type_element"] == "MURS_PLAN"}

    def test_desactive_par_defaut(self):
        self.assertEqual(self.lignes_murs(self.dqe()), {})

    def test_cas_de_reference(self):
        for p in self.projet.elements.filter(type_element="poteau"):
            self.assertEqual(p.resultat_valide["cote_cm"], 20)  # hypothèse du calcul à la main
        r = self.client.patch(f"/api/projets/{self.projet.id}/", {"metrer_murs_depuis_plan": True}, format="json")
        self.assertEqual(r.status_code, 200, r.data)
        d = self.dqe()
        m = self.lignes_murs(d)
        agglos, enduit = m["Agglos 15 creux — murs du plan"], m["Enduit 2 faces — murs du plan"]
        h_py = self.projet.elements.get(identifiant="PY_0_0").resultat_valide["hauteur_cm"]
        self.assertEqual(h_py, 43.8)
        self.assertEqual((agglos["quantite"], enduit["quantite"]), (21.964, 43.928))
        self.assertEqual(agglos["montant"], round(agglos["quantite"] * BAREME_TEST["agglos_15_creux_m2"]))
        self.assertEqual((agglos["type_donnee"], agglos["lot"]), ("estimé", "lot_02_gros_oeuvre_superstructure"))
        self.assertEqual(len(agglos["detail_murs"]), 3)  # k1 RDC, k1 étages, k2 étages
        self.assertTrue(any("règle B6" in h for h in d["hypotheses"]))
        self.assertTrue(d["projet"]["metrer_murs_depuis_plan"])

        # Part des baies saisie : coefficient exact, ligne « calculé ».
        self.projet.pourcentage_baies_murs = 15
        self.projet.save()
        agglos = self.lignes_murs(self.dqe())["Agglos 15 creux — murs du plan"]
        self.assertEqual(agglos["quantite"], 23.336)
        self.assertEqual(agglos["type_donnee"], "calculé")

    def test_pas_de_double_comptage(self):
        self.projet.metrer_murs_depuis_plan = True
        self.projet.save()
        PosteComplementaire.objects.create(projet=self.projet, lot="lot_02_gros_oeuvre_superstructure", mode="ratio",
                                           type_poste="maconnerie", geometrie={"perimetre_batiment_m": 30, "hauteur_etage_m": 3, "nb_niveaux": 2})
        PosteComplementaire.objects.create(projet=self.projet, lot="lot_12_peinture", mode="simple",
                                           designation="Enduit de façade", unite="m²", quantite=10, prix_unitaire=3000)
        d = self.dqe()
        m = self.lignes_murs(d)
        self.assertNotIn("Agglos 15 creux — murs du plan", m)       # le poste à ratio prime
        self.assertIn("Enduit 2 faces — murs du plan", m)
        self.assertTrue(any("pas de double comptage" in h for h in d["hypotheses"]))
        self.assertTrue(any("Enduit de façade" in h and "double emploi" in h for h in d["hypotheses"]))

    def test_prix_manquant_explicite(self):
        self.projet.metrer_murs_depuis_plan = True
        self.projet.save()
        self.cabinet.prix_unitaires = {k: v for k, v in BAREME_TEST.items() if k != "agglos_15_creux_m2"}
        self.cabinet.save()
        with self.assertRaises(DQEIncomplet) as ctx:
            self.dqe()
        self.assertTrue(any("plan des murs" in p["message"] for p in ctx.exception.problemes))

    def test_aucun_mur_place(self):
        self.projet.murs_rdc, self.projet.murs_etages, self.projet.metrer_murs_depuis_plan = [], [], True
        self.projet.save()
        d = self.dqe()
        self.assertEqual(self.lignes_murs(d), {})
        self.assertTrue(any("aucun mur n'est placé" in h for h in d["hypotheses"]))
