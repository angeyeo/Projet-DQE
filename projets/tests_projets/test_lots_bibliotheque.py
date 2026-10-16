"""
Lots du second œuvre (09 à 15) et bibliothèque d'ouvrages du cabinet.

Cas de référence (prix DE TEST, fournis par le test) :
  ouvrage « Porte isoplane 0,80 × 2,10 », u, 85 000 FCFA (source « devis test »)
  poste repris : 3 u -> 3 × 85 000 = 255 000 FCFA au lot 09
  poste repris avec prix saisi 90 000 -> 270 000 FCFA, origine « saisie (poste) »
"""

from rest_framework.test import APITestCase

from projets.models import OuvrageType, PosteComplementaire, Profil, Projet
from projets.services.dqe_exporters import regrouper_par_lot
from projets.tests_projets.utils import BAREME_TEST, authentifier, creer_cabinet, creer_membre

URL = "/api/ouvrages/"


class LotsSecondOeuvre(APITestCase):
    def test_lots_ajoutes_apres_les_existants(self):
        codes = PosteComplementaire.Lot.values
        self.assertEqual(codes[9], "lot_08_couverture")   # 10 lots existants inchangés
        self.assertEqual(codes[-7:], ["lot_09_menuiserie_bois", "lot_10_menuiserie_metallique", "lot_11_revetements",
                                      "lot_12_peinture", "lot_13_faux_plafond", "lot_14_vrd", "lot_15_divers"])

    def test_referentiel_et_export(self):
        authentifier(self)
        r = self.client.get("/api/referentiel/")
        cles = [l["cle"] for l in r.data["lots"]]
        self.assertIn("lot_12_peinture", cles)
        groupes = regrouper_par_lot({"lots": [
            {"lot": "lot_12_peinture", "libelle": "Peinture", "lignes": [], "sous_total": 10},
            {"lot": "lot_02_gros_oeuvre_superstructure", "libelle": "GO", "lignes": [], "sous_total": 5},
        ]})
        self.assertEqual([g["label"] for g in groupes], ["LOT 02 — GROS ŒUVRE", "LOT 12 — PEINTURE"])


class Bibliotheque(APITestCase):
    def setUp(self):
        self.user, self.cabinet = authentifier(self, role=Profil.Role.INGENIEUR, bareme=BAREME_TEST)
        self.projet = Projet.objects.create(nom="Villa", entreprise=self.cabinet)

    def creer(self, **kw):
        donnees = {"lot": "lot_09_menuiserie_bois", "designation": "Porte isoplane 0,80 × 2,10", "unite": "u",
                   "prix_unitaire": 85000, "source_prix": "devis test", "date_prix": "2026-10-16"} | kw
        return self.client.post(URL, donnees, format="json")

    def test_creation_et_liste_filtree(self):
        r = self.creer()
        self.assertEqual(r.status_code, 201, r.data)
        self.assertEqual(r.data["lot_libelle"], "Menuiserie bois")
        self.creer(lot="lot_12_peinture", designation="Peinture glycéro", unite="m²", prix_unitaire=2500)
        self.assertEqual(len(self.client.get(URL).data), 2)
        self.assertEqual(len(self.client.get(URL, {"lot": "lot_12_peinture"}).data), 1)
        self.assertEqual(len(self.client.get(URL, {"q": "porte"}).data), 1)
        o = OuvrageType.objects.get(designation="Porte isoplane 0,80 × 2,10")
        self.assertEqual((o.entreprise, o.cree_par), (self.cabinet, self.user))

    def test_validations(self):
        self.creer()
        self.assertEqual(self.creer().status_code, 400)                           # doublon
        self.assertEqual(self.creer(designation="Autre", prix_unitaire=-1).status_code, 400)
        self.assertEqual(self.creer(designation="  ").status_code, 400)
        self.assertEqual(self.creer(designation="Autre", lot="lot_99").status_code, 400)
        self.assertEqual(self.creer(designation="Sans prix", prix_unitaire=None).status_code, 201)

    def test_poste_repris_de_la_bibliotheque(self):
        ouvrage = self.creer().data["id"]
        r = self.client.post("/api/postes-complementaires/", {
            "projet": self.projet.id, "mode": "simple", "ouvrage": ouvrage, "quantite": 3}, format="json")
        self.assertEqual(r.status_code, 201, r.data)
        self.assertEqual((r.data["designation"], r.data["unite"], r.data["lot"]),
                         ("Porte isoplane 0,80 × 2,10", "u", "lot_09_menuiserie_bois"))
        self.assertEqual(r.data["montant"], 255000)
        self.assertEqual(r.data["prix_source"], "bibliothèque du cabinet (devis test)")

        # Le prix de la bibliothèque change : le poste du projet ne bouge pas.
        self.client.patch(f"{URL}{ouvrage}/", {"prix_unitaire": 99000}, format="json")
        self.assertEqual(PosteComplementaire.objects.get(pk=r.data["id"]).prix_unitaire, 85000)

        d = self.client.post(f"/api/projets/{self.projet.id}/generer-dqe/", format="json").json()
        ligne = next(l for l in d["lignes"] if l["designation"].startswith("Porte"))
        self.assertEqual((ligne["montant"], ligne["lot"]), (255000, "lot_09_menuiserie_bois"))
        self.assertEqual((ligne["prix_source"], ligne["prix_date"]), ("bibliothèque du cabinet (devis test)", "2026-10-16"))
        self.assertEqual(d["total_general"], 255000)

    def test_prix_saisi_prioritaire(self):
        ouvrage = self.creer().data["id"]
        r = self.client.post("/api/postes-complementaires/", {
            "projet": self.projet.id, "mode": "simple", "ouvrage": ouvrage, "quantite": 3,
            "prix_unitaire": 90000}, format="json")
        self.assertEqual(r.data["montant"], 270000)
        self.assertEqual(r.data["prix_source"], "saisie (poste)")

    def test_ouvrage_sans_prix_exige_un_prix(self):
        ouvrage = self.creer(designation="Sans prix", prix_unitaire=None).data["id"]
        r = self.client.post("/api/postes-complementaires/", {
            "projet": self.projet.id, "mode": "simple", "ouvrage": ouvrage, "quantite": 2}, format="json")
        self.assertEqual(r.status_code, 400)
        self.assertIn("prix_unitaire", r.data)

    def test_suppression_de_l_ouvrage_garde_le_poste(self):
        ouvrage = self.creer().data["id"]
        poste = self.client.post("/api/postes-complementaires/", {
            "projet": self.projet.id, "mode": "simple", "ouvrage": ouvrage, "quantite": 1}, format="json").data["id"]
        self.assertEqual(self.client.get(f"{URL}{ouvrage}/").data["nb_postes"], 1)
        self.assertEqual(self.client.delete(f"{URL}{ouvrage}/").status_code, 204)
        p = PosteComplementaire.objects.get(pk=poste)
        self.assertIsNone(p.ouvrage)
        self.assertEqual((p.designation, p.prix_unitaire), ("Porte isoplane 0,80 × 2,10", 85000))

    def test_isolation_entre_cabinets(self):
        ouvrage = self.creer().data["id"]
        autre = creer_cabinet("Autre")
        intrus = creer_membre(autre, username="intrus", role=Profil.Role.ADMIN)
        projet_autre = Projet.objects.create(nom="P", entreprise=autre)
        self.client.force_authenticate(intrus)
        self.assertEqual(self.client.get(URL).data, [])
        self.assertEqual(self.client.get(f"{URL}{ouvrage}/").status_code, 404)
        r = self.client.post("/api/postes-complementaires/", {
            "projet": projet_autre.id, "mode": "simple", "ouvrage": ouvrage, "quantite": 1}, format="json")
        self.assertEqual(r.status_code, 400)
        self.assertIn("ouvrage", r.data)

    def test_technicien_en_lecture_seule(self):
        self.creer()
        tech = creer_membre(self.cabinet, username="tech", role=Profil.Role.TECHNICIEN)
        self.client.force_authenticate(tech)
        self.assertEqual(self.client.get(URL).status_code, 200)
        self.assertEqual(self.creer(designation="X").status_code, 403)

    def test_non_authentifie(self):
        self.client.force_authenticate(None)
        self.assertIn(self.client.get(URL).status_code, (401, 403))
