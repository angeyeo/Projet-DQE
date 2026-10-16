"""Analytics : chiffres issus UNIQUEMENT de la base et du journal
d'événements -- jamais d'estimation ni de données fictives."""

from django.contrib.auth.models import User
from rest_framework import status
from rest_framework.test import APITestCase

from projets.models import ElementStructurel, EvenementProduit, Projet
from projets.tests_projets.utils import BAREME_TEST, authentifier, creer_cabinet, creer_membre


class AnalyticsTestCase(APITestCase):
    def setUp(self):
        self.user, self.cabinet = authentifier(self, bareme=BAREME_TEST)

    def _projet_valide(self, nom="Villa"):
        r = self.client.post("/api/projets/", {"nom": nom, "usage_batiment": "habitation"}, format="json")
        projet = Projet.objects.get(pk=r.data["id"])
        el = ElementStructurel.objects.create(
            projet=projet, type_element="poteau", identifiant="P1", hauteur_poteau=3.0,
            resultat_calcul={"cote_cm": 20},
        )
        self.client.post(f"/api/elements/{el.id}/valider/")
        return projet

    def test_cabinet_vide_aucune_valeur_inventee(self):
        r = self.client.get("/api/analytics/cabinet/")
        self.assertEqual(r.status_code, status.HTTP_200_OK)
        self.assertEqual(r.data["projets"]["total"], 0)
        self.assertEqual(r.data["dqe"]["valeur_totale"], 0)
        self.assertEqual(r.data["activite_recente"], [])

    def test_flux_reel_de_bout_en_bout(self):
        projet = self._projet_valide()
        r = self.client.get(f"/api/projets/{projet.id}/generer-dqe/")
        total = r.data["total_general"]
        # 0,12 m³ x 100 000 + 2,4 m² x 12 000 + 15 kg x 800 = 52 800 FCFA
        self.assertEqual(total, 52800)

        d = self.client.get("/api/analytics/cabinet/").data
        self.assertEqual(d["projets"]["par_statut"]["dqe_genere"], 1)
        self.assertEqual(d["dqe"]["valeur_totale"], 52800)
        self.assertEqual(d["dqe"]["repartition_par_categorie"]["beton"], 12000)
        self.assertEqual(d["elements"]["valides"], 1)
        types = [e["type"] for e in d["activite_recente"]]
        self.assertEqual(types[:3], ["dqe_genere", "element_valide", "projet_cree"])
        self.assertIsNotNone(d["date_debut_fiabilite"])

        p = self.client.get(f"/api/analytics/projets/{projet.id}/").data
        self.assertEqual(p["statut"], "dqe_genere")
        self.assertEqual(p["cout"]["total"], 52800)
        self.assertFalse(p["cout"]["partiel"])
        ratio = p["cout"]["ratios_acier"][0]
        self.assertEqual(ratio["ratio_kg_m3"], 125.0)
        self.assertTrue(ratio["acier_estime"])  # ratio de référence : comparaison non probante

    def test_regeneration_ne_double_pas_la_valeur(self):
        projet = self._projet_valide()
        self.client.get(f"/api/projets/{projet.id}/generer-dqe/")
        self.client.get(f"/api/projets/{projet.id}/generer-dqe/")
        self.assertEqual(self.client.get("/api/analytics/cabinet/").data["dqe"]["valeur_totale"], 52800)
        # Réaffichage sans aucun changement : pas un nouveau DQE.
        self.assertEqual(EvenementProduit.objects.filter(type="dqe_genere").count(), 1)

    def test_projet_modifie_apres_dqe_signale_a_regenerer(self):
        projet = self._projet_valide()
        self.client.get(f"/api/projets/{projet.id}/generer-dqe/")
        el = projet.elements.get()
        self.client.post(f"/api/elements/{el.id}/deverrouiller/")
        d = self.client.get("/api/analytics/cabinet/").data
        raisons = " ".join(r for p in d["projets_a_traiter"] for r in p["raisons"])
        self.assertIn("à régénérer", raisons)

    def test_bareme_incomplet_remonte_les_prix_manquants_au_lieu_d_un_cout(self):
        self.cabinet.prix_unitaires = {}
        self.cabinet.save()
        projet = self._projet_valide()
        p = self.client.get(f"/api/analytics/projets/{projet.id}/").data
        self.assertIsNone(p["cout"])
        self.assertTrue(any(pb["code"] == "PRIX_MANQUANT" for pb in p["problemes_dqe"]))
        d = self.client.get("/api/analytics/cabinet/").data
        self.assertEqual(len(d["bareme"]["prix_manquants"]), 7)

    def test_isolation_cabinet(self):
        projet = self._projet_valide()
        intrus = creer_membre(creer_cabinet("Autre"), username="intrus")
        self.client.force_authenticate(user=intrus)
        self.assertEqual(self.client.get(f"/api/analytics/projets/{projet.id}/").status_code, 404)
        self.assertEqual(self.client.get("/api/analytics/cabinet/").data["projets"]["total"], 0)

    def test_mois_anterieurs_au_journal_sont_inconnus_pas_nuls(self):
        self._projet_valide()
        serie = self.client.get("/api/analytics/cabinet/").data["activite_mensuelle"]["projets_crees"]
        self.assertEqual(serie[-1]["valeur"], 1)
        # Le journal démarre ce mois-ci : les 11 mois précédents sont inconnus.
        self.assertTrue(all(m["valeur"] is None for m in serie[:-1]))


class AnalyticsStaffTestCase(APITestCase):
    def test_reserve_au_staff(self):
        authentifier(self)
        self.assertEqual(self.client.get("/api/analytics/staff/").status_code, 403)

    def test_funnel_sur_cohorte_journalisee(self):
        staff = User.objects.create_user("staff", password="x", is_staff=True)
        # Inscription réelle via l'API (journalise l'événement)
        r = self.client.post("/api/auth/inscription/", {
            "nom_entreprise": "BATI SARL", "username": "admin_bati",
            "email": "a@bati.ci", "mot_de_passe": "UnMotDePasseSolide2026!",
        }, format="json")
        self.assertEqual(r.status_code, 201)
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {r.data['access']}")
        self.client.post("/api/projets/", {"nom": "P"}, format="json")
        # Cabinet "ancien" sans inscription journalisée : hors cohorte
        ancien = creer_cabinet("Ancien")
        EvenementProduit.objects.create(type="projet_cree", entreprise=ancien)

        self.client.credentials()
        self.client.force_authenticate(user=staff)
        d = self.client.get("/api/analytics/staff/").data
        funnel = {e["etape"]: e["cabinets"] for e in d["funnel"]}
        self.assertEqual(funnel["inscription"], 1)
        self.assertEqual(funnel["premier_projet"], 1)
        self.assertEqual(funnel["premier_dqe"], 0)
        self.assertEqual(d["totaux"]["cabinets_inscrits"], 1)
        self.assertEqual(d["totaux"]["cabinets_actifs_30j"], 2)
