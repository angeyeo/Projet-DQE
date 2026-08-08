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


class TestProjetAPI(APITestCase):
    def test_creer_projet(self):
        response = self.client.post(
            "/api/projets/",
            {"nom": "Immeuble test", "usage_batiment": "habitation", "nb_niveaux": 2},
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(Projet.objects.count(), 1)

    def test_lister_projets(self):
        Projet.objects.create(nom="A", usage_batiment="bureau", nb_niveaux=1)
        response = self.client.get("/api/projets/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 1)


class TestElementStructurelAPI(APITestCase):
    def setUp(self):
        self.projet = Projet.objects.create(
            nom="Immeuble test", usage_batiment="habitation", nb_niveaux=2
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

    def test_modifier_element_valide_repasse_a_modifie(self):
        """Verrou logiciel : modifier un élément validé le repasse à MODIFIE."""
        element = ElementStructurel.objects.create(
            projet=self.projet,
            type_element="poteau",
            identifiant="P1",
            resultat_calcul={"largeur_cm": 25},
            resultat_valide={"largeur_cm": 25},
            statut=ElementStructurel.Statut.VALIDE,
        )
        response = self.client.patch(
            f"/api/elements/{element.id}/", {"hauteur_poteau": 3.5}
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        element.refresh_from_db()
        self.assertEqual(element.statut, ElementStructurel.Statut.MODIFIE)

    def test_generer_dqe_refuse_si_elements_non_valides(self):
        ElementStructurel.objects.create(
            projet=self.projet, type_element="poteau", identifiant="P1"
        )
        response = self.client.get(f"/api/projets/{self.projet.id}/generer_dqe/")
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)