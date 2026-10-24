import io
import os
from unittest import mock

from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from rest_framework import status
from rest_framework.test import APITestCase
from PIL import Image

from projets.models import Projet, Profil
from projets.tests_projets.utils import creer_cabinet

User = get_user_model()


def image_test():
    image = Image.new("RGB", (3, 3), color="red")
    stream = io.BytesIO()
    image.save(stream, format="JPEG")
    return stream.getvalue()


class TestConsentementGemini(APITestCase):
    def setUp(self):
        self.cabinet = creer_cabinet("Cabinet consentement")
        self.user = User.objects.create_user(username="consentement", password="test-password")
        Profil.objects.create(utilisateur=self.user, entreprise=self.cabinet, role=Profil.Role.INGENIEUR)
        self.projet = Projet.objects.create(nom="Projet consentement", entreprise=self.cabinet, cree_par=self.user)
        self.client.force_authenticate(user=self.user)
        self.provider = mock.patch.dict(os.environ, {"LLM_PROVIDER": "gemini", "LLM_API_KEY": "test-key"})
        self.provider.start()
        self.addCleanup(self.provider.stop)

    def enregistrer(self, decision):
        return self.client.post("/api/auth/moi/consentement-ia/", {"decision": decision}, format="json")

    def test_premiere_requete_bloquee_sans_consentement(self):
        with mock.patch("projets.views.structurer_description_projet") as appel:
            response = self.client.post("/api/assistant/structurer-projet/", {"description": "Projet R+1"}, format="json")
        self.assertEqual(response.status_code, status.HTTP_428_PRECONDITION_REQUIRED)
        appel.assert_not_called()

    def test_acceptation_persistante_et_commune_aux_fonctionnalites(self):
        choix = self.enregistrer("accepte")
        self.assertEqual(choix.status_code, status.HTTP_200_OK)
        self.assertTrue(choix.data["consentement_ia_valide"])
        self.assertTrue(self.client.get("/api/me/").data["consentement_ia_valide"])
        with mock.patch("projets.views.structurer_description_projet", return_value={"source": "GEMINI"}) as appel:
            response = self.client.post("/api/assistant/structurer-projet/", {"description": "Projet R+1"}, format="json")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        appel.assert_called_once()

    def test_refus_persistant_bloque_sans_reafficher_automatiquement(self):
        choix = self.enregistrer("refuse")
        self.assertEqual(choix.status_code, status.HTTP_200_OK)
        self.assertEqual(choix.data["consentement_ia"], "refuse")
        with mock.patch("projets.views.structurer_description_projet") as appel:
            response = self.client.post("/api/assistant/structurer-projet/", {"description": "Projet R+1"}, format="json")
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        self.assertEqual(response.data["code"], "AI_CONSENT_REFUSED")
        appel.assert_not_called()

    def test_activation_et_desactivation_depuis_les_parametres(self):
        self.enregistrer("refuse")
        self.enregistrer("accepte")
        self.assertTrue(self.client.get("/api/auth/moi/").data["consentement_ia_valide"])
        self.enregistrer("refuse")
        self.assertFalse(self.client.get("/api/auth/moi/").data["consentement_ia_valide"])

    def test_vision_autorisee_apres_accord_sans_scope(self):
        self.enregistrer("accepte")
        fichier = SimpleUploadedFile("plan.jpg", image_test(), content_type="image/jpeg")
        with mock.patch("projets.views.analyser_plan_2d", return_value={"source": "GEMINI"}) as appel:
            response = self.client.post(f"/api/projets/{self.projet.pk}/analyser_plan_image/", {"fichier": fichier}, format="multipart")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        appel.assert_called_once()

    def test_autre_utilisateur_independant(self):
        self.enregistrer("accepte")
        autre = User.objects.create_user(username="autre-consentement")
        Profil.objects.create(utilisateur=autre, entreprise=self.cabinet, role=Profil.Role.TECHNICIEN)
        self.client.force_authenticate(user=autre)
        response = self.client.post("/api/assistant/structurer-projet/", {"description": "Projet R+1"}, format="json")
        self.assertEqual(response.status_code, status.HTTP_428_PRECONDITION_REQUIRED)

    def test_authentification_reste_requise(self):
        self.client.logout()
        response = self.client.post("/api/auth/moi/consentement-ia/", {"decision": "accepte"}, format="json")
        self.assertIn(response.status_code, (status.HTTP_401_UNAUTHORIZED, status.HTTP_403_FORBIDDEN))
