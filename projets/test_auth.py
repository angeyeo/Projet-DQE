from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase
from django.contrib.auth.models import User

class AuthEndpointsTests(APITestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="testuser", email="test@example.com", password="AncienPassword123!")

    def test_demande_reinitialisation_mdp(self):
        url = reverse('forgot-password')
        data = {"email": "test@example.com"}
        response = self.client.post(url, data)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn("reset_url", response.data)

    def test_changement_mot_de_passe_connecte(self):
        self.client.force_authenticate(user=self.user)
        url = reverse('change-password')
        data = {
            "ancien_mdp": "AncienPassword123!",
            "nouveau_mdp": "NouveauPassword456!"
        }
        response = self.client.post(url, data)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        
        self.user.refresh_from_db()
        self.assertTrue(self.user.check_password("NouveauPassword456!"))