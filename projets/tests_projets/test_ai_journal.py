import os
from unittest import mock
from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from rest_framework import status
from rest_framework.test import APIClient

from projets.models import JournalAppelIA, ElementStructurel, Projet
from projets.services.assistant_ia.journalisation import enregistrer_appel_ia
from projets.services.assistant_ia.client import LLMServiceError

User = get_user_model()


class AIJournalTestCase(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.user = User.objects.create_user(
            username="testuser",
            email="test@example.com",
            password="password123",
        )
        self.projet = Projet.objects.create(nom="Projet Test Journal")
        self.poteau = ElementStructurel.objects.create(
            projet=self.projet,
            identifiant="P1",
            type_element=ElementStructurel.TypeElement.POTEAU,
            resultat_calcul={"section_acier_cm2": 4.5},
            resultat_valide={"section_acier_cm2": 4.5},
            statut=ElementStructurel.Statut.VALIDE,
        )
        # S'assurer que le provider d'IA est 'mock' par défaut pendant les tests
        self.env_patcher = mock.patch.dict(os.environ, {"LLM_PROVIDER": "mock", "DEMO_MODE": "True"})
        self.env_patcher.start()

    def tearDown(self):
        self.env_patcher.stop()

    def test_enregistrer_appel_ia_succes(self):
        """Vérifie l'enregistrement direct d'un log d'appel IA."""
        journal = enregistrer_appel_ia(
            endpoint="/api/assistant/structurer-projet/",
            source="MOCK",
            utilisateur=self.user,
            duree_ms=120,
        )
        self.assertIsNotNone(journal)
        self.assertEqual(journal.endpoint, "/api/assistant/structurer-projet/")
        self.assertEqual(journal.source, "MOCK")
        self.assertEqual(journal.utilisateur, self.user)
        self.assertEqual(journal.duree_ms, 120)
        self.assertEqual(JournalAppelIA.objects.count(), 1)

    def test_enregistrer_appel_ia_anonyme(self):
        """Vérifie qu'un utilisateur anonyme ne fait pas crasher la journalisation."""
        journal = enregistrer_appel_ia(
            endpoint="/api/assistant/structurer-projet/",
            source="GEMINI",
            utilisateur=None,
            duree_ms=45,
        )
        self.assertIsNotNone(journal)
        self.assertIsNone(journal.utilisateur)
        self.assertEqual(journal.source, "GEMINI")
        self.assertEqual(JournalAppelIA.objects.count(), 1)

    def test_enregistrer_appel_ia_defensif_sur_erreur(self):
        """Vérifie qu'une erreur de DB dans le logger est étanche et renvoie None sans lever d'exception."""
        with mock.patch("projets.models.JournalAppelIA.objects.create", side_effect=Exception("Database crash")):
            res = enregistrer_appel_ia(
                endpoint="/api/assistant/structurer-projet/",
                source="MOCK",
                utilisateur=self.user,
            )
            self.assertIsNone(res)

    def test_journal_source_mock_api(self):
        """Vérifie que l'appel API en mode MOCK enregistre source = MOCK."""
        JournalAppelIA.objects.all().delete()
        response = self.client.post(
            "/api/assistant/structurer-projet/",
            {"description": "Bâtiment R+2 à usage de bureau avec portée de 4m"},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(JournalAppelIA.objects.count(), 1)
        entry = JournalAppelIA.objects.first()
        self.assertEqual(entry.endpoint, "/api/assistant/structurer-projet/")
        self.assertEqual(entry.source, "MOCK")

    def test_journal_source_gemini_api(self):
        """Vérifie qu'un client Gemini réel enregistre la source GEMINI."""
        JournalAppelIA.objects.all().delete()
        from projets.services.assistant_ia.client import GeminiAIClient

        gemini_mock_client = GeminiAIClient(api_key="fake-key")
        with mock.patch("projets.services.assistant_ia.parser.get_ai_client", return_value=gemini_mock_client):
            with mock.patch.object(
                gemini_mock_client,
                "appeler_llm",
                return_value='{"nombre_niveaux": 3, "configuration": "R+2", "usage": "BUREAU", "portee_m": 4.0, "hauteur_niveau_m": 3.0, "contrainte_sol_kn_m2": 200, "donnees_manquantes": [], "avertissements": []}',
            ):
                response = self.client.post(
                    "/api/assistant/structurer-projet/",
                    {"description": "Bâtiment R+2 bureau 4m sol 200"},
                    format="json",
                )
                self.assertEqual(response.status_code, status.HTTP_200_OK)
                self.assertEqual(JournalAppelIA.objects.count(), 1)
                entry = JournalAppelIA.objects.first()
                self.assertEqual(entry.source, "GEMINI")

    def test_journal_source_fallback_local_sur_erreur_llm(self):
        """Vérifie qu'une erreur LLM loggue source = FALLBACK_LOCAL."""
        JournalAppelIA.objects.all().delete()
        err = LLMServiceError("Service LLM en défaillance", code="LLM_PROVIDER_ERROR", status_code=502)
        with mock.patch(
            "projets.views.structurer_description_projet",
            side_effect=err,
        ):
            response = self.client.post(
                "/api/assistant/structurer-projet/",
                {"description": "Description valide"},
                format="json",
            )
            self.assertEqual(response.status_code, status.HTTP_502_BAD_GATEWAY)
            self.assertEqual(JournalAppelIA.objects.count(), 1)
            entry = JournalAppelIA.objects.first()
            self.assertEqual(entry.source, "FALLBACK_LOCAL")

    def test_journal_utilisateur_authentifie(self):
        """Vérifie qu'un utilisateur connecté est rattaché au log."""
        JournalAppelIA.objects.all().delete()
        self.client.force_authenticate(user=self.user)
        response = self.client.post(
            "/api/assistant/suggerer-poste/",
            {"description": "Béton de propreté dosé à 150 kg/m3"},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(JournalAppelIA.objects.count(), 1)
        entry = JournalAppelIA.objects.first()
        self.assertEqual(entry.utilisateur, self.user)
        self.assertEqual(entry.endpoint, "/api/assistant/suggerer-poste/")

    def test_logging_failure_does_not_break_api(self):
        """Vérifie qu'un échec interne de la BD lors de la création du log n'empêche pas l’API de répondre."""
        with mock.patch(
            "projets.models.JournalAppelIA.objects.create",
            side_effect=Exception("Logging crash inattendu"),
        ):
            response = self.client.post(
                "/api/assistant/suggerer-poste/",
                {"description": "Fouille en rigole"},
                format="json",
            )
            self.assertEqual(response.status_code, status.HTTP_200_OK)
            self.assertIn("suggestion", response.data)

    def test_pas_de_doublons_involontaires(self):
        """Vérifie qu'un seul enregistrement est créé par requête API."""
        JournalAppelIA.objects.all().delete()
        self.client.post(
            f"/api/elements/{self.poteau.id}/expliquer-coherence/",
            format="json",
        )
        self.assertEqual(JournalAppelIA.objects.count(), 1)
