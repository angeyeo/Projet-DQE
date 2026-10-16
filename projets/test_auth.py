from django.contrib.auth.models import User
from django.test import override_settings
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase


class AuthEndpointsTests(APITestCase):
    """Routes réelles (auth_views) -- les anciens noms 'forgot-password' /
    'change-password' pointaient vers des vues mortes non routées."""

    def setUp(self):
        self.user = User.objects.create_user(
            username="testuser", email="test@example.com", password="AncienPassword123!"
        )

    @override_settings(DEBUG=True)
    def test_demande_reinitialisation_mdp_dev(self):
        response = self.client.post(reverse("auth-mdp-oublie"), {"email": "test@example.com"})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        # En DEBUG uniquement, sans SMTP : lien renvoyé pour le poste de dev.
        self.assertIn("lien_reinitialisation", response.data)

    @override_settings(DEBUG=False, EMAIL_HOST="")
    def test_demande_reinitialisation_ne_fuit_jamais_le_lien_en_production(self):
        response = self.client.post(reverse("auth-mdp-oublie"), {"email": "test@example.com"})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertNotIn("lien_reinitialisation", response.data)
        self.assertFalse(response.data["email_envoye"])

    def test_changement_mot_de_passe_connecte(self):
        self.client.force_authenticate(user=self.user)
        response = self.client.post(reverse("auth-changer-mdp"), {
            "ancien_mot_de_passe": "AncienPassword123!",
            "nouveau_mot_de_passe": "NouveauPassword456!",
        })
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.user.refresh_from_db()
        self.assertTrue(self.user.check_password("NouveauPassword456!"))
