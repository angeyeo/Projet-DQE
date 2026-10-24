"""Prix par type d'ouvrage (béton, coffrage), facultatifs.

Origine : DQE CIMBAT n°0017-2026 (villa AKPA), coffrage à 3 000 FCFA/m² en
fondation, 4 000 aux poteaux, 5 000 aux poutres et dalles.

CAS DE RÉFÉRENCE : poteau P_1_1 du projet de référence (2 niveaux) ; on lit sa
quantité de coffrage q dans le DQE ; avec un prix propre aux poteaux de
4 000 FCFA/m², montant = round(q × 4 000) ; une semelle sans prix « fondations »
garde le prix général (12 000) et la ligne le dit.
"""
from rest_framework.test import APITestCase

from projets.models import Profil, Projet
from projets.services.dqe_calculator import DQEIncomplet, calculer_projet_dqe
from projets.tests_projets.utils import BAREME_TEST, authentifier


class PrixParOuvrage(APITestCase):
    def setUp(self):
        self.user, self.cabinet = authentifier(self, role=Profil.Role.ADMIN, bareme=BAREME_TEST)
        self.projet = Projet.objects.create(
            nom="Réf", entreprise=self.cabinet, usage_batiment="habitation", nb_niveaux=2, hauteur_etage=3.0,
            nb_travees_x=2, nb_travees_y=2, portee_x=4.0, portee_y=3.5, contrainte_sol_kn_m2=150)
        self.client.post(f"/api/projets/{self.projet.id}/generer_trame/")
        for e in self.projet.elements.all():
            self.client.post(f"/api/elements/{e.id}/valider/")

    def dqe(self, **prix):
        self.cabinet.prix_unitaires = {**BAREME_TEST, **prix}
        self.cabinet.save()
        return calculer_projet_dqe(self.projet, prix_unitaires=self.cabinet.get_prix_unitaires())

    def ligne(self, d, repere, categorie):
        return next(l for l in d["lignes"] if l["repere"] == repere and l["categorie"] == categorie)

    def test_sans_prix_propre_rien_ne_change(self):
        d = self.dqe()
        c = self.ligne(d, "P_1_1", "COFFRAGE")
        self.assertEqual((c["cle_prix"], c["prix_unitaire"]), ("coffrage_m2", 12000))
        self.assertNotIn("prix général", c["prix_source"])

    def test_prix_propre_aux_poteaux(self):
        d = self.dqe(coffrage_poteaux_m2=4000, beton_dalles_m3=90000)
        c = self.ligne(d, "P_1_1", "COFFRAGE")
        self.assertEqual((c["cle_prix"], c["prix_unitaire"]), ("coffrage_poteaux_m2", 4000))
        self.assertEqual(c["montant"], round(c["quantite"] * 4000))
        self.assertIn("prix propre", c["prix_source"])
        s = self.ligne(d, "S_1_1", "COFFRAGE")                       # fondations : prix général
        self.assertEqual((s["cle_prix"], s["prix_unitaire"]), ("coffrage_m2", 12000))
        self.assertIn("prix général", s["prix_source"])
        b = self.ligne(d, "P_1_1", "BETON")                          # béton des poteaux : général
        self.assertEqual(b["prix_unitaire"], 100000)
        self.assertEqual(sum(l["montant"] for l in d["lignes"]), d["total_general"])

    def test_prix_general_absent_mais_prix_propre_present(self):
        prix = {k: v for k, v in BAREME_TEST.items() if k != "coffrage_m2"}
        self.cabinet.prix_unitaires = {**prix, "coffrage_poteaux_m2": 4000}
        self.cabinet.save()
        with self.assertRaises(DQEIncomplet) as ctx:
            calculer_projet_dqe(self.projet, prix_unitaires=self.cabinet.get_prix_unitaires())
        # Les poteaux sont chiffrés ; les autres ouvrages réclament le prix général.
        msg = [p["message"] for p in ctx.exception.problemes if p.get("cle_prix") == "coffrage_m2"]
        self.assertEqual(len(msg), 1)
        self.assertIn("Coffrage (FCFA/m²)", msg[0])

    def test_decomposition_et_api(self):
        r = self.client.patch("/api/entreprise/", {
            "prix_unitaires": {**BAREME_TEST, "coffrage_poteaux_m2": 4000},
            "prix_decomposition": {"coffrage_poteaux_m2": {"materiaux": 1500, "main_oeuvre": 2500}}}, format="json")
        self.assertEqual(r.status_code, 200, r.data)
        self.assertEqual(r.data["prix_unitaires_meta"]["coffrage_poteaux_m2"]["source"], "saisie")
        self.cabinet.refresh_from_db()
        d = calculer_projet_dqe(self.projet, prix_unitaires=self.cabinet.get_prix_unitaires())
        c = self.ligne(d, "P_1_1", "COFFRAGE")
        self.assertEqual(c["decomposition"], "decompose")
        self.assertEqual(c["montant_materiaux"] + c["montant_main_oeuvre"], c["montant"])
        ref = self.client.get("/api/referentiel/").data["cles_prix_par_ouvrage"]
        self.assertIn({"generale": "coffrage_m2", "cle": "coffrage_poteaux_m2", "famille": "Poteaux",
                       "libelle": "Coffrage — poteaux (FCFA/m²)"}, ref)
        self.assertEqual(len(ref), 10)
