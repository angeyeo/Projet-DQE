import os
from unittest import mock

from django.core.cache import cache
from rest_framework import status
from rest_framework.exceptions import Throttled
from rest_framework.request import Request
from rest_framework.test import APIClient, APIRequestFactory, APITestCase

from api.errors import api_exception_handler
from projets.models import Projet
from projets.services.assistant_ia.client import LLMServiceError
from projets.tests_projets.utils import authentifier, creer_cabinet, creer_membre


class EnveloppeErreursAPITests(APITestCase):
    def setUp(self):
        self.user, self.entreprise = authentifier(self, nom_cabinet="Erreurs API")
        self.projet = Projet.objects.create(nom="Projet erreur", entreprise=self.entreprise)

    def test_validation_drF_garde_les_cles_anciennes_et_ajoute_error(self):
        response = self.client.post(
            "/api/v1/projets/", {"nom": "Niveaux invalides", "nb_niveaux": 21}, format="json",
        )
        body = response.json()
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("nb_niveaux", body)
        self.assertEqual(body["error"]["code"], "VALIDATION_ERROR")
        self.assertIn("nb_niveaux", body["error"]["fields"])

    def test_erreur_metier_conserve_champs_manquants_dans_details_et_a_la_racine(self):
        response = self.client.get(f"/api/v1/projets/{self.projet.pk}/chainage_suggere/")
        body = response.json()
        self.assertEqual(response.status_code, 400)
        self.assertEqual(body["champs_manquants"], body["error"]["details"]["champs_manquants"])
        self.assertIn("portee_x", [item["champ"] for item in body["error"]["details"]["champs_manquants"]])

    def test_401_404_405_sont_enveloppes_sans_changer_les_statuts(self):
        anonymous = APIClient().get("/api/v1/projets/")
        self.assertEqual(anonymous.status_code, 401)
        self.assertEqual(anonymous.json()["error"]["code"], "AUTHENTICATION_REQUIRED")

        externe = creer_membre(creer_cabinet("Autre cabinet erreurs"), "autre_erreurs")
        client = APIClient()
        client.force_authenticate(user=externe)
        introuvable = client.get(f"/api/v1/projets/{self.projet.pk}/")
        self.assertEqual(introuvable.status_code, 404)
        self.assertEqual(introuvable.json()["error"]["code"], "NOT_FOUND")

        client.force_authenticate(user=self.user)
        methode = client.get(f"/api/v1/projets/{self.projet.pk}/analyser_plan_image/")
        self.assertEqual(methode.status_code, 405)
        self.assertEqual(methode.json()["error"]["code"], "METHOD_NOT_ALLOWED")

    def test_t12_428_et_403_gardent_les_codes_et_ne_appellent_pas_le_service(self):
        client = APIClient()
        client.force_authenticate(user=self.user)
        with mock.patch.dict(os.environ, {"LLM_PROVIDER": "gemini"}), mock.patch(
            "projets.views.structurer_description_projet"
        ) as service:
            requis = client.post(
                "/api/v1/assistant/structurer-projet/", {"description": "Projet fictif"}, format="json",
            )
            self.assertEqual(requis.status_code, 428)
            self.assertEqual(requis.json()["code"], "AI_CONSENT_REQUIRED")
            self.assertEqual(requis.json()["error"]["code"], "AI_CONSENT_REQUIRED")

            client.post("/api/v1/auth/moi/consentement-ia/", {"decision": "refuse"}, format="json")
            refuse = client.post(
                "/api/v1/assistant/structurer-projet/", {"description": "Projet fictif"}, format="json",
            )
            self.assertEqual(refuse.status_code, 403)
            self.assertEqual(refuse.json()["code"], "AI_CONSENT_REFUSED")
            self.assertEqual(refuse.json()["error"]["code"], "AI_CONSENT_REFUSED")
            service.assert_not_called()

    def test_429_exception_handler_emet_le_format_commun(self):
        request = Request(APIRequestFactory().get("/api/v1/assistant/structurer-projet/"))
        response = api_exception_handler(Throttled(wait=4), {"request": request})
        self.assertEqual(response.status_code, 429)
        self.assertEqual(response.data["error"]["code"], "RATE_LIMITED")
        self.assertEqual(response.data["detail"], response.data["error"]["message"])

    def test_throttling_reel_429_est_normalise_et_garde_son_statut(self):
        cache.clear()
        url = f"/api/v1/projets/{self.projet.pk}/analyser_plan_image/"
        for _ in range(5):
            response = self.client.post(url, {}, format="multipart")
            self.assertEqual(response.status_code, 400)
        response = self.client.post(url, {}, format="multipart")
        self.assertEqual(response.status_code, 429)
        self.assertEqual(response.json()["error"]["code"], "RATE_LIMITED")

    def test_502_ne_revele_pas_le_texte_interne_de_l_exception(self):
        client = APIClient()
        client.force_authenticate(user=self.user)
        client.post("/api/v1/auth/moi/consentement-ia/", {"decision": "accepte"}, format="json")
        secret_interne_factice = "internal endpoint key=do-not-show"
        with mock.patch.dict(os.environ, {"LLM_PROVIDER": "gemini"}), mock.patch(
            "projets.views.structurer_description_projet",
            side_effect=LLMServiceError(secret_interne_factice, code="UPSTREAM_FAILURE", status_code=502),
        ):
            response = client.post(
                "/api/v1/assistant/structurer-projet/", {"description": "Projet fictif"}, format="json",
            )
        body = response.json()
        self.assertEqual(response.status_code, 502)
        self.assertEqual(body["detail"], body["error"]["message"])
        self.assertNotIn(secret_interne_factice, str(body))
        self.assertEqual(body["error"]["code"], "UPSTREAM_FAILURE")

    def test_exception_interne_inattendue_devient_500_json_sans_detail(self):
        client = APIClient()
        client.force_authenticate(user=self.user)
        exception_interne = "traceback /srv/private/api_key=not-for-client"
        with mock.patch("projets.views.ReferentielView.get", side_effect=RuntimeError(exception_interne)):
            response = client.get("/api/v1/referentiel/")
        body = response.json()
        self.assertEqual(response.status_code, 500)
        self.assertEqual(body["error"]["code"], "INTERNAL_SERVER_ERROR")
        self.assertNotIn(exception_interne, str(body))
        self.assertEqual(body["detail"], body["error"]["message"])
