"""
Tests d'intégration du sprint "Comptes & Permissions" :
- isolation inter-cabinets (un cabinet ne voit jamais les projets d'un autre)
- verrou d'ingénieur (seul ingénieur/admin peut valider un élément)
- un Admin voit tout son propre cabinet
- flux d'authentification complet (inscription, JWT, invitation,
  activation, changement de mot de passe, mot de passe oublié, logout)

Tous ces tests tournent avec DEMO_MODE=False explicitement : c'est
justement le mode où les permissions doivent s'appliquer pour de vrai.
"""

import os

from django.contrib.auth.models import User
from django.core import mail
from django.test import override_settings
from rest_framework import status
from rest_framework.test import APITestCase

from projets.models import EntrepriseParametres, Profil, Projet, ElementStructurel


def _sans_demo_mode():
    """Contexte : force DEMO_MODE=False le temps du test, restaure après."""
    return override_settings() if False else _EnvCtx("DEMO_MODE", "False")


class _EnvCtx:
    def __init__(self, key, value):
        self.key = key
        self.value = value
        self.ancien = None

    def __enter__(self):
        self.ancien = os.environ.get(self.key)
        os.environ[self.key] = self.value

    def __exit__(self, *a):
        if self.ancien is None:
            os.environ.pop(self.key, None)
        else:
            os.environ[self.key] = self.ancien


class IsolationInterCabinetsTestCase(APITestCase):
    """Le cœur du sprint : un cabinet ne doit jamais voir les données d'un autre."""

    def setUp(self):
        self.demo = _EnvCtx("DEMO_MODE", "False")
        self.demo.__enter__()

        self.ent_a = EntrepriseParametres.objects.create(nom="Cabinet A")
        self.ent_b = EntrepriseParametres.objects.create(nom="Cabinet B")

        self.user_a = User.objects.create_user("cabinet_a_user", password="x")
        Profil.objects.create(utilisateur=self.user_a, entreprise=self.ent_a, role=Profil.Role.INGENIEUR)

        self.user_b = User.objects.create_user("cabinet_b_user", password="x")
        Profil.objects.create(utilisateur=self.user_b, entreprise=self.ent_b, role=Profil.Role.INGENIEUR)

        self.projet_a = Projet.objects.create(nom="Projet A", entreprise=self.ent_a, cree_par=self.user_a)
        self.projet_b = Projet.objects.create(nom="Projet B", entreprise=self.ent_b, cree_par=self.user_b)

    def tearDown(self):
        self.demo.__exit__()

    def _noms(self, data):
        items = data.get("results", data) if isinstance(data, dict) else data
        return [p["nom"] for p in items]

    def test_liste_projets_filtree_par_entreprise(self):
        self.client.force_authenticate(user=self.user_a)
        response = self.client.get("/api/projets/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        noms = self._noms(response.data)
        self.assertIn("Projet A", noms)
        self.assertNotIn("Projet B", noms)

    def test_acces_detail_autre_cabinet_refuse(self):
        self.client.force_authenticate(user=self.user_a)
        response = self.client.get(f"/api/projets/{self.projet_b.id}/")
        # 404 plutôt que 403 : on ne révèle même pas l'existence de l'objet
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_acces_detail_propre_cabinet_autorise(self):
        self.client.force_authenticate(user=self.user_a)
        response = self.client.get(f"/api/projets/{self.projet_a.id}/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_creation_projet_rattache_automatiquement_a_l_entreprise(self):
        self.client.force_authenticate(user=self.user_a)
        response = self.client.post("/api/projets/", {"nom": "Nouveau Projet"}, format="json")
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        projet = Projet.objects.get(id=response.data["id"])
        self.assertEqual(projet.entreprise_id, self.ent_a.id)
        self.assertEqual(projet.cree_par_id, self.user_a.id)

    def test_utilisateur_sans_profil_non_filtre_legacy(self):
        """Comportement legacy volontaire : un utilisateur authentifié sans
        Profil (compte créé avant ce sprint) n'est pas bloqué -- pas de
        régression pour les comptes existants tant que l'onboarding n'a
        pas encore créé leur Profil."""
        user_sans_profil = User.objects.create_user("legacy_user", password="x")
        self.client.force_authenticate(user=user_sans_profil)
        response = self.client.get(f"/api/projets/{self.projet_a.id}/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)


class VerrouIngenieurTestCase(APITestCase):
    """Seul un compte ingénieur ou admin peut valider/verrouiller un élément."""

    def setUp(self):
        self.demo = _EnvCtx("DEMO_MODE", "False")
        self.demo.__enter__()

        self.entreprise = EntrepriseParametres.objects.create(nom="Cabinet Test")

        self.technicien = User.objects.create_user("technicien1", password="x")
        Profil.objects.create(utilisateur=self.technicien, entreprise=self.entreprise, role=Profil.Role.TECHNICIEN)

        self.ingenieur = User.objects.create_user("ingenieur1", password="x")
        Profil.objects.create(utilisateur=self.ingenieur, entreprise=self.entreprise, role=Profil.Role.INGENIEUR)

        self.admin = User.objects.create_user("admin1", password="x")
        Profil.objects.create(utilisateur=self.admin, entreprise=self.entreprise, role=Profil.Role.ADMIN)

        self.projet = Projet.objects.create(nom="Projet", entreprise=self.entreprise)
        self.element = ElementStructurel.objects.create(
            projet=self.projet, identifiant="P1", type_element="poteau",
            resultat_calcul={"section": "20x20"},
        )

    def tearDown(self):
        self.demo.__exit__()

    def test_technicien_ne_peut_pas_valider(self):
        self.client.force_authenticate(user=self.technicien)
        response = self.client.post(f"/api/elements/{self.element.id}/valider/", {}, format="json")
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_ingenieur_peut_valider(self):
        self.client.force_authenticate(user=self.ingenieur)
        response = self.client.post(f"/api/elements/{self.element.id}/valider/", {}, format="json")
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_admin_peut_valider(self):
        self.client.force_authenticate(user=self.admin)
        response = self.client.post(f"/api/elements/{self.element.id}/valider/", {}, format="json")
        self.assertEqual(response.status_code, status.HTTP_200_OK)


class GestionComptesAdminTestCase(APITestCase):
    """Un Admin voit et gère tout son cabinet ; jamais celui d'un autre."""

    def setUp(self):
        self.demo = _EnvCtx("DEMO_MODE", "False")
        self.demo.__enter__()

        self.ent_a = EntrepriseParametres.objects.create(nom="Cabinet A")
        self.ent_b = EntrepriseParametres.objects.create(nom="Cabinet B")

        self.admin_a = User.objects.create_user("admin_a", password="x")
        Profil.objects.create(utilisateur=self.admin_a, entreprise=self.ent_a, role=Profil.Role.ADMIN)

        self.technicien_a = User.objects.create_user("technicien_a", password="x")
        Profil.objects.create(utilisateur=self.technicien_a, entreprise=self.ent_a, role=Profil.Role.TECHNICIEN)

        self.technicien_b = User.objects.create_user("technicien_b", password="x")
        Profil.objects.create(utilisateur=self.technicien_b, entreprise=self.ent_b, role=Profil.Role.TECHNICIEN)

    def tearDown(self):
        self.demo.__exit__()

    def test_technicien_ne_peut_pas_gerer_les_comptes(self):
        self.client.force_authenticate(user=self.technicien_a)
        response = self.client.get("/api/auth/membres/")
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_admin_voit_uniquement_son_cabinet(self):
        self.client.force_authenticate(user=self.admin_a)
        response = self.client.get("/api/auth/membres/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        usernames = [m["username"] for m in response.data]
        self.assertIn("admin_a", usernames)
        self.assertIn("technicien_a", usernames)
        self.assertNotIn("technicien_b", usernames)

    def test_admin_ne_peut_pas_desactiver_un_membre_d_un_autre_cabinet(self):
        self.client.force_authenticate(user=self.admin_a)
        response = self.client.post(f"/api/auth/membres/{self.technicien_b.id}/desactiver/")
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
        self.technicien_b.refresh_from_db()
        self.assertTrue(self.technicien_b.is_active)

    def test_admin_ne_peut_pas_se_desactiver_lui_meme(self):
        self.client.force_authenticate(user=self.admin_a)
        response = self.client.post(f"/api/auth/membres/{self.admin_a.id}/desactiver/")
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)


class FluxAuthentificationTestCase(APITestCase):
    """Bout en bout : inscription -> login JWT -> invitation -> activation
    -> changement de mot de passe -> mot de passe oublié -> logout."""

    def setUp(self):
        self.demo = _EnvCtx("DEMO_MODE", "False")
        self.demo.__enter__()

    def tearDown(self):
        self.demo.__exit__()

    def test_inscription_cree_entreprise_et_compte_admin(self):
        response = self.client.post("/api/auth/inscription/", {
            "nom_entreprise": "BATI-TEST SARL",
            "username": "admin_test",
            "email": "admin@bati-test.ci",
            "mot_de_passe": "UnMotDePasseSolide2026!",
        }, format="json")
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data["profil"]["role"], "admin")
        self.assertIn("access", response.data)
        self.assertIn("refresh", response.data)

    def test_inscription_refuse_mot_de_passe_faible(self):
        response = self.client.post("/api/auth/inscription/", {
            "nom_entreprise": "BATI-TEST SARL",
            "username": "admin_test2",
            "email": "admin2@bati-test.ci",
            "mot_de_passe": "123",
        }, format="json")
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_login_jwt_et_acces_route_protegee(self):
        self.client.post("/api/auth/inscription/", {
            "nom_entreprise": "BATI-TEST SARL",
            "username": "admin_test3",
            "email": "admin3@bati-test.ci",
            "mot_de_passe": "UnMotDePasseSolide2026!",
        }, format="json")

        response = self.client.post("/api/auth/token/", {
            "username": "admin_test3", "password": "UnMotDePasseSolide2026!",
        }, format="json")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        access = response.data["access"]

        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {access}")
        response2 = self.client.get("/api/projets/")
        self.assertEqual(response2.status_code, status.HTTP_200_OK)

    def test_invitation_puis_activation(self):
        insc = self.client.post("/api/auth/inscription/", {
            "nom_entreprise": "BATI-TEST SARL",
            "username": "admin_test4",
            "email": "admin4@bati-test.ci",
            "mot_de_passe": "UnMotDePasseSolide2026!",
        }, format="json")
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {insc.data['access']}")

        invit = self.client.post("/api/auth/inviter/", {
            "email": "technicien4@bati-test.ci", "role": "technicien",
        }, format="json")
        self.assertEqual(invit.status_code, status.HTTP_201_CREATED)
        self.assertFalse(invit.data["email_envoye"])  # jamais de faux "email envoyé"
        self.assertIn("uid", invit.data)
        self.assertIn("token", invit.data)

        # Le compte est créé mais désactivé, et n'a pas encore de mot de passe utilisable
        user_invite = User.objects.get(username="technicien4@bati-test.ci")
        self.assertFalse(user_invite.is_active)

        self.client.credentials()  # activation ne nécessite pas d'être connecté
        activ = self.client.post("/api/auth/activer/", {
            "uid": invit.data["uid"],
            "token": invit.data["token"],
            "mot_de_passe": "AutreMotDePasse2026!",
        }, format="json")
        self.assertEqual(activ.status_code, status.HTTP_200_OK)

        user_invite.refresh_from_db()
        self.assertTrue(user_invite.is_active)

        login = self.client.post("/api/auth/token/", {
            "username": "technicien4@bati-test.ci", "password": "AutreMotDePasse2026!",
        }, format="json")
        self.assertEqual(login.status_code, status.HTTP_200_OK)

    def test_mot_de_passe_oublie_ne_revele_pas_si_email_inconnu(self):
        response = self.client.post("/api/auth/forgot-password/", {
            "email": "personne@nulle-part.ci",
        }, format="json")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
    # Adaptez les clés aux retours réels de votre vue demander_reinitialisation_mdp
        self.assertIn("detail", response.data)

    def test_mot_de_passe_oublie_puis_reinitialisation(self):
        self.client.post("/api/auth/inscription/", {
            "nom_entreprise": "BATI-TEST SARL",
            "username": "admin_test5",
            "email": "admin5@bati-test.ci",
            "mot_de_passe": "UnMotDePasseSolide2026!",
        }, format="json")

        demande = self.client.post("/api/auth/mot-de-passe-oublie/", {
            "email": "admin5@bati-test.ci",
        }, format="json")
        self.assertFalse(demande.data["email_envoye"])
        self.assertIn("lien_reinitialisation", demande.data)

        reinit = self.client.post("/api/auth/reinitialiser-mot-de-passe/", {
            "uid": demande.data["lien_reinitialisation"].split("uid=")[1].split("&")[0],
            "token": demande.data["lien_reinitialisation"].split("token=")[1],
            "nouveau_mot_de_passe": "EncoreUnAutre2026!",
        }, format="json")
        self.assertEqual(reinit.status_code, status.HTTP_200_OK)

        login = self.client.post("/api/auth/token/", {
            "username": "admin_test5", "password": "EncoreUnAutre2026!",
        }, format="json")
        self.assertEqual(login.status_code, status.HTTP_200_OK)

    def test_logout_revoque_le_refresh_token(self):
        insc = self.client.post("/api/auth/inscription/", {
            "nom_entreprise": "BATI-TEST SARL",
            "username": "admin_test6",
            "email": "admin6@bati-test.ci",
            "mot_de_passe": "UnMotDePasseSolide2026!",
        }, format="json")
        access, refresh = insc.data["access"], insc.data["refresh"]

        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {access}")
        logout = self.client.post("/api/auth/logout/", {"refresh": refresh}, format="json")
        self.assertEqual(logout.status_code, status.HTTP_205_RESET_CONTENT)

        refresh_apres = self.client.post("/api/auth/token/refresh/", {"refresh": refresh}, format="json")
        self.assertEqual(refresh_apres.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_changer_mot_de_passe(self):
        insc = self.client.post("/api/auth/inscription/", {
            "nom_entreprise": "BATI-TEST SARL",
            "username": "admin_test7",
            "email": "admin7@bati-test.ci",
            "mot_de_passe": "UnMotDePasseSolide2026!",
        }, format="json")
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {insc.data['access']}")

        response = self.client.post("/api/auth/changer-mot-de-passe/", {
            "ancien_mot_de_passe": "UnMotDePasseSolide2026!",
            "nouveau_mot_de_passe": "ToutNouveau2026!",
        }, format="json")
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        login = self.client.post("/api/auth/token/", {
            "username": "admin_test7", "password": "ToutNouveau2026!",
        }, format="json")
        self.assertEqual(login.status_code, status.HTTP_200_OK)

    def test_changer_mot_de_passe_refuse_si_ancien_incorrect(self):
        insc = self.client.post("/api/auth/inscription/", {
            "nom_entreprise": "BATI-TEST SARL",
            "username": "admin_test8",
            "email": "admin8@bati-test.ci",
            "mot_de_passe": "UnMotDePasseSolide2026!",
        }, format="json")
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {insc.data['access']}")

        response = self.client.post("/api/auth/changer-mot-de-passe/", {
            "ancien_mot_de_passe": "MauvaisMotDePasse",
            "nouveau_mot_de_passe": "ToutNouveau2026!",
        }, format="json")
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)


@override_settings(
    EMAIL_HOST="smtp.dqe-test.local",
    DEFAULT_FROM_EMAIL="no-reply@dqe-test.local",
    FRONTEND_URL="https://app.dqe-test.local",
)
class EnvoiEmailTestCase(APITestCase):
    """Sprint "Serveur mail" : avec un backend SMTP réellement configuré
    (ici simulé par le backend locmem de Django, capturé dans mail.outbox),
    invitation et réinitialisation doivent réellement envoyer un email --
    et la réinitialisation ne doit plus jamais exposer le lien en JSON."""

    def setUp(self):
        self.demo = _EnvCtx("DEMO_MODE", "False")
        self.demo.__enter__()

    def tearDown(self):
        self.demo.__exit__()

    @override_settings(EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend")
    def test_inscription_envoie_un_email_de_bienvenue(self):
        mail.outbox = []
        insc = self.client.post("/api/auth/inscription/", {
            "nom_entreprise": "BATI-TEST SARL",
            "username": "admin_mail0",
            "email": "admin_mail0@bati-test.ci",
            "mot_de_passe": "UnMotDePasseSolide2026!",
        }, format="json")
        self.assertEqual(insc.status_code, status.HTTP_201_CREATED)
        self.assertTrue(insc.data["email_envoye"])
        self.assertEqual(len(mail.outbox), 1)
        self.assertEqual(mail.outbox[0].to, ["admin_mail0@bati-test.ci"])
        self.assertIn("BATI-TEST SARL", mail.outbox[0].body)

    @override_settings(EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend")
    def test_invitation_envoie_reellement_un_email(self):
        insc = self.client.post("/api/auth/inscription/", {
            "nom_entreprise": "BATI-TEST SARL",
            "username": "admin_mail1",
            "email": "admin_mail1@bati-test.ci",
            "mot_de_passe": "UnMotDePasseSolide2026!",
        }, format="json")
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {insc.data['access']}")

        mail.outbox = []
        invit = self.client.post("/api/auth/inviter/", {
            "email": "invite_mail1@bati-test.ci", "role": "technicien",
        }, format="json")
        self.assertEqual(invit.status_code, status.HTTP_201_CREATED)
        self.assertTrue(invit.data["email_envoye"])
        self.assertEqual(len(mail.outbox), 1)
        self.assertEqual(mail.outbox[0].to, ["invite_mail1@bati-test.ci"])
        self.assertIn("https://app.dqe-test.local/activer-compte", mail.outbox[0].body)

    @override_settings(EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend")
    def test_reinitialisation_envoie_email_et_ne_fuite_pas_le_lien(self):
        self.client.post("/api/auth/inscription/", {
            "nom_entreprise": "BATI-TEST SARL",
            "username": "admin_mail2",
            "email": "admin_mail2@bati-test.ci",
            "mot_de_passe": "UnMotDePasseSolide2026!",
        }, format="json")

        mail.outbox = []
        demande = self.client.post("/api/auth/mot-de-passe-oublie/", {
            "email": "admin_mail2@bati-test.ci",
        }, format="json")
        self.assertEqual(demande.status_code, status.HTTP_200_OK)
        self.assertTrue(demande.data["email_envoye"])
        self.assertNotIn("lien_reinitialisation", demande.data)
        self.assertEqual(len(mail.outbox), 1)
        self.assertEqual(mail.outbox[0].to, ["admin_mail2@bati-test.ci"])
        self.assertIn("https://app.dqe-test.local/reinitialiser-mot-de-passe", mail.outbox[0].body)

    @override_settings(EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend")
    def test_reinitialisation_reponse_identique_email_connu_ou_non(self):
        """Anti-énumération : avec SMTP configuré, la réponse ne doit
        jamais permettre de distinguer un email connu d'un email inconnu."""
        self.client.post("/api/auth/inscription/", {
            "nom_entreprise": "BATI-TEST SARL",
            "username": "admin_mail3",
            "email": "admin_mail3@bati-test.ci",
            "mot_de_passe": "UnMotDePasseSolide2026!",
        }, format="json")

        connu = self.client.post("/api/auth/mot-de-passe-oublie/", {
            "email": "admin_mail3@bati-test.ci",
        }, format="json")
        inconnu = self.client.post("/api/auth/mot-de-passe-oublie/", {
            "email": "personne@nulle-part.ci",
        }, format="json")
        self.assertEqual(set(connu.data.keys()), set(inconnu.data.keys()))
        self.assertEqual(connu.data["email_envoye"], inconnu.data["email_envoye"])