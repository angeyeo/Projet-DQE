import os
import json
from unittest import mock
import urllib.error
from django.test import TestCase
from django.contrib.auth import get_user_model
from rest_framework import status
from rest_framework.test import APITestCase

from projets.models import Projet, ElementStructurel
from projets.services.assistant_ia.client import (
    get_ai_client,
    MockAIClient,
    GeminiAIClient,
    LLMServiceError
)
from projets.services.assistant_ia.parser import structurer_description_projet
from projets.services.assistant_ia.explanations import expliquer_resultat_element, extraire_nombres
from projets.services.assistant_ia.schemas import valider_donnees_extraites, niveaux_depuis_configuration

User = get_user_model()


class AssistantIAUnitTestCase(TestCase):
    def setUp(self):
        os.environ["LLM_PROVIDER"] = "mock"
        if "LLM_API_KEY" in os.environ:
            del os.environ["LLM_API_KEY"]

    def test_mock_client_instantiation(self):
        client = get_ai_client()
        self.assertIsInstance(client, MockAIClient)

    def test_saisie_extraction_complete_r2_commerce(self):
        desc = "Je veux construire un bâtiment R+2 à usage commercial avec des portées de 6 mètres."
        res = structurer_description_projet(desc)

        self.assertEqual(res["donnees"]["nombre_niveaux"], 3)
        self.assertEqual(res["donnees"]["configuration"], "R+2")
        self.assertEqual(res["donnees"]["usage"], "COMMERCE")
        self.assertEqual(res["donnees"]["portee_m"], 6.0)
        self.assertEqual(res["donnees_manquantes"], [])
        self.assertIn("La contrainte admissible du sol doit être confirmée", res["avertissements"][0])

    def test_saisie_champs_manquants(self):
        desc = "Un bâtiment résidentiel sans précision."
        res = structurer_description_projet(desc)

        self.assertEqual(res["donnees"]["usage"], "HABITATION")
        self.assertIn("portee_m", res["donnees_manquantes"])
        self.assertTrue(res["confirmation_requise"])

    def test_saisie_refuse_texte_vide(self):
        with self.assertRaises(ValueError):
            structurer_description_projet("")
        with self.assertRaises(ValueError):
            structurer_description_projet("   ")

    def test_validation_niveaux_configuration_coherence(self):
        self.assertEqual(niveaux_depuis_configuration("R+2"), 3)
        self.assertEqual(niveaux_depuis_configuration("RDC"), 1)

        # Incohérence R+2 (3 niveaux) vs 6 niveaux -> ValueError
        data_incoherente = {
            "configuration": "R+2",
            "nombre_niveaux": 6
        }
        with self.assertRaises(ValueError):
            valider_donnees_extraites(data_incoherente)

    def test_validation_portee_bool_nan_inf_rejet(self):
        with self.assertRaises(ValueError):
            valider_donnees_extraites({"nombre_niveaux": 3, "portee_m": False})
        with self.assertRaises(ValueError):
            valider_donnees_extraites({"nombre_niveaux": 3, "portee_m": float("nan")})
        with self.assertRaises(ValueError):
            valider_donnees_extraites({"nombre_niveaux": 3, "portee_m": float("inf")})

    def test_gemini_client_header_et_sans_cle_dans_url(self):
        g_client = GeminiAIClient(api_key="SECRET_TEST_KEY_456")
        mock_resp = mock.MagicMock()
        mock_resp.read.return_value = json.dumps({"candidates": [{"content": {"parts": [{"text": "OK"}]}}]}).encode('utf-8')
        mock_resp.__enter__.return_value = mock_resp
        mock_resp.__exit__.return_value = None

        with mock.patch("urllib.request.urlopen", return_value=mock_resp) as spy_urlopen:
            res = g_client.appeler_llm("Test prompt")
            self.assertEqual(res, "OK")
            req = spy_urlopen.call_args[0][0]
            # Vérification : l'URL ne doit PAS contenir la clé
            self.assertNotIn("SECRET_TEST_KEY_456", req.full_url)
            # L'en-tête x-goog-api-key doit contenir la clé
            self.assertEqual(req.headers.get("X-goog-api-key"), "SECRET_TEST_KEY_456")

    def test_gemini_client_reponse_trop_volumineuse_rejetee(self):
        g_client = GeminiAIClient(api_key="TEST_KEY")
        # Simuler une réponse de 100 Ko (> LLM_MAX_RESPONSE_BYTES=65536)
        oversized = json.dumps({"candidates": [{"content": {"parts": [{"text": "A" * 70000}]}}]}).encode('utf-8')
        mock_resp = mock.MagicMock()
        mock_resp.read.return_value = oversized
        mock_resp.__enter__.return_value = mock_resp
        mock_resp.__exit__.return_value = None

        with mock.patch("urllib.request.urlopen", return_value=mock_resp):
            with self.assertRaises(LLMServiceError) as ctx:
                g_client.appeler_llm("Test oversize")
            self.assertEqual(ctx.exception.code, "LLM_RESPONSE_TOO_LARGE")
            self.assertEqual(ctx.exception.status_code, 502)

    def test_explication_post_validation_anti_hallucination(self):
        elem_data = {
            "repere": "P1",
            "type_element": "POTEAU",
            "parametres": {"hauteur_poteau": 3.0},
            "resultats": {"cote_cm": 30.0}
        }
        hallucinated_text = "Le poteau P1 de 30 cm reprend une charge de 450 kN."
        with mock.patch.object(MockAIClient, "appeler_llm", return_value=hallucinated_text):
            res = expliquer_resultat_element(elem_data)
            self.assertEqual(res["source"], "FALLBACK_LOCAL")
            self.assertFalse(res["explication_technique_disponible"])
            self.assertIn("pas pu être validée", res["explication"])


class AssistantIAAPITestCase(APITestCase):
    def setUp(self):
        os.environ["LLM_PROVIDER"] = "mock"
        self.user = User.objects.create_user(username="testuser", password="password123")
        self.client.force_authenticate(user=self.user)

        self.projet = Projet.objects.create(
            nom="Projet IA Test",
            usage_batiment="habitation",
            nb_niveaux=2
        )
        self.poteau = ElementStructurel.objects.create(
            projet=self.projet,
            type_element=ElementStructurel.TypeElement.POTEAU,
            identifiant="P1",
            hauteur_poteau=3.0,
            charge_calculee=450.0,
            resultat_calcul={"cote_cm": 30, "section_cm2": 900},
            statut=ElementStructurel.Statut.PROPOSE
        )

    def test_api_acces_anonyme_refuse(self):
        self.client.logout()
        resp1 = self.client.post("/api/assistant/structurer-projet/", {"description": "Test"}, format="json")
        resp2 = self.client.post("/api/assistant/expliquer-element/", {"element_id": self.poteau.id}, format="json")
        self.assertIn(resp1.status_code, [status.HTTP_401_UNAUTHORIZED, status.HTTP_403_FORBIDDEN])
        self.assertIn(resp2.status_code, [status.HTTP_401_UNAUTHORIZED, status.HTTP_403_FORBIDDEN])

    def test_api_structurer_projet_success(self):
        url = "/api/assistant/structurer-projet/"
        payload = {"description": "Bâtiment R+2 commercial avec des portées de 6 mètres."}
        response = self.client.post(url, payload, format="json")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["donnees"]["nombre_niveaux"], 3)
        self.assertEqual(response.data["donnees"]["usage"], "COMMERCE")
        self.assertTrue(response.data["confirmation_requise"])

    def test_api_structurer_description_trop_longue_echoue(self):
        url = "/api/assistant/structurer-projet/"
        payload = {"description": "a" * 1005}
        response = self.client.post(url, payload, format="json")
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_api_expliquer_element_success(self):
        url = "/api/assistant/expliquer-element/"
        payload = {"element_id": self.poteau.id}
        response = self.client.post(url, payload, format="json")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn("explication", response.data)
        self.assertEqual(response.data["source"], "MOCK")
        self.assertTrue(response.data["explication_technique_disponible"])
        self.assertTrue(response.data["validation_humaine_requise"])

    def test_api_mapping_erreurs_llm_status_codes(self):
        url = "/api/assistant/structurer-projet/"
        payload = {"description": "Description valide"}

        # Timeout -> HTTP 504
        with mock.patch("projets.views.structurer_description_projet", side_effect=LLMServiceError("Timeout", code="LLM_TIMEOUT", status_code=504)):
            resp = self.client.post(url, payload, format="json")
            self.assertEqual(resp.status_code, status.HTTP_504_GATEWAY_TIMEOUT)
            self.assertEqual(resp.data["code"], "LLM_TIMEOUT")

        # Quota Exceeded -> HTTP 503
        with mock.patch("projets.views.structurer_description_projet", side_effect=LLMServiceError("Quota", code="LLM_QUOTA_EXCEEDED", status_code=503)):
            resp = self.client.post(url, payload, format="json")
            self.assertEqual(resp.status_code, status.HTTP_503_SERVICE_UNAVAILABLE)
            self.assertEqual(resp.data["code"], "LLM_QUOTA_EXCEEDED")

    def test_api_throttling_assistant_structurer(self):
        from django.core.cache import cache
        cache.clear()
        url = "/api/assistant/structurer-projet/"
        payload = {"description": "Bâtiment test throttling"}
        status_codes = [self.client.post(url, payload, format="json").status_code for _ in range(12)]
        self.assertIn(status.HTTP_429_TOO_MANY_REQUESTS, status_codes)

    def test_api_throttling_assistant_expliquer(self):
        from django.core.cache import cache
        cache.clear()
        url = "/api/assistant/expliquer-element/"
        payload = {"element_id": self.poteau.id}
        status_codes = [self.client.post(url, payload, format="json").status_code for _ in range(22)]
        self.assertIn(status.HTTP_429_TOO_MANY_REQUESTS, status_codes)

    def test_explication_post_validation_termes_interdits(self):
        from projets.services.assistant_ia.explanations import expliquer_resultat_element
        elem = {
            "repere": "P1",
            "type_element": "POTEAU",
            "parametres": {"hauteur_poteau": 3.0},
            "resultats": {"cote_cm": 30.0}
        }
        with mock.patch("projets.services.assistant_ia.explanations.get_ai_client") as mock_get:
            mock_client = mock.MagicMock()
            mock_client.appeler_llm.return_value = "La section est conforme et validée par le calcul."
            mock_get.return_value = mock_client
            exp = expliquer_resultat_element(elem)
            self.assertEqual(exp["source"], "FALLBACK_LOCAL")
            self.assertFalse(exp["explication_technique_disponible"])
