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

    @mock.patch("projets.services.assistant_ia.client.MockAIClient.appeler_llm")
    def test_parser_robustesse_markdown_et_texte(self, mock_appeler):
        # 1. {"usage":"COMMERCE"} -> accepté
        mock_appeler.return_value = '{"usage": "COMMERCE", "nombre_niveaux": 3, "configuration": "R+2", "portee_m": 5.0}'
        res = structurer_description_projet("test")
        self.assertEqual(res["donnees"]["usage"], "COMMERCE")

        # 2. ```json ... ``` -> accepté
        mock_appeler.return_value = '```json\n{"usage": "COMMERCE", "nombre_niveaux": 3, "configuration": "R+2", "portee_m": 5.0}\n```'
        res = structurer_description_projet("test")
        self.assertEqual(res["donnees"]["usage"], "COMMERCE")

        # 3. Voici le résultat : {"usage":"COMMERCE"} -> accepté
        mock_appeler.return_value = 'Voici le résultat : {"usage": "COMMERCE", "nombre_niveaux": 3, "configuration": "R+2", "portee_m": 5.0}'
        res = structurer_description_projet("test")
        self.assertEqual(res["donnees"]["usage"], "COMMERCE")

        # 4. texte avant + JSON + texte après -> accepté
        mock_appeler.return_value = 'Blabla {"usage": "COMMERCE", "nombre_niveaux": 3, "configuration": "R+2", "portee_m": 5.0} blabla'
        res = structurer_description_projet("test")
        self.assertEqual(res["donnees"]["usage"], "COMMERCE")

        # 5. aucune accolade -> rejet contrôlé
        mock_appeler.return_value = 'Pas de JSON ici'
        with self.assertRaises(ValueError):
            structurer_description_projet("test")

        # 6. JSON tronqué -> rejet contrôlé
        mock_appeler.return_value = '{"usage": "COMMERCE"'
        with self.assertRaises(ValueError):
            structurer_description_projet("test")

        # 7. [] au lieu de {} -> rejet contrôlé
        mock_appeler.return_value = '[1, 2, 3]'
        with self.assertRaises(ValueError):
            structurer_description_projet("test")

        # 8. deux objets JSON successifs -> rejet contrôlé
        mock_appeler.return_value = '{"usage": "COMMERCE"} {"usage": "HABITATION"}'
        with self.assertRaises(ValueError):
            structurer_description_projet("test")

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
        os.environ["DEMO_MODE"] = "False"
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


class SuggestionPosteUnitTestCase(TestCase):
    """Tests unitaires exhaustifs pour la suggestion de poste complémentaire (IA Jour 1)."""

    def setUp(self):
        os.environ["LLM_PROVIDER"] = "mock"
        if "LLM_API_KEY" in os.environ:
            del os.environ["LLM_API_KEY"]

    def test_suggestion_description_valide(self):
        from projets.services.assistant_ia.postes import suggerer_poste_complementaire
        res = suggerer_poste_complementaire("Maçonnerie en agglos pleins 20")
        suggestion = res["suggestion"]
        self.assertEqual(suggestion["lot_suggere"], "lot_02_gros_oeuvre_superstructure")
        self.assertEqual(suggestion["unite"], "m²")
        self.assertEqual(suggestion["confiance"], "haute")
        self.assertEqual(res["source"], "MOCK")

    def test_suggestion_description_vide_refusee(self):
        from projets.services.assistant_ia.postes import suggerer_poste_complementaire
        with self.assertRaises(ValueError):
            suggerer_poste_complementaire("")

    def test_suggestion_description_espaces_refusee(self):
        from projets.services.assistant_ia.postes import suggerer_poste_complementaire
        with self.assertRaises(ValueError):
            suggerer_poste_complementaire("     ")

    def test_suggestion_mauvais_type_refuse(self):
        from projets.services.assistant_ia.postes import suggerer_poste_complementaire
        with self.assertRaises(ValueError):
            suggerer_poste_complementaire(12345)
        with self.assertRaises(ValueError):
            suggerer_poste_complementaire(None)

    def test_suggestion_description_trop_longue_refusee(self):
        from projets.services.assistant_ia.postes import suggerer_poste_complementaire
        longue_desc = "A" * 501
        with self.assertRaises(ValueError):
            suggerer_poste_complementaire(longue_desc)

    def test_suggestion_designation_llm_vide_leve_erreur(self):
        from projets.services.assistant_ia.postes import suggerer_poste_complementaire
        fake_response = json.dumps({
            "designation": "",
            "unite": "m²",
            "lot_suggere": "lot_02_gros_oeuvre_superstructure",
            "confiance": "haute"
        })
        with mock.patch("projets.services.assistant_ia.postes.get_ai_client") as mock_get:
            mock_client = mock.MagicMock()
            mock_client.appeler_llm.return_value = fake_response
            mock_get.return_value = mock_client
            with self.assertRaises(ValueError):
                suggerer_poste_complementaire("Terrassement")

    def test_suggestion_unite_invalide_leve_erreur(self):
        from projets.services.assistant_ia.postes import suggerer_poste_complementaire
        fake_response = json.dumps({
            "designation": "Terrassement",
            "unite": "invalide_unit",
            "lot_suggere": "lot_01_terrassement",
            "confiance": "haute"
        })
        with mock.patch("projets.services.assistant_ia.postes.get_ai_client") as mock_get:
            mock_client = mock.MagicMock()
            mock_client.appeler_llm.return_value = fake_response
            mock_get.return_value = mock_client
            with self.assertRaises(ValueError):
                suggerer_poste_complementaire("Terrassement")

    def test_suggestion_lot_invalide_leve_erreur(self):
        from projets.services.assistant_ia.postes import suggerer_poste_complementaire
        fake_response = json.dumps({
            "designation": "Plomberie",
            "unite": "ens.",
            "lot_suggere": "lot_inexistant",
            "confiance": "haute"
        })
        with mock.patch("projets.services.assistant_ia.postes.get_ai_client") as mock_get:
            mock_client = mock.MagicMock()
            mock_client.appeler_llm.return_value = fake_response
            mock_get.return_value = mock_client
            with self.assertRaises(ValueError):
                suggerer_poste_complementaire("Plomberie")

    def test_suggestion_confiance_invalide_leve_erreur(self):
        from projets.services.assistant_ia.postes import suggerer_poste_complementaire
        fake_response = json.dumps({
            "designation": "Peinture",
            "unite": "m²",
            "lot_suggere": "lot_00_generalites",
            "confiance": "ultra_sure"
        })
        with mock.patch("projets.services.assistant_ia.postes.get_ai_client") as mock_get:
            mock_client = mock.MagicMock()
            mock_client.appeler_llm.return_value = fake_response
            mock_get.return_value = mock_client
            with self.assertRaises(ValueError):
                suggerer_poste_complementaire("Peinture")

    def test_prompt_utilise_les_valeurs_du_modele(self):
        """Vérifie que le prompt transmis au LLM contient l'intégralité des lots du modèle Django."""
        from projets.models import PosteComplementaire
        from projets.services.assistant_ia.postes import suggerer_poste_complementaire

        captured_prompts = []
        with mock.patch("projets.services.assistant_ia.postes.get_ai_client") as mock_get:
            mock_client = mock.MagicMock()
            def mock_appeler(prompt, forcer_json=False):
                captured_prompts.append(prompt)
                return json.dumps({
                    "designation": "Implantation",
                    "unite": "ens.",
                    "lot_suggere": "lot_00_generalites",
                    "confiance": "haute"
                })
            mock_client.appeler_llm.side_effect = mock_appeler
            mock_get.return_value = mock_client

            suggerer_poste_complementaire("Installation de chantier")

            self.assertEqual(len(captured_prompts), 1)
            prompt_used = captured_prompts[0]

            for lot in PosteComplementaire.Lot.values:
                self.assertIn(lot, prompt_used, f"Le lot '{lot}' du modèle Django est absent du prompt envoyé au LLM.")

    def test_suggestion_champs_mauvais_type_levent_erreur(self):
        """Vérifie qu'aucun champ non-string n'est accepté ni converti silencieusement par str()."""
        from projets.services.assistant_ia.postes import suggerer_poste_complementaire

        bad_type_payloads = [
            {"designation": 12345, "unite": "m²", "lot_suggere": "lot_01_terrassement", "confiance": "haute"},
            {"designation": True, "unite": "m²", "lot_suggere": "lot_01_terrassement", "confiance": "haute"},
            {"designation": None, "unite": "m²", "lot_suggere": "lot_01_terrassement", "confiance": "haute"},
            {"designation": "Fouille", "unite": True, "lot_suggere": "lot_01_terrassement", "confiance": "haute"},
            {"designation": "Fouille", "unite": 123, "lot_suggere": "lot_01_terrassement", "confiance": "haute"},
            {"designation": "Fouille", "unite": "m³", "lot_suggere": ["lot_01_terrassement"], "confiance": "haute"},
            {"designation": "Fouille", "unite": "m³", "lot_suggere": 99, "confiance": "haute"},
            {"designation": "Fouille", "unite": "m³", "lot_suggere": "lot_01_terrassement", "confiance": 1},
            {"designation": "Fouille", "unite": "m³", "lot_suggere": "lot_01_terrassement", "confiance": False},
        ]

        for payload in bad_type_payloads:
            with mock.patch("projets.services.assistant_ia.postes.get_ai_client") as mock_get:
                mock_client = mock.MagicMock()
                mock_client.appeler_llm.return_value = json.dumps(payload)
                mock_get.return_value = mock_client
                with self.assertRaises(ValueError, msg=f"Échec de rejet du mauvais type pour payload: {payload}"):
                    suggerer_poste_complementaire("Test types")

    def test_suggestion_cles_inconnues_ignorees(self):
        from projets.services.assistant_ia.postes import suggerer_poste_complementaire
        fake_response = json.dumps({
            "designation": "Fouille en rigole",
            "unite": "m³",
            "lot_suggere": "lot_01_terrassement",
            "confiance": "haute",
            "prix_estime": 50000,
            "quantite_estimee": 12.5,
            "commentaire_inutile": "Coucou"
        })
        with mock.patch("projets.services.assistant_ia.postes.get_ai_client") as mock_get:
            mock_client = mock.MagicMock()
            mock_client.appeler_llm.return_value = fake_response
            mock_get.return_value = mock_client
            res = suggerer_poste_complementaire("Fouilles")
            sug = res["suggestion"]
            self.assertNotIn("prix_estime", sug)
            self.assertNotIn("quantite_estimee", sug)
            self.assertNotIn("commentaire_inutile", sug)

    def test_suggestion_json_markdown(self):
        from projets.services.assistant_ia.postes import suggerer_poste_complementaire
        fake_response = "```json\n" + json.dumps({
            "designation": "Couverture tôle",
            "unite": "m²",
            "lot_suggere": "lot_08_couverture",
            "confiance": "haute"
        }) + "\n```"
        with mock.patch("projets.services.assistant_ia.postes.get_ai_client") as mock_get:
            mock_client = mock.MagicMock()
            mock_client.appeler_llm.return_value = fake_response
            mock_get.return_value = mock_client
            res = suggerer_poste_complementaire("Toiture tôle")
            self.assertEqual(res["suggestion"]["lot_suggere"], "lot_08_couverture")

    def test_suggestion_texte_avant_apres_json(self):
        from projets.services.assistant_ia.postes import suggerer_poste_complementaire
        fake_response = "Voici mon analyse :\n" + json.dumps({
            "designation": "Étanchéité",
            "unite": "m²",
            "lot_suggere": "lot_03_etancheite",
            "confiance": "haute"
        }) + "\nEn espérant avoir aidé !"
        with mock.patch("projets.services.assistant_ia.postes.get_ai_client") as mock_get:
            mock_client = mock.MagicMock()
            mock_client.appeler_llm.return_value = fake_response
            mock_get.return_value = mock_client
            res = suggerer_poste_complementaire("Étanchéité terrasse")
            self.assertEqual(res["suggestion"]["lot_suggere"], "lot_03_etancheite")

    def test_suggestion_json_tronque_leve_erreur(self):
        from projets.services.assistant_ia.postes import suggerer_poste_complementaire
        fake_response = '{"designation": "Projet", "unite": "m²"'
        with mock.patch("projets.services.assistant_ia.postes.get_ai_client") as mock_get:
            mock_client = mock.MagicMock()
            mock_client.appeler_llm.return_value = fake_response
            mock_get.return_value = mock_client
            with self.assertRaises(ValueError):
                suggerer_poste_complementaire("Test tronqué")

    def test_suggestion_erreur_fournisseur_llm(self):
        from projets.services.assistant_ia.postes import suggerer_poste_complementaire
        with mock.patch("projets.services.assistant_ia.postes.get_ai_client") as mock_get:
            mock_client = mock.MagicMock()
            mock_client.appeler_llm.side_effect = LLMServiceError("Timeout LLM", status_code=504)
            mock_get.return_value = mock_client
            with self.assertRaises(LLMServiceError):
                suggerer_poste_complementaire("Test erreur LLM")

    def test_suggestion_aucune_ecriture_db_ni_quantite_ni_prix(self):
        from projets.models import PosteComplementaire
        count_before = PosteComplementaire.objects.count()
        from projets.services.assistant_ia.postes import suggerer_poste_complementaire
        res = suggerer_poste_complementaire("Terrassement pour fondation")
        count_after = PosteComplementaire.objects.count()
        self.assertEqual(count_before, count_after)

        sug = res["suggestion"]
        self.assertNotIn("prix", sug)
        self.assertNotIn("prix_unitaire", sug)
        self.assertNotIn("quantite", sug)

    # --- Tests de sécurité anti-hallucination et termes interdits ---

    def test_suggestion_nombre_existant_accepte(self):
        """Un nombre présent dans la description d'entrée est accepté dans la designation."""
        from projets.services.assistant_ia.postes import suggerer_poste_complementaire
        fake_response = json.dumps({
            "designation": "Maçonnerie agglos pleins 20",
            "unite": "m²",
            "lot_suggere": "lot_02_gros_oeuvre_superstructure",
            "confiance": "haute"
        })
        with mock.patch("projets.services.assistant_ia.postes.get_ai_client") as mock_get:
            mock_client = mock.MagicMock()
            mock_client.appeler_llm.return_value = fake_response
            mock_get.return_value = mock_client
            res = suggerer_poste_complementaire("Maçonnerie agglos 20")
            self.assertIsNotNone(res["suggestion"])
            self.assertIn(res["source"], ("MOCK", "GEMINI"))

    def test_suggestion_nombre_invente_declenche_fallback(self):
        """Un nombre absent de la description d'entrée déclenche le fallback."""
        from projets.services.assistant_ia.postes import suggerer_poste_complementaire
        fake_response = json.dumps({
            "designation": "Installation de chantier 250 m²",
            "unite": "ens.",
            "lot_suggere": "lot_00_generalites",
            "confiance": "haute"
        })
        with mock.patch("projets.services.assistant_ia.postes.get_ai_client") as mock_get:
            mock_client = mock.MagicMock()
            mock_client.appeler_llm.return_value = fake_response
            mock_get.return_value = mock_client
            res = suggerer_poste_complementaire("Installation de chantier")
            self.assertIsNone(res["suggestion"])
            self.assertEqual(res["source"], "FALLBACK_LOCAL")
            self.assertTrue(res["validation_humaine_requise"])

    def _assert_terme_interdit_declenche_fallback(self, terme):
        """Helper : vérifie qu'un terme interdit dans la designation déclenche le fallback."""
        from projets.services.assistant_ia.postes import suggerer_poste_complementaire
        fake_response = json.dumps({
            "designation": f"Fondation {terme} pour bâtiment",
            "unite": "m³",
            "lot_suggere": "lot_01_terrassement",
            "confiance": "haute"
        })
        with mock.patch("projets.services.assistant_ia.postes.get_ai_client") as mock_get:
            mock_client = mock.MagicMock()
            mock_client.appeler_llm.return_value = fake_response
            mock_get.return_value = mock_client
            res = suggerer_poste_complementaire("Fondation pour bâtiment")
            self.assertIsNone(res["suggestion"],
                             f"Le terme interdit '{terme}' n'a pas déclenché le fallback.")
            self.assertEqual(res["source"], "FALLBACK_LOCAL")
            self.assertTrue(res["validation_humaine_requise"])

    def test_suggestion_terme_conforme_declenche_fallback(self):
        self._assert_terme_interdit_declenche_fallback("conforme")

    def test_suggestion_terme_valide_declenche_fallback(self):
        self._assert_terme_interdit_declenche_fallback("validé")

    def test_suggestion_terme_sur_declenche_fallback(self):
        self._assert_terme_interdit_declenche_fallback("sûr")

    def test_suggestion_terme_optimal_declenche_fallback(self):
        self._assert_terme_interdit_declenche_fallback("optimal")

    def test_suggestion_valide_validation_humaine_requise(self):
        """Toute suggestion valide contient validation_humaine_requise=True."""
        from projets.services.assistant_ia.postes import suggerer_poste_complementaire
        res = suggerer_poste_complementaire("Maçonnerie en agglos pleins 20")
        self.assertTrue(res["validation_humaine_requise"])
        self.assertIn("message_validation", res)
        self.assertIsInstance(res["message_validation"], str)
        self.assertGreater(len(res["message_validation"]), 0)

    def test_fallback_ne_divulgue_aucune_suggestion_metier(self):
        """En fallback, aucune donnée métier (lot, unité, prix, quantité) ne doit fuiter."""
        from projets.services.assistant_ia.postes import suggerer_poste_complementaire
        fake_response = json.dumps({
            "designation": "Installation de chantier 999 m²",
            "unite": "ens.",
            "lot_suggere": "lot_00_generalites",
            "confiance": "haute"
        })
        with mock.patch("projets.services.assistant_ia.postes.get_ai_client") as mock_get:
            mock_client = mock.MagicMock()
            mock_client.appeler_llm.return_value = fake_response
            mock_get.return_value = mock_client
            res = suggerer_poste_complementaire("Installation de chantier")
            self.assertIsNone(res["suggestion"])
            self.assertNotIn("lot_suggere", res)
            self.assertNotIn("unite", res)
            self.assertNotIn("prix", res)
            self.assertNotIn("prix_unitaire", res)
            self.assertNotIn("quantite", res)
            self.assertNotIn("designation", res)


class SuggestionPosteAPITestCase(APITestCase):
    """Tests d'API REST exhaustifs pour l'endpoint de suggestion de poste."""

    def setUp(self):
        os.environ["DEMO_MODE"] = "True"
        os.environ["LLM_PROVIDER"] = "mock"
        self.user = User.objects.create_user(username="testuser_ia", password="password123")

    def test_api_suggerer_poste_success(self):
        url = "/api/assistant/suggerer-poste/"
        payload = {"description": "Fouille en rigole pour fondation"}
        response = self.client.post(url, payload, format="json")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn("suggestion", response.data)
        self.assertIn("lot_suggere", response.data["suggestion"])

    def test_api_suggerer_poste_description_vide(self):
        url = "/api/assistant/suggerer-poste/"
        payload = {"description": ""}
        response = self.client.post(url, payload, format="json")
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_api_suggerer_poste_description_manquante(self):
        url = "/api/assistant/suggerer-poste/"
        payload = {}
        response = self.client.post(url, payload, format="json")
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_api_suggerer_poste_demo_mode_false_sans_auth_refuse(self):
        os.environ["DEMO_MODE"] = "False"
        url = "/api/assistant/suggerer-poste/"
        payload = {"description": "Fouilles"}
        response = self.client.post(url, payload, format="json")
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_api_suggerer_poste_demo_mode_false_avec_auth_autorise(self):
        os.environ["DEMO_MODE"] = "False"
        self.client.force_authenticate(user=self.user)
        url = "/api/assistant/suggerer-poste/"
        payload = {"description": "Fouilles"}
        response = self.client.post(url, payload, format="json")
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_api_suggerer_poste_throttling(self):
        from django.core.cache import cache
        cache.clear()
        url = "/api/assistant/suggerer-poste/"
        payload = {"description": "Fouille en rigole"}
        status_codes = [self.client.post(url, payload, format="json").status_code for _ in range(17)]
        self.assertIn(status.HTTP_429_TOO_MANY_REQUESTS, status_codes)