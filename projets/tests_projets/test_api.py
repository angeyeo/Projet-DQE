"""
Tests des endpoints API.

Comme pour le moteur de calcul, certains tests vérifient volontairement
qu'on reçoit une erreur "503 / moteur non disponible" tant que les
formules ne sont pas injectées -- ça confirme que le branchement
vue -> service -> moteur_calcul fonctionne correctement de bout en bout.
"""

from rest_framework.test import APITestCase
from rest_framework import status
from unittest.mock import patch
from projets.models import Projet, ElementStructurel
from projets.tests_projets.utils import authentifier


class TestProjetAPI(APITestCase):
    def setUp(self):
        self.user, self.entreprise = authentifier(self, nom_cabinet="Cabinet Test API")

    def test_creer_projet(self):
        response = self.client.post(
            "/api/projets/",
            {"nom": "Immeuble test", "usage_batiment": "habitation", "nb_niveaux": 2},
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(Projet.objects.count(), 1)
        # Aucune valeur inventée : non saisi = vide.
        projet = Projet.objects.get()
        self.assertIsNone(projet.portee_x)
        self.assertIsNone(projet.hauteur_etage)

    def test_usage_non_canonique_refuse(self):
        response = self.client.post("/api/projets/", {"nom": "X", "usage_batiment": "commercial"})
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("usage_batiment", response.data)

    def test_contrainte_sol_en_mpa_refusee(self):
        response = self.client.post("/api/projets/", {"nom": "X", "contrainte_sol_kn_m2": 0.2})
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_generer_trame_parametres_manquants_explicites(self):
        projet = Projet.objects.create(nom="Vide", entreprise=self.entreprise)
        response = self.client.post(f"/api/projets/{projet.id}/generer_trame/")
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        champs = {m["champ"] for m in response.data["champs_manquants"]}
        self.assertTrue({"usage_batiment", "nb_niveaux", "hauteur_etage", "portee_x"} <= champs)
        self.assertEqual(projet.elements.count(), 0)

    def test_liste_resumee_avec_compteurs(self):
        projet = Projet.objects.create(nom="A", entreprise=self.entreprise)
        ElementStructurel.objects.create(projet=projet, type_element="poteau", identifiant="P1")
        response = self.client.get("/api/projets/")
        self.assertEqual(response.data[0]["nb_elements"], 1)
        self.assertEqual(response.data[0]["nb_elements_valides"], 0)
        self.assertNotIn("elements", response.data[0])

    def test_lister_projets(self):
        Projet.objects.create(
            nom="A", 
            usage_batiment="bureau", 
            nb_niveaux=1,
            entreprise=self.entreprise,
            cree_par=self.user
        )
        response = self.client.get("/api/projets/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 1)


class TestElementStructurelAPI(APITestCase):
    def setUp(self):
        self.user, self.entreprise = authentifier(self, nom_cabinet="Cabinet Test API")

        self.projet = Projet.objects.create(
            nom="Immeuble test", 
            usage_batiment="habitation", 
            nb_niveaux=2,
            entreprise=self.entreprise,
            cree_par=self.user
        )

    def test_creer_element(self):
        response = self.client.post(
            "/api/elements/",
            {
                "projet": self.projet.id,
                "type_element": "poteau",
                "identifiant": "P1",
                "charge_calculee": 250,
                "hauteur_poteau": 3.0,
            },
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

    def test_filtrer_elements_par_projet(self):
        ElementStructurel.objects.create(
            projet=self.projet, type_element="poteau", identifiant="P1"
        )
        response = self.client.get(f"/api/elements/?projet={self.projet.id}")
        self.assertEqual(len(response.data), 1)

    @patch("projets.services.calculations.dimensionner_poteau")
    def test_calculer_element_renvoie_moteur_non_disponible(self, mock_dim):
        """
        Tant que les formules ne sont pas injectées dans moteur_calcul,
        cet appel doit renvoyer 503 -- pas une erreur 500 non gérée.
        """
        mock_dim.side_effect = NotImplementedError("Formule en attente")
        element = ElementStructurel.objects.create(
            projet=self.projet,
            type_element="poteau",
            identifiant="P1",
            charge_calculee=250,
            hauteur_poteau=3.0,
        )
        response = self.client.post(f"/api/elements/{element.id}/calculer/")
        self.assertEqual(response.status_code, status.HTTP_503_SERVICE_UNAVAILABLE)

    def test_valider_element_sans_resultat_calcul_echoue(self):
        element = ElementStructurel.objects.create(
            projet=self.projet, type_element="poteau", identifiant="P1"
        )
        response = self.client.post(f"/api/elements/{element.id}/valider/")
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_valider_element_avec_resultat_calcul(self):
        """Le verrou logiciel : un élément avec un résultat peut être validé."""
        element = ElementStructurel.objects.create(
            projet=self.projet,
            type_element="poteau",
            identifiant="P1",
            resultat_calcul={"largeur_cm": 25, "profondeur_cm": 25},
        )
        response = self.client.post(f"/api/elements/{element.id}/valider/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        element.refresh_from_db()
        self.assertEqual(element.statut, ElementStructurel.Statut.VALIDE)

    def test_element_valide_verrouille_cote_serveur(self):
        """Verrou serveur : un élément validé n'est PAS modifiable tant
        qu'un ingénieur ne l'a pas déverrouillé ; le déverrouillage retire
        le résultat validé (il ne peut plus entrer au DQE)."""
        element = ElementStructurel.objects.create(
            projet=self.projet,
            type_element="poteau",
            identifiant="P1",
            resultat_calcul={"largeur_cm": 25},
            resultat_valide={"largeur_cm": 25},
            statut=ElementStructurel.Statut.VALIDE,
        )
        response = self.client.patch(f"/api/elements/{element.id}/", {"hauteur_poteau": 3.5})
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

        response = self.client.post(f"/api/elements/{element.id}/deverrouiller/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        element.refresh_from_db()
        self.assertEqual(element.statut, ElementStructurel.Statut.MODIFIE)
        self.assertIsNone(element.resultat_valide)

        response = self.client.patch(f"/api/elements/{element.id}/", {"hauteur_poteau": 3.5})
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_technicien_ne_peut_pas_deverrouiller(self):
        from projets.models import Profil
        from projets.tests_projets.utils import creer_membre

        tech = creer_membre(self.entreprise, username="tech", role=Profil.Role.TECHNICIEN)
        element = ElementStructurel.objects.create(
            projet=self.projet, type_element="poteau", identifiant="P1",
            resultat_valide={"cote_cm": 25}, statut=ElementStructurel.Statut.VALIDE,
        )
        self.client.force_authenticate(user=tech)
        response = self.client.post(f"/api/elements/{element.id}/deverrouiller/")
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_generer_dqe_refuse_si_elements_non_valides(self):
        ElementStructurel.objects.create(
            projet=self.projet, type_element="poteau", identifiant="P1"
        )
        response = self.client.get(f"/api/projets/{self.projet.id}/generer-dqe/")
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

class TestDallesEtPostes(APITestCase):
    def setUp(self):
        self.user, self.entreprise = authentifier(self)
        self.projet = Projet.objects.create(nom="P", entreprise=self.entreprise)

    def test_dalle_deux_sens_bael(self):
        """Lx = 4 m, Ly = 5 m : alpha = 0,8 >= 0,4 -> deux sens -> h = Lx/35
        = 11,4 cm -> minimum constructif 12 cm. Surface = 20 m² (serveur)."""
        r = self.client.post("/api/elements/", {
            "projet": self.projet.id, "type_element": "dalle", "identifiant": "D1",
            "portee": 4.0, "longueur_m": 5.0,
        }, format="json")
        self.assertEqual(r.status_code, status.HTTP_201_CREATED, r.data)
        self.assertEqual(r.data["surface_m2"], 20.0)
        r = self.client.post(f"/api/elements/{r.data['id']}/calculer/")
        self.assertEqual(r.status_code, status.HTTP_200_OK, r.data)
        res = r.data["resultat_calcul"]
        self.assertTrue(res["portant_deux_sens"])
        self.assertEqual(res["alpha"], 0.8)
        self.assertEqual(res["epaisseur_cm"], 12)

    def test_dalle_un_sens(self):
        """Lx = 3, Ly = 9 : alpha = 0,33 < 0,4 -> un sens -> h = 3/25 = 12 cm."""
        r = self.client.post("/api/elements/", {
            "projet": self.projet.id, "type_element": "dalle", "identifiant": "D2",
            "portee": 3.0, "longueur_m": 9.0,
        }, format="json")
        res = self.client.post(f"/api/elements/{r.data['id']}/calculer/").data["resultat_calcul"]
        self.assertFalse(res["portant_deux_sens"])
        self.assertEqual(res["epaisseur_cm"], 12)

    def test_dalle_lx_superieur_ly_refuse(self):
        r = self.client.post("/api/elements/", {
            "projet": self.projet.id, "type_element": "dalle", "identifiant": "D3",
            "portee": 6.0, "longueur_m": 4.0,
        }, format="json")
        self.assertEqual(r.status_code, status.HTTP_400_BAD_REQUEST)

    def test_poste_simple_montant_serveur(self):
        r = self.client.post("/api/postes-complementaires/", {
            "projet": self.projet.id, "lot": "lot_04_plomberie", "mode": "simple",
            "designation": "Réseau EU", "unite": "ml", "quantite": 12.5, "prix_unitaire": 4000,
        }, format="json")
        self.assertEqual(r.status_code, status.HTTP_201_CREATED, r.data)
        self.assertEqual(r.data["montant"], 50000)

    def test_poste_simple_incomplet_refuse(self):
        r = self.client.post("/api/postes-complementaires/", {
            "projet": self.projet.id, "lot": "lot_04_plomberie", "mode": "simple", "designation": "X",
        }, format="json")
        self.assertEqual(r.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("quantite", r.data)

    def test_poste_ratio_geometrie_incomplete_refuse_a_la_saisie(self):
        r = self.client.post("/api/postes-complementaires/", {
            "projet": self.projet.id, "lot": "lot_02_gros_oeuvre_superstructure", "mode": "ratio",
            "type_poste": "chainage", "geometrie": {"perimetre_batiment_m": 40},
        }, format="json")
        self.assertEqual(r.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("longueur_chainage_m", str(r.data))

    def test_poste_ratio_valide_calcule_ses_lignes(self):
        r = self.client.post("/api/postes-complementaires/", {
            "projet": self.projet.id, "lot": "lot_02_gros_oeuvre_superstructure", "mode": "ratio",
            "type_poste": "acrotere", "geometrie": {"perimetre_acrotere_m": 40},
        }, format="json")
        self.assertEqual(r.status_code, status.HTTP_201_CREATED, r.data)
        # 40 m x 0,05 m² = 2 m³ de béton
        beton = next(l for l in r.data["lignes_calculees"] if l["unite"] == "m³")
        self.assertEqual(beton["quantite"], 2.0)

    def test_referentiel_expose_nomenclatures_du_moteur(self):
        r = self.client.get("/api/referentiel/")
        usages = {u["cle"]: u["charge_exploitation_kn_m2"] for u in r.data["usages"]}
        self.assertEqual(usages["commerce"], 5.0)
        self.assertNotIn("commercial", usages)
        types = {t["cle"] for t in r.data["types_postes_ratio"]}
        self.assertEqual(types, {"maconnerie", "enduit", "chainage", "raidisseur", "acrotere"})

    def test_trame_regeneree_conserve_les_dalles(self):
        self.projet.usage_batiment = "habitation"
        self.projet.nb_niveaux = 1
        self.projet.hauteur_etage = 3.0
        self.projet.nb_travees_x = self.projet.nb_travees_y = 1
        self.projet.portee_x = self.projet.portee_y = 4.0
        self.projet.save()
        ElementStructurel.objects.create(projet=self.projet, type_element="dalle", identifiant="D1")
        r = self.client.post(f"/api/projets/{self.projet.id}/generer_trame/")
        self.assertEqual(r.status_code, status.HTTP_201_CREATED, r.data)
        self.assertTrue(self.projet.elements.filter(identifiant="D1").exists())
        self.assertIn("hypotheses", r.data)


class TestTrameContrainteSol(APITestCase):
    def test_contrainte_sol_du_projet_transmise_aux_semelles(self):
        user, cabinet = authentifier(self)
        projet = Projet.objects.create(
            nom="Sol", entreprise=cabinet, usage_batiment="habitation", nb_niveaux=1, hauteur_etage=3.0,
            nb_travees_x=1, nb_travees_y=1, portee_x=4.0, portee_y=4.0, contrainte_sol_kn_m2=250,
        )
        r = self.client.post(f"/api/projets/{projet.id}/generer_trame/")
        self.assertEqual(r.status_code, status.HTTP_201_CREATED, r.data)
        semelle = projet.elements.filter(type_element="semelle").first()
        self.assertEqual(semelle.taux_travail_sol, 250)
        self.assertFalse(semelle.resultat_calcul["hypothese_sol"])
        # A² ≥ N / σ (côté arrondi à 5 cm) et pression réelle ≤ σ du projet
        self.assertGreaterEqual(semelle.resultat_calcul["surface_m2"], semelle.charge_calculee / 250)
        self.assertLessEqual(semelle.resultat_calcul["pression_sol_kn_m2"], 250)
        self.assertEqual(semelle.resultat_calcul["contrainte_sol_kn_m2"], 250)
        self.assertFalse(any(h.startswith("HYPOTHÈSE : contrainte admissible du sol") for h in r.data["hypotheses"]))
