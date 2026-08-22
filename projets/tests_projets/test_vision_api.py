import io
import json
import os
from unittest import mock
from django.contrib.auth.models import User
from django.core.cache import cache
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import override_settings
from rest_framework import status
from rest_framework.test import APITestCase
from PIL import Image

from projets.models import Projet, ElementStructurel
from projets.services.assistant_ia.client import LLMServiceError, MockAIClient


def generer_image_jpeg_valide() -> bytes:
    """Génère en mémoire une vraie petite image JPEG."""
    img = Image.new("RGB", (10, 10), color="red")
    stream = io.BytesIO()
    img.save(stream, format="JPEG")
    return stream.getvalue()


def generer_image_png_valide() -> bytes:
    """Génère en mémoire une vraie petite image PNG."""
    img = Image.new("RGBA", (10, 10), color="blue")
    stream = io.BytesIO()
    img.save(stream, format="PNG")
    return stream.getvalue()


class TestVisionAPI(APITestCase):
    def setUp(self):
        # On s'assure que le cache est propre avant chaque test pour éviter des interférences de throttling
        cache.clear()

        # Création des données de test
        self.projet = Projet.objects.create(nom="Projet Test Vision")
        self.user = User.objects.create_user(username="testuser", password="password123")

        # Par défaut, on se met en mode DEMO_MODE=True pour simplifier les tests nominaux hors-sécurité
        self.original_demo_mode = os.getenv("DEMO_MODE")
        os.environ["DEMO_MODE"] = "True"

        # On force également le fournisseur d'IA à 'mock' pour éviter les appels réels
        self.original_llm_provider = os.getenv("LLM_PROVIDER")
        os.environ["LLM_PROVIDER"] = "mock"

        self.jpeg_bytes = generer_image_jpeg_valide()
        self.png_bytes = generer_image_png_valide()

    def tearDown(self):
        # Restauration des variables d'environnement d'origine
        if self.original_demo_mode is not None:
            os.environ["DEMO_MODE"] = self.original_demo_mode
        else:
            os.environ.pop("DEMO_MODE", None)

        if self.original_llm_provider is not None:
            os.environ["LLM_PROVIDER"] = self.original_llm_provider
        else:
            os.environ.pop("LLM_PROVIDER", None)

        cache.clear()

    def _url(self, projet_id=None):
        pid = projet_id if projet_id is not None else self.projet.id
        return f"/api/projets/{pid}/analyser_plan_image/"

    # --- A. Routing ---
    def test_endpoint_existe_en_post(self):
        response = self.client.post(self._url(), {}, format="multipart")
        # Le routing existe, la réponse sera 400 (car fichier manquant) et non 404/405
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_endpoint_refuse_get(self):
        response = self.client.get(self._url())
        self.assertEqual(response.status_code, status.HTTP_405_METHOD_NOT_ALLOWED)

    # --- B. Projet ---
    def test_projet_inexistant_retourne_404(self):
        response = self.client.post(self._url(projet_id=9999), {}, format="multipart")
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    # --- C. Upload ---
    def test_fichier_absent_retourne_400(self):
        response = self.client.post(self._url(), {}, format="multipart")
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("fichier image est requis", response.data["detail"])

    def test_png_valide_retourne_200(self):
        fichier = SimpleUploadedFile("plan.png", self.png_bytes, content_type="image/png")
        response = self.client.post(self._url(), {"fichier": fichier}, format="multipart")
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_jpeg_valide_retourne_200(self):
        fichier = SimpleUploadedFile("plan.jpg", self.jpeg_bytes, content_type="image/jpeg")
        response = self.client.post(self._url(), {"fichier": fichier}, format="multipart")
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_pdf_rejete_retourne_400(self):
        fichier = SimpleUploadedFile("plan.pdf", b"%PDF-1.4...", content_type="application/pdf")
        response = self.client.post(self._url(), {"fichier": fichier}, format="multipart")
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("non supporté", response.data["detail"])

    def test_gif_rejete_retourne_400(self):
        fichier = SimpleUploadedFile("plan.gif", b"GIF89a...", content_type="image/gif")
        response = self.client.post(self._url(), {"fichier": fichier}, format="multipart")
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("non supporté", response.data["detail"])

    def test_image_corrompue_retourne_400(self):
        # Bytes aléatoires ne correspondant pas à une structure JPEG
        fichier = SimpleUploadedFile("plan.jpg", b"donnees_corrompues_non_image", content_type="image/jpeg")
        response = self.client.post(self._url(), {"fichier": fichier}, format="multipart")
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("corrompue ou illisible", response.data["detail"])

    def test_mime_incoherent_retourne_400(self):
        # On envoie un vrai PNG mais avec le MIME image/jpeg
        fichier = SimpleUploadedFile("plan.jpg", self.png_bytes, content_type="image/jpeg")
        response = self.client.post(self._url(), {"fichier": fichier}, format="multipart")
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("Incohérence format", response.data["detail"])

    # --- D. Réponse ---
    def test_structure_reponse_nominale(self):
        fichier = SimpleUploadedFile("plan.png", self.png_bytes, content_type="image/png")
        response = self.client.post(self._url(), {"fichier": fichier}, format="multipart")
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        data = response.data
        self.assertEqual(data["mode_import"], "VISION")
        self.assertEqual(data["source"], "MOCK")
        self.assertTrue(data["validation_humaine_requise"])
        self.assertIn("annotations_lues", data)
        self.assertIn("textes_non_classes", data)

        # Vérification du mapping et parsing local appliqué sur le retour Mock
        annotations = data["annotations_lues"]
        self.assertGreater(len(annotations), 0)
        self.assertEqual(annotations[0]["texte_lu"], "S1(170x170x40)")
        self.assertEqual(annotations[0]["repere"], "S1")
        self.assertEqual(annotations[0]["type_normalise"], "semelle")
        self.assertEqual(annotations[0]["dimensions_parsees"]["valeurs"], [170.0, 170.0, 40.0])

    # --- E. Fallback ---
    @mock.patch("projets.services.assistant_ia.vision.get_ai_client")
    def test_fallback_sur_erreur_service_retourne_200_avec_fallback_local(self, mock_get_client):
        # Simulation d'une panne réseau / indisponibilité de l'API Gemini
        mock_client = mock.MagicMock()
        mock_client.appeler_llm_vision.side_effect = LLMServiceError(
            "Service Unavailable", code="LLM_UNAVAILABLE", status_code=503
        )
        mock_get_client.return_value = mock_client

        fichier = SimpleUploadedFile("plan.png", self.png_bytes, content_type="image/png")
        response = self.client.post(self._url(), {"fichier": fichier}, format="multipart")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = response.data
        self.assertEqual(data["mode_import"], "VISION")
        self.assertEqual(data["source"], "FALLBACK_LOCAL")
        self.assertEqual(data["annotations_lues"], [])
        self.assertEqual(data["textes_non_classes"], [])
        self.assertTrue(data["validation_humaine_requise"])
        self.assertIn("L'analyse automatique du plan n'est pas disponible", data["message"])

    # --- F. Sécurité ---
    def test_securite_demo_mode_false_anonyme_rejete(self):
        os.environ["DEMO_MODE"] = "False"
        # Client anonyme
        fichier = SimpleUploadedFile("plan.png", self.png_bytes, content_type="image/png")
        response = self.client.post(self._url(), {"fichier": fichier}, format="multipart")
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_securite_demo_mode_false_authentifie_accepte(self):
        os.environ["DEMO_MODE"] = "False"
        # Connexion de l'utilisateur de test
        self.client.force_authenticate(user=self.user)
        fichier = SimpleUploadedFile("plan.png", self.png_bytes, content_type="image/png")
        response = self.client.post(self._url(), {"fichier": fichier}, format="multipart")
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_securite_demo_mode_true_anonyme_accepte(self):
        os.environ["DEMO_MODE"] = "True"
        # Client non authentifié (anonyme)
        fichier = SimpleUploadedFile("plan.png", self.png_bytes, content_type="image/png")
        response = self.client.post(self._url(), {"fichier": fichier}, format="multipart")
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    # --- G. Throttling ---
    def test_throttling_limite_de_5_appels_par_minute(self):
        # En mode démonstration pour simplifier les requêtes
        os.environ["DEMO_MODE"] = "True"

        # 5 appels autorisés
        for _ in range(5):
            fichier = SimpleUploadedFile("plan.png", self.png_bytes, content_type="image/png")
            response = self.client.post(self._url(), {"fichier": fichier}, format="multipart")
            self.assertEqual(response.status_code, status.HTTP_200_OK)

        # Le 6ème appel doit être rejeté en 429 Too Many Requests
        fichier_throttled = SimpleUploadedFile("plan.png", self.png_bytes, content_type="image/png")
        response_throttled = self.client.post(self._url(), {"fichier": fichier_throttled}, format="multipart")
        self.assertEqual(response_throttled.status_code, status.HTTP_429_TOO_MANY_REQUESTS)

    # --- H. Invariance DB ---
    def test_invariance_base_de_donnees(self):
        # Nombre de projets et d'éléments avant l'appel
        projets_avant = Projet.objects.count()
        elements_avant = ElementStructurel.objects.count()

        # Appel Vision
        fichier = SimpleUploadedFile("plan.png", self.png_bytes, content_type="image/png")
        response = self.client.post(self._url(), {"fichier": fichier}, format="multipart")
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        # Nombre de projets et d'éléments après l'appel (invariance totale)
        self.assertEqual(Projet.objects.count(), projets_avant)
        self.assertEqual(ElementStructurel.objects.count(), elements_avant)

        # Le fichier_import_origine du projet doit rester vide
        self.projet.refresh_from_db()
        self.assertFalse(bool(self.projet.fichier_import_origine))

    # --- I. Limite de taille et Exceptions inattendues ---
    @override_settings(PLAN_IMAGE_MAX_BYTES=1000000)  # 1 Mo
    def test_image_sous_la_limite_taille_acceptee(self):
        # L'image fait quelques centaines d'octets, donc < 1 Mo
        fichier = SimpleUploadedFile("plan.png", self.png_bytes, content_type="image/png")
        response = self.client.post(self._url(), {"fichier": fichier}, format="multipart")
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    @override_settings(PLAN_IMAGE_MAX_BYTES=10)  # 10 octets
    @mock.patch("projets.views.analyser_plan_2d")
    def test_image_au_dessus_de_la_limite_taille_rejete_sans_appel_service(self, mock_analyser):
        # L'image fait plus de 10 octets, elle dépasse la limite de 10 octets
        fichier = SimpleUploadedFile("plan.png", self.png_bytes, content_type="image/png")
        response = self.client.post(self._url(), {"fichier": fichier}, format="multipart")
        self.assertEqual(response.status_code, status.HTTP_413_REQUEST_ENTITY_TOO_LARGE)
        self.assertIn("trop volumineux", response.data["detail"])
        mock_analyser.assert_not_called()

    @mock.patch("projets.views.analyser_plan_2d")
    def test_erreur_inattendue_retourne_500_propre(self, mock_analyser):
        # Simulation d'une exception imprévue
        mock_analyser.side_effect = RuntimeError("Crash inattendu")
        fichier = SimpleUploadedFile("plan.png", self.png_bytes, content_type="image/png")
        response = self.client.post(self._url(), {"fichier": fichier}, format="multipart")
        self.assertEqual(response.status_code, status.HTTP_500_INTERNAL_SERVER_ERROR)
        self.assertIn("erreur interne", response.data["detail"])
