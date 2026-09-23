import os
from unittest.mock import MagicMock, patch
from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.test import override_settings
from rest_framework import status
from rest_framework.test import APITestCase

from projets.models import Projet, ElementStructurel
from projets.services.assistant_ia.client import MockAIClient

User = get_user_model()


class TestAICoherenceAPI(APITestCase):
    """Suite de tests d'intégration API pour le module de cohérence IA."""

    @classmethod
    def setUpTestData(cls):
        cls.user = User.objects.create_user(
            username="testuser_coherence", password="password123"
        )

    def setUp(self):
        cache.clear()
        self.projet = Projet.objects.create(nom="Projet Cohérence API")

    def _creer_element(self, type_element="semelle_filante", statut="valide", **kwargs):
        return ElementStructurel.objects.create(
            projet=self.projet,
            identifiant=kwargs.pop("identifiant", f"EL_{type_element}"),
            type_element=type_element,
            statut=statut,
            **kwargs,
        )

    # 1. GET projet existant → 200 OK
    def test_01_get_projet_coherence_200(self):
        self._creer_element("semelle_filante", resultat_valide={"condition_respectee": False})
        url = f"/api/projets/{self.projet.id}/analyse-coherence/"

        with patch.dict(os.environ, {"DEMO_MODE": "True"}):
            response = self.client.get(url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["projet_id"], self.projet.id)
        self.assertEqual(response.data["nom_projet"], "Projet Cohérence API")
        self.assertEqual(response.data["resume"]["total_elements"], 1)
        self.assertEqual(response.data["resume"]["critiques"], 1)

    # 2. GET projet inexistant → 404
    def test_02_get_projet_inexistant_404(self):
        url = "/api/projets/99999/analyse-coherence/"

        with patch.dict(os.environ, {"DEMO_MODE": "True"}):
            response = self.client.get(url)

        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    # 3. Résumé correctement retourné
    def test_03_resume_structure_coherente(self):
        self._creer_element("semelle_filante", identifiant="SF1", resultat_valide={"condition_respectee": False})
        self._creer_element("semelle", identifiant="S1", resultat_valide={"hypothese_sol": True})
        self._creer_element("poutre", identifiant="P1", resultat_valide={"non_fragilite_respectee": False})
        self._creer_element("dalle", identifiant="D1", resultat_valide={"longueur_m": 4.0})

        url = f"/api/projets/{self.projet.id}/analyse-coherence/"
        with patch.dict(os.environ, {"DEMO_MODE": "True"}):
            response = self.client.get(url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        resume = response.data["resume"]
        self.assertEqual(resume["total_elements"], 4)
        self.assertEqual(resume["critiques"], 1)
        self.assertEqual(resume["attentions"], 1)
        self.assertEqual(resume["informations"], 1)
        self.assertEqual(resume["aucun_signal"], 1)

    # 4. Aucun appel LLM pendant GET projet
    def test_04_get_projet_aucun_llm_appele(self):
        self._creer_element("semelle_filante", resultat_valide={"condition_respectee": False})
        url = f"/api/projets/{self.projet.id}/analyse-coherence/"

        with patch("projets.services.assistant_ia.coherence_explanations.get_ai_client") as mock_get_client:
            with patch.dict(os.environ, {"DEMO_MODE": "True"}):
                response = self.client.get(url)

            self.assertEqual(response.status_code, status.HTTP_200_OK)
            mock_get_client.assert_not_called()

    # 5. Aucune mutation DB pendant GET projet
    def test_05_get_projet_aucune_mutation_db(self):
        self._creer_element("semelle_filante", resultat_valide={"condition_respectee": False})
        url = f"/api/projets/{self.projet.id}/analyse-coherence/"

        elements_avant = list(ElementStructurel.objects.values())
        with patch.dict(os.environ, {"DEMO_MODE": "True"}):
            response = self.client.get(url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        elements_apres = list(ElementStructurel.objects.values())
        self.assertEqual(elements_avant, elements_apres)

    # 6. POST expliquer cohérence sur élément CRITIQUE → 200
    def test_06_post_expliquer_element_critique_200(self):
        el = self._creer_element("semelle_filante", resultat_valide={"condition_respectee": False})
        url = f"/api/elements/{el.id}/expliquer-coherence/"

        with patch.dict(os.environ, {"DEMO_MODE": "True", "LLM_PROVIDER": "mock"}):
            response = self.client.post(url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["statut_analyse"], "CRITIQUE")
        self.assertIsNotNone(response.data["explication_ia"])
        self.assertTrue(response.data["validation_humaine_requise"])

    # 7. Réponse MOCK → source_explication = MOCK
    def test_07_source_explication_mock(self):
        el = self._creer_element("semelle_filante", resultat_valide={"condition_respectee": False})
        url = f"/api/elements/{el.id}/expliquer-coherence/"

        with patch.dict(os.environ, {"DEMO_MODE": "True", "LLM_PROVIDER": "mock"}):
            response = self.client.post(url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["source_explication"], "MOCK")

    # 8. Panne LLM → HTTP 200, source_explication = LOCAL, signaux conservés
    def test_08_panne_llm_fallback_local(self):
        el = self._creer_element("semelle_filante", resultat_valide={"condition_respectee": False})
        url = f"/api/elements/{el.id}/expliquer-coherence/"

        mock_failing = MagicMock()
        mock_failing.appeler_llm.side_effect = RuntimeError("Crash service LLM")

        with patch("projets.services.assistant_ia.coherence_explanations.get_ai_client", return_value=mock_failing):
            with patch.dict(os.environ, {"DEMO_MODE": "True"}):
                response = self.client.post(url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["source_explication"], "LOCAL")
        self.assertIsNone(response.data["explication_ia"])
        self.assertEqual(response.data["statut_analyse"], "CRITIQUE")
        self.assertEqual(len(response.data["signaux"]), 1)

    # 9. CALCUL_A_VALIDER → HTTP 200, aucun LLM
    def test_09_calcul_a_valider_aucun_llm(self):
        el = self._creer_element("poteau", statut="propose", resultat_calcul={"section_acier_retenue_cm2": 5.0})
        url = f"/api/elements/{el.id}/expliquer-coherence/"

        with patch("projets.services.assistant_ia.coherence_explanations.get_ai_client") as mock_get_client:
            with patch.dict(os.environ, {"DEMO_MODE": "True"}):
                response = self.client.post(url)

            self.assertEqual(response.status_code, status.HTTP_200_OK)
            self.assertEqual(response.data["statut_analyse"], "CALCUL_A_VALIDER")
            self.assertEqual(response.data["source_explication"], "LOCAL")
            self.assertIsNone(response.data["explication_ia"])
            mock_get_client.assert_not_called()

    # 10. CALCUL_A_REFAIRE → aucun LLM
    def test_10_calcul_a_refaire_aucun_llm(self):
        el = self._creer_element(
            "poteau",
            statut="modifie",
            resultat_calcul={"section_acier_retenue_cm2": 5.0},
            resultat_valide={"section_acier_retenue_cm2": 4.0},
        )
        url = f"/api/elements/{el.id}/expliquer-coherence/"

        with patch("projets.services.assistant_ia.coherence_explanations.get_ai_client") as mock_get_client:
            with patch.dict(os.environ, {"DEMO_MODE": "True"}):
                response = self.client.post(url)

            self.assertEqual(response.status_code, status.HTTP_200_OK)
            self.assertEqual(response.data["statut_analyse"], "CALCUL_A_REFAIRE")
            self.assertEqual(response.data["source_explication"], "LOCAL")
            mock_get_client.assert_not_called()

    # 11. CALCUL_NON_DISPONIBLE → aucun LLM
    def test_11_calcul_non_disponible_aucun_llm(self):
        el = self._creer_element("poteau", statut="propose", resultat_calcul=None)
        url = f"/api/elements/{el.id}/expliquer-coherence/"

        with patch("projets.services.assistant_ia.coherence_explanations.get_ai_client") as mock_get_client:
            with patch.dict(os.environ, {"DEMO_MODE": "True"}):
                response = self.client.post(url)

            self.assertEqual(response.status_code, status.HTTP_200_OK)
            self.assertEqual(response.data["statut_analyse"], "CALCUL_NON_DISPONIBLE")
            self.assertEqual(response.data["source_explication"], "LOCAL")
            mock_get_client.assert_not_called()

    # 12. Sécurité DEMO_MODE=True → anonyme autorisé
    def test_12_securite_demo_mode_true_anonyme_autorise(self):
        el = self._creer_element("semelle_filante", resultat_valide={"condition_respectee": False})
        url = f"/api/elements/{el.id}/expliquer-coherence/"

        with patch.dict(os.environ, {"DEMO_MODE": "True", "LLM_PROVIDER": "mock"}):
            response = self.client.post(url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)

    # 13. DEMO_MODE=False → anonyme rejeté
    def test_13_securite_demo_mode_false_anonyme_rejete(self):
        el = self._creer_element("semelle_filante", resultat_valide={"condition_respectee": False})
        url = f"/api/elements/{el.id}/expliquer-coherence/"

        with patch.dict(os.environ, {"DEMO_MODE": "False"}):
            response = self.client.post(url)

        self.assertIn(response.status_code, (status.HTTP_401_UNAUTHORIZED, status.HTTP_403_FORBIDDEN))

    # 14. Utilisateur authentifié → accès autorisé (DEMO_MODE=False)
    def test_14_securite_demo_mode_false_authentifie_accepte(self):
        el = self._creer_element("semelle_filante", resultat_valide={"condition_respectee": False})
        url = f"/api/elements/{el.id}/expliquer-coherence/"
        self.client.force_authenticate(user=self.user)

        with patch.dict(os.environ, {"DEMO_MODE": "False", "LLM_PROVIDER": "mock"}):
            response = self.client.post(url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)

    # 15. Throttling endpoint explication → 429 après dépassement (10/min par défaut)
    def test_15_throttling_limite_depassee_429(self):
        el = self._creer_element("semelle_filante", resultat_valide={"condition_respectee": False})
        url = f"/api/elements/{el.id}/expliquer-coherence/"

        with patch.dict(os.environ, {"DEMO_MODE": "True", "LLM_PROVIDER": "mock"}):
            # 10 requêtes autorisées
            for i in range(10):
                r = self.client.post(url)
                self.assertEqual(r.status_code, status.HTTP_200_OK, f"Requete {i+1} a echoue")

            # La 11ème requête doit être rejetée en 429 Too Many Requests
            r_throttled = self.client.post(url)
            self.assertEqual(r_throttled.status_code, status.HTTP_429_TOO_MANY_REQUESTS)

    # 16. Aucune écriture DB pendant POST expliquer-coherence
    def test_16_aucune_ecriture_db_post_expliquer(self):
        el = self._creer_element("semelle_filante", resultat_valide={"condition_respectee": False})
        url = f"/api/elements/{el.id}/expliquer-coherence/"

        elements_avant = list(ElementStructurel.objects.values())
        with patch.dict(os.environ, {"DEMO_MODE": "True", "LLM_PROVIDER": "mock"}):
            response = self.client.post(url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        elements_apres = list(ElementStructurel.objects.values())
        self.assertEqual(elements_avant, elements_apres)
