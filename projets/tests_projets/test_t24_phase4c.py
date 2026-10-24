"""Compléments ciblés de parité fonctionnelle T24 (legacy et API v1)."""

from tempfile import TemporaryDirectory
from unittest.mock import patch
from urllib.parse import parse_qs, urlparse

from django.contrib.auth.models import User
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import override_settings
from rest_framework.test import APIClient, APITestCase

from projets.models import (
    ElementStructurel,
    OuvrageType,
    Profil,
    Projet,
)
from projets.tests_projets.test_hypotheses_dqe import projet_grille
from projets.tests_projets.test_import_bibliotheque import classeur_test
from projets.tests_projets.test_import_plan_api import _construire_ifc_bytes
from projets.tests_projets.utils import BAREME_TEST, authentifier, creer_cabinet, creer_membre


class T24V1ComptesEtJwtTests(APITestCase):
    """Rejoue les principaux parcours comptes sur chacun des deux préfixes."""

    @override_settings(DEBUG=True, EMAIL_HOST="")
    @patch("projets.auth_views._envoyer_email", return_value=False)
    def test_inscription_membres_activation_mdp_et_logout_legacy_v1(self, _email):
        for suffix, prefix in (("legacy", "/api"), ("v1", "/api/v1")):
            username = f"t24_{suffix}_admin"
            password = "MotDePasseSolide-2026!"
            inscription = self.client.post(
                f"{prefix}/auth/inscription/",
                {
                    "nom_entreprise": f"Cabinet T24 {suffix}",
                    "username": username,
                    "email": f"{username}@example.test",
                    "mot_de_passe": password,
                },
                format="json",
            )
            self.assertEqual(inscription.status_code, 201, inscription.data)
            self.assertEqual(inscription.data["profil"]["role"], Profil.Role.ADMIN)
            self.assertFalse(inscription.data["email_envoye"])
            admin = User.objects.get(username=username)
            cabinet = admin.profil.entreprise

            admin_client = APIClient()
            admin_client.credentials(HTTP_AUTHORIZATION=f"Bearer {inscription.data['access']}")
            moi = admin_client.get(f"{prefix}/auth/moi/")
            self.assertEqual(moi.status_code, 200)
            self.assertEqual(moi.data["username"], username)

            invitation = admin_client.post(
                f"{prefix}/auth/inviter/",
                {"email": f"{suffix}_technicien@example.test", "role": Profil.Role.TECHNICIEN},
                format="json",
            )
            self.assertEqual(invitation.status_code, 201, invitation.data)
            cible = User.objects.get(username=f"{suffix}_technicien@example.test")
            self.assertFalse(cible.is_active)
            self.assertEqual(cible.profil.entreprise_id, cabinet.pk)

            activation = self.client.post(
                f"{prefix}/auth/activer/",
                {"uid": invitation.data["uid"], "token": invitation.data["token"],
                 "mot_de_passe": "ActivationSolide-2026!"},
                format="json",
            )
            self.assertEqual(activation.status_code, 200, activation.data)
            cible.refresh_from_db()
            self.assertTrue(cible.is_active)

            membres = admin_client.get(f"{prefix}/auth/membres/")
            self.assertEqual(membres.status_code, 200)
            self.assertEqual({m["username"] for m in membres.data}, {username, cible.username})

            connexion = self.client.post(
                f"{prefix}/auth/token/",
                {"username": cible.username, "password": "ActivationSolide-2026!"}, format="json",
            )
            self.assertEqual(connexion.status_code, 200)
            tech_client = APIClient()
            tech_client.credentials(HTTP_AUTHORIZATION=f"Bearer {connexion.data['access']}")
            changement = tech_client.post(
                f"{prefix}/auth/changer-mot-de-passe/",
                {"ancien_mot_de_passe": "ActivationSolide-2026!",
                 "nouveau_mot_de_passe": "NouveauMotSolide-2026!"},
                format="json",
            )
            self.assertEqual(changement.status_code, 200, changement.data)
            self.assertTrue(User.objects.get(pk=cible.pk).check_password("NouveauMotSolide-2026!"))

            refresh = inscription.data["refresh"]
            logout = admin_client.post(f"{prefix}/auth/logout/", {"refresh": refresh}, format="json")
            self.assertEqual(logout.status_code, 205)
            refresh_reutilise = self.client.post(
                f"{prefix}/auth/token/refresh/", {"refresh": refresh}, format="json",
            )
            self.assertEqual(refresh_reutilise.status_code, 401)

            desactivation = admin_client.post(f"{prefix}/auth/membres/{cible.pk}/desactiver/")
            self.assertEqual(desactivation.status_code, 200, desactivation.data)
            cible.refresh_from_db()
            self.assertFalse(cible.is_active)

            demande = self.client.post(
                f"{prefix}/auth/mot-de-passe-oublie/", {"email": f"{username}@example.test"}, format="json",
            )
            self.assertEqual(demande.status_code, 200, demande.data)
            self.assertFalse(demande.data["email_envoye"])
            lien = urlparse(demande.data["lien_reinitialisation"])
            jetons = parse_qs(lien.query)
            reinitialisation = self.client.post(
                f"{prefix}/auth/reinitialiser-mot-de-passe/",
                {"uid": jetons["uid"][0], "token": jetons["token"][0],
                 "nouveau_mot_de_passe": f"Reinitialise-{suffix}-2026!"},
                format="json",
            )
            self.assertEqual(reinitialisation.status_code, 200, reinitialisation.data)
            nouvelle_connexion = self.client.post(
                f"{prefix}/auth/token/",
                {"username": username, "password": f"Reinitialise-{suffix}-2026!"}, format="json",
            )
            self.assertEqual(nouvelle_connexion.status_code, 200)


class T24AnalyticsEtCabinetTests(APITestCase):
    def setUp(self):
        self.admin, self.cabinet = authentifier(
            self, role=Profil.Role.ADMIN, nom_cabinet="T24 4C", bareme=BAREME_TEST,
        )
        self.projet = Projet.objects.create(
            nom="Projet analytics v1", entreprise=self.cabinet, usage_batiment="habitation", nb_niveaux=1,
        )

    def test_analytics_cabinet_projet_staff_et_referentiel_sur_les_deux_prefixes(self):
        staff = User.objects.create_user("t24_staff_4c", password="unused", is_staff=True)
        for prefix in ("/api", "/api/v1"):
            cabinet = self.client.get(f"{prefix}/analytics/cabinet/")
            self.assertEqual(cabinet.status_code, 200)
            self.assertEqual(cabinet.data["projets"]["total"], 1)

            projet = self.client.get(f"{prefix}/analytics/projets/{self.projet.pk}/")
            self.assertEqual(projet.status_code, 200)
            self.assertIsInstance(projet.data, dict)
            self.assertTrue(projet.data)

            client_staff = APIClient()
            client_staff.force_authenticate(user=staff)
            analytics_staff = client_staff.get(f"{prefix}/analytics/staff/")
            self.assertEqual(analytics_staff.status_code, 200)
            self.assertIsInstance(analytics_staff.data, dict)

            referentiel = self.client.get(f"{prefix}/referentiel/")
            self.assertEqual(referentiel.status_code, 200)
            self.assertIn("limites_structuration", referentiel.data)

    def test_entreprise_put_patch_persistes_sur_les_deux_prefixes(self):
        for suffix, prefix in (("legacy", "/api"), ("v1", "/api/v1")):
            lecture = self.client.get(f"{prefix}/entreprise/")
            self.assertEqual(lecture.status_code, 200)
            self.assertEqual(lecture.data["id"], self.cabinet.pk)

            remplacement = self.client.put(
                f"{prefix}/entreprise/",
                {"nom": f"Cabinet PUT {suffix}", "telephone": "01020304", "email": "test@example.test"},
                format="json",
            )
            self.assertEqual(remplacement.status_code, 200, remplacement.data)
            self.cabinet.refresh_from_db()
            self.assertEqual(self.cabinet.nom, f"Cabinet PUT {suffix}")
            self.assertEqual(self.cabinet.telephone, "01020304")

            telephone = "0202" if suffix == "v1" else "0201"
            modification = self.client.patch(
                f"{prefix}/entreprise/", {"telephone": telephone}, format="json",
            )
            self.assertEqual(modification.status_code, 200, modification.data)
            self.cabinet.refresh_from_db()
            self.assertEqual(self.cabinet.telephone, telephone)


class T24ActionsProjetTests(APITestCase):
    def setUp(self):
        self.user, self.cabinet = authentifier(self, nom_cabinet="T24 actions", bareme=BAREME_TEST)
        self.projet = projet_grille(self.cabinet)

    def test_analyse_chainage_validation_plan_et_dqe_post_legacy_v1(self):
        for prefix in ("/api", "/api/v1"):
            analyse = self.client.get(f"{prefix}/projets/{self.projet.pk}/analyse-coherence/")
            self.assertEqual(analyse.status_code, 200, analyse.data)
            self.assertIsInstance(analyse.data, dict)

            chainage = self.client.get(f"{prefix}/projets/{self.projet.pk}/chainage_suggere/")
            self.assertEqual(chainage.status_code, 200, chainage.data)
            self.assertGreater(chainage.data["longueur_m"], 0)

            validation = self.client.post(f"{prefix}/projets/{self.projet.pk}/valider_plan_fondation/")
            self.assertEqual(validation.status_code, 200, validation.data)
            self.projet.refresh_from_db()
            self.assertTrue(self.projet.plan_fondation_valide)
            self.projet.plan_fondation_valide = False
            self.projet.save(update_fields=["plan_fondation_valide"])

            # Le DQE POST est appelé avec une trame réellement générée puis
            # validée dans la base de test; aucun résultat structurel n'est simulé.
            generation = self.client.post(f"{prefix}/projets/{self.projet.pk}/generer_trame/", {}, format="json")
            self.assertEqual(generation.status_code, 201, generation.data)
            self.projet.elements.update(statut=ElementStructurel.Statut.VALIDE)
            for element in self.projet.elements.all():
                element.resultat_valide = element.resultat_calcul
                element.save(update_fields=["resultat_valide"])
            dqe = self.client.post(
                f"{prefix}/projets/{self.projet.pk}/generer-dqe/", {"export": "pdf"}, format="json",
            )
            self.assertEqual(dqe.status_code, 200, getattr(dqe, "data", None))
            self.assertEqual(dqe["Content-Type"], "application/pdf")
            self.assertTrue(dqe.content.startswith(b"%PDF"))

    def test_variantes_repondent_sans_modifier_le_projet_sur_les_deux_prefixes(self):
        for prefix in ("/api", "/api/v1"):
            generation = self.client.post(f"{prefix}/projets/{self.projet.pk}/generer_trame/", {}, format="json")
            self.assertEqual(generation.status_code, 201, generation.data)
            avant = {
                "parametres": (self.projet.portee_x, self.projet.contrainte_sol_kn_m2),
                "elements": list(self.projet.elements.values_list("identifiant", "resultat_calcul", "statut")),
            }
            resultat = self.client.post(
                f"{prefix}/projets/{self.projet.pk}/variantes/",
                {"variantes": [{"nom": "Sol modifié", "modifications": {"contrainte_sol_kn_m2": 75}}]},
                format="json",
            )
            self.assertEqual(resultat.status_code, 200, resultat.data)
            self.assertEqual(len(resultat.data["variantes"]), 2)
            self.assertIsNone(resultat.data["variantes"][1]["erreur"])
            self.projet.refresh_from_db()
            apres = {
                "parametres": (self.projet.portee_x, self.projet.contrainte_sol_kn_m2),
                "elements": list(self.projet.elements.values_list("identifiant", "resultat_calcul", "statut")),
            }
            self.assertEqual(apres, avant)

    def test_validation_et_deverrouillage_element_persistes_sur_les_deux_prefixes(self):
        for prefix, repere in (("/api", "P-VALID-L"), ("/api/v1", "P-VALID-V1")):
            element = ElementStructurel.objects.create(
                projet=self.projet, identifiant=repere, type_element=ElementStructurel.TypeElement.POTEAU,
                resultat_calcul={"cote_cm": 25},
            )
            validation = self.client.post(f"{prefix}/elements/{element.pk}/valider/", {}, format="json")
            self.assertEqual(validation.status_code, 200, validation.data)
            element.refresh_from_db()
            self.assertEqual(element.statut, ElementStructurel.Statut.VALIDE)
            self.assertEqual(element.resultat_valide, {"cote_cm": 25})

            deverrouillage = self.client.post(f"{prefix}/elements/{element.pk}/deverrouiller/", {}, format="json")
            self.assertEqual(deverrouillage.status_code, 200, deverrouillage.data)
            element.refresh_from_db()
            self.assertEqual(element.statut, ElementStructurel.Statut.MODIFIE)
            self.assertIsNone(element.resultat_valide)


class T24ImportsV1Tests(APITestCase):
    def setUp(self):
        self.user, self.cabinet = authentifier(self, role=Profil.Role.INGENIEUR)
        OuvrageType.objects.create(
            entreprise=self.cabinet, lot="lot_01_terrassement", designation="Fouille en rigole",
            unite="m³", prix_unitaire=3500,
        )

    def test_apercu_et_confirmation_bibliotheque_legacy_v1(self):
        for prefix in ("/api", "/api/v1"):
            nombre_avant = OuvrageType.objects.count()
            apercu = self.client.post(
                f"{prefix}/ouvrages/importer/",
                {"fichier": SimpleUploadedFile("dqe.xlsx", classeur_test(),
                                                content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")},
                format="multipart",
            )
            self.assertEqual(apercu.status_code, 200, apercu.data)
            self.assertTrue(apercu.data["lignes"])
            self.assertEqual(OuvrageType.objects.count(), nombre_avant)

            confirmation = self.client.post(
                f"{prefix}/ouvrages/importer/confirmer/",
                {"source_prix": f"T24 {prefix}", "lignes": [{
                    "lot": "lot_09_menuiserie_bois", "designation": f"Porte T24 {prefix}", "unite": "u",
                    "prix_unitaire": 85000, "action": "creer",
                }]},
                format="json",
            )
            self.assertEqual(confirmation.status_code, 201, confirmation.data)
            self.assertEqual(confirmation.data["crees"], 1)
            ouvrage = OuvrageType.objects.get(designation=f"Porte T24 {prefix}")
            self.assertEqual(ouvrage.entreprise_id, self.cabinet.pk)
            self.assertEqual(ouvrage.cree_par_id, self.user.pk)


class T24CalculApiTests(APITestCase):
    def setUp(self):
        self.user, self.cabinet = authentifier(self, nom_cabinet="T24 calcul mock")
        self.projet = Projet.objects.create(
            nom="Projet calcul API", entreprise=self.cabinet, usage_batiment="habitation", nb_niveaux=1,
        )

    @patch("projets.services.calculations.dimensionner_poteau", return_value={
        "cote_cm": 25, "largeur_cm": 25, "profondeur_cm": 25,
    })
    def test_calcul_api_transmet_les_parametres_persiste_et_repond_sur_les_deux_prefixes(self, moteur):
        for prefix, repere in (("/api", "P-LEGACY"), ("/api/v1", "P-V1")):
            element = ElementStructurel.objects.create(
                projet=self.projet, identifiant=repere, type_element=ElementStructurel.TypeElement.POTEAU,
                charge_calculee=250, hauteur_poteau=3,
            )
            response = self.client.post(f"{prefix}/elements/{element.pk}/calculer/", {}, format="json")
            self.assertEqual(response.status_code, 200, response.data)
            self.assertEqual(response.data["resultat_calcul"]["cote_cm"], 25)
            element.refresh_from_db()
            self.assertEqual(element.resultat_calcul["cote_cm"], 25)
        self.assertEqual(moteur.call_count, 2)
        self.assertEqual(moteur.call_args_list[0].kwargs["charge_calculee"], 250)
        self.assertEqual(moteur.call_args_list[0].kwargs["hauteur_poteau"], 3)

    def test_calcul_poteau_reel_sur_un_cas_simple_prend_le_chemin_moteur_disponible(self):
        for prefix, repere in (("/api", "P-REEL-L"), ("/api/v1", "P-REEL-V1")):
            element = ElementStructurel.objects.create(
                projet=self.projet, identifiant=repere, type_element=ElementStructurel.TypeElement.POTEAU,
                charge_calculee=250, hauteur_poteau=3,
            )
            response = self.client.post(f"{prefix}/elements/{element.pk}/calculer/", {}, format="json")
            self.assertEqual(response.status_code, 200, response.data)
            self.assertGreater(response.data["resultat_calcul"]["cote_cm"], 0)
            element.refresh_from_db()
            self.assertEqual(element.resultat_calcul, response.data["resultat_calcul"])

    @patch("projets.services.calculations.dimensionner_poteau", side_effect=NotImplementedError("formule indisponible"))
    def test_indisponibilite_moteur_reste_503_sans_ecraser_un_resultat_sur_les_deux_prefixes(self, _moteur):
        for prefix, repere in (("/api", "P-ERR-LEGACY"), ("/api/v1", "P-ERR-V1")):
            initial = {"cote_cm": 20}
            element = ElementStructurel.objects.create(
                projet=self.projet, identifiant=repere, type_element=ElementStructurel.TypeElement.POTEAU,
                charge_calculee=250, hauteur_poteau=3, resultat_calcul=initial,
            )
            response = self.client.post(f"{prefix}/elements/{element.pk}/calculer/", {}, format="json")
            self.assertEqual(response.status_code, 503, response.data)
            element.refresh_from_db()
            self.assertEqual(element.resultat_calcul, initial)

    @patch("projets.services.calculations.dimensionner_poteau", return_value={
        "cote_cm": 30, "largeur_cm": 30, "profondeur_cm": 30,
    })
    def test_recalculer_projet_persiste_les_resultats_sur_legacy_et_v1(self, moteur):
        for prefix, repere in (("/api", "P-RECALC-L"), ("/api/v1", "P-RECALC-V1")):
            element = ElementStructurel.objects.create(
                projet=self.projet, identifiant=repere, type_element=ElementStructurel.TypeElement.POTEAU,
                charge_calculee=300, hauteur_poteau=3,
            )
            response = self.client.post(f"{prefix}/projets/{self.projet.pk}/recalculer/", {}, format="json")
            self.assertEqual(response.status_code, 200, response.data)
            resultat = response.data.get(element.pk, response.data.get(str(element.pk)))
            self.assertIsNotNone(resultat, response.data)
            self.assertTrue(resultat["ok"])
            self.assertEqual(resultat["resultat"]["cote_cm"], 30)
            element.refresh_from_db()
            self.assertEqual(element.resultat_calcul["cote_cm"], 30)
        self.assertGreaterEqual(moteur.call_count, 2)


class T24ImportIFCLegacyV1Tests(APITestCase):
    def setUp(self):
        self.user, self.cabinet = authentifier(self)
        self.ifc_bytes = _construire_ifc_bytes(xs=[0.0, 5.0, 10.0], ys=[0.0, 4.0])

    def test_apercu_et_confirmation_ifc_avec_stockage_temporaire_sur_les_deux_prefixes(self):
        with TemporaryDirectory(prefix="dqe-t24-ifc-") as media_root, override_settings(MEDIA_ROOT=media_root):
            for prefix in ("/api", "/api/v1"):
                projet = Projet.objects.create(
                    nom=f"IFC {prefix}", entreprise=self.cabinet, usage_batiment="habitation",
                    nb_niveaux=2, hauteur_etage=3, charge_exploitation=1.5,
                )
                url = f"{prefix}/projets/{projet.pk}/importer_plan/"
                apercu = self.client.post(
                    url,
                    {"fichier": SimpleUploadedFile("plan.ifc", self.ifc_bytes,
                                                    content_type="application/octet-stream")},
                    format="multipart",
                )
                self.assertEqual(apercu.status_code, 200, apercu.data)
                self.assertEqual((apercu.data["nb_travees_x"], apercu.data["nb_travees_y"]), (2, 1))
                self.assertEqual(projet.elements.count(), 0)

                confirmation = self.client.post(url, {"confirmer": "true"}, format="json")
                self.assertEqual(confirmation.status_code, 201, confirmation.data)
                projet.refresh_from_db()
                self.assertGreater(projet.elements.count(), 0)
                self.assertEqual(len(confirmation.data["elements"]), projet.elements.count())
