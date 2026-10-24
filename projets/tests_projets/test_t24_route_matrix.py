"""Contrôles transversaux des opérations OpenAPI sur les deux préfixes.

Les cas nominatifs métier détaillés restent dans leurs modules respectifs.
Ce fichier vérifie systématiquement l'authentification, les frontières de
tenant et les permissions de rôle pour chaque méthode exposée.
"""

import json

from django.contrib.auth.models import User
from drf_spectacular.generators import SchemaGenerator
from rest_framework.test import APIClient, APITestCase

from projets.models import (
    CoucheCharge,
    ElementStructurel,
    OuvrageType,
    PosteComplementaire,
    Profil,
    Projet,
)
from projets.tests_projets.utils import authentifier, creer_cabinet, creer_membre


METHODES = {"get", "post", "put", "patch", "delete"}


def _est_protegee(operation):
    security = operation.get("security")
    return bool(security) and not any(not requirement for requirement in security)


def _url(path, prefix, objets):
    url = path.replace("/api/v1/", f"{prefix}/", 1)
    for param in ("id", "user_id", "numero"):
        if "{" + param + "}" in url:
            url = url.replace("{" + param + "}", str(objets.get(param, 999999)))
    return url


def _appeler(client, method, url):
    if method == "get":
        return client.get(url, HTTP_ACCEPT="application/json")
    return client.generic(
        method.upper(), url, data=json.dumps({}), content_type="application/json",
        HTTP_ACCEPT="application/json",
    )


class T24AuthentificationToutesOperationsTests(APITestCase):
    def test_chaque_operation_protegee_refuse_un_anonyme_sur_legacy_et_v1(self):
        operations_verifiees = 0
        for urlconf, prefix in (("api.legacy_urls", "/api"), ("api.v1_urls", "/api/v1")):
            schema = SchemaGenerator(urlconf=urlconf).get_schema(request=None, public=True)
            client = APIClient()
            for path, path_item in schema["paths"].items():
                for method, operation in path_item.items():
                    if method not in METHODES or not _est_protegee(operation):
                        continue
                    url = _url(path, prefix, {"id": 99999999, "user_id": 99999999})
                    response = _appeler(client, method, url)
                    self.assertIn(
                        response.status_code, (401, 403, 404),
                        f"Anonyme autorisé ou route incohérente: {method.upper()} {url} ({response.status_code})",
                    )
                    self.assertIn("error", response.data, f"Enveloppe absente: {method.upper()} {url}")
                    operations_verifiees += 1
        self.assertGreaterEqual(operations_verifiees, 140)


class T24IsolationToutesRoutesDetailTests(APITestCase):
    @classmethod
    def setUpTestData(cls):
        cls.cabinet_a = creer_cabinet("T24 tenant A")
        cls.cabinet_b = creer_cabinet("T24 tenant B")
        cls.user_a = creer_membre(cls.cabinet_a, "t24_owner_a", role=Profil.Role.ADMIN)
        cls.membre_a = creer_membre(cls.cabinet_a, "t24_member_a")
        cls.ingenieur_b = creer_membre(cls.cabinet_b, "t24_engineer_b", role=Profil.Role.INGENIEUR)
        cls.admin_b = creer_membre(cls.cabinet_b, "t24_admin_b", role=Profil.Role.ADMIN)
        cls.projet = Projet.objects.create(
            nom="Projet tenant A", entreprise=cls.cabinet_a,
            usage_batiment="habitation", nb_niveaux=1, hauteur_etage=3,
            nb_travees_x=1, nb_travees_y=1, portee_x=4, portee_y=4,
        )
        cls.element = ElementStructurel.objects.create(
            projet=cls.projet, identifiant="P1", type_element="poteau",
            hauteur_poteau=3, resultat_calcul={"cote_cm": 25},
        )
        cls.couche = CoucheCharge.objects.create(
            projet=cls.projet, designation="Couche A", epaisseur_cm=10,
            poids_volumique_kn_m3=20,
        )
        cls.poste = PosteComplementaire.objects.create(
            projet=cls.projet, lot="lot_15_divers", mode="simple",
            designation="Poste A", unite="u", quantite=1, prix_unitaire=100,
        )
        cls.ouvrage = OuvrageType.objects.create(
            entreprise=cls.cabinet_a, cree_par=cls.user_a,
            lot="lot_15_divers", designation="Ouvrage A", unite="u", prix_unitaire=100,
        )

    def test_chaque_operation_de_detail_isole_le_cabinet_sur_legacy_et_v1(self):
        identifiants = {
            "/projets/": self.projet.pk,
            "/elements/": self.element.pk,
            "/couches-charges/": self.couche.pk,
            "/postes-complementaires/": self.poste.pk,
            "/ouvrages/": self.ouvrage.pk,
            "/analytics/projets/": self.projet.pk,
            "/auth/membres/": self.membre_a.pk,
        }
        objets = {"id": self.projet.pk, "user_id": self.membre_a.pk}
        routes_verifiees = 0

        for urlconf, prefix in (("api.legacy_urls", "/api"), ("api.v1_urls", "/api/v1")):
            schema = SchemaGenerator(urlconf=urlconf).get_schema(request=None, public=True)
            for path, path_item in schema["paths"].items():
                if "{" not in path:
                    continue
                famille = next((racine for racine in identifiants if racine in path), None)
                if famille is None:
                    continue
                objets_route = dict(objets)
                if "{id}" in path:
                    objets_route["id"] = identifiants[famille]
                if "{user_id}" in path:
                    objets_route["user_id"] = identifiants[famille]

                # Les validations réservées à l'ingénieur/admin sont appelées
                # par un ingénieur externe afin d'atteindre le filtrage tenant.
                user = self.admin_b if "{user_id}" in path else self.ingenieur_b
                client = APIClient()
                client.force_authenticate(user=user)
                for method in path_item:
                    if method not in METHODES:
                        continue
                    url = _url(path, prefix, objets_route)
                    response = _appeler(client, method, url)
                    self.assertEqual(
                        response.status_code, 404,
                        f"Fuite ou comportement inattendu: {method.upper()} {url} -> {response.status_code}",
                    )
                    body = response.json()
                    self.assertIn(
                        "error", body,
                        f"Enveloppe 404 absente: {method.upper()} {url}: {body}",
                    )
                    self.assertEqual(body["error"]["code"], "NOT_FOUND")
                    routes_verifiees += 1

        self.assertGreaterEqual(routes_verifiees, 75)
        self.projet.refresh_from_db()
        self.element.refresh_from_db()
        self.assertEqual(self.projet.nom, "Projet tenant A")
        self.assertEqual(self.element.statut, ElementStructurel.Statut.PROPOSE)
        self.assertTrue(self.membre_a.is_active)

    def test_listes_et_analytics_restent_cantonnees_sur_legacy_et_v1(self):
        client = APIClient()
        client.force_authenticate(user=self.admin_b)
        for prefix in ("/api", "/api/v1"):
            for famille in (
                "projets", "elements", "couches-charges", "postes-complementaires", "ouvrages",
            ):
                response = client.get(f"{prefix}/{famille}/")
                self.assertEqual(response.status_code, 200, f"{prefix}/{famille}/")
                donnees = response.data.get("results", []) if isinstance(response.data, dict) else response.data
                ids = {ligne.get("id") for ligne in donnees}
                interdits = {self.projet.pk, self.element.pk, self.couche.pk, self.poste.pk, self.ouvrage.pk}
                self.assertTrue(ids.isdisjoint(interdits), f"Fuite de liste {prefix}/{famille}/: {ids}")

            membres = client.get(f"{prefix}/auth/membres/")
            self.assertEqual(membres.status_code, 200)
            usernames = {ligne["username"] for ligne in membres.data}
            self.assertTrue(usernames.isdisjoint({self.user_a.username, self.membre_a.username}))

            analytics = client.get(f"{prefix}/analytics/cabinet/")
            self.assertEqual(analytics.status_code, 200)
            self.assertEqual(analytics.data["projets"]["total"], 0)


class T24PermissionsRoleRoutesTests(APITestCase):
    def setUp(self):
        self.cabinet = creer_cabinet("T24 rôles")
        self.admin = creer_membre(self.cabinet, "t24_role_admin", role=Profil.Role.ADMIN)
        self.tech = creer_membre(self.cabinet, "t24_role_tech", role=Profil.Role.TECHNICIEN)
        self.projet = Projet.objects.create(
            nom="Projet rôles", entreprise=self.cabinet,
            usage_batiment="habitation", nb_niveaux=1, hauteur_etage=3,
        )
        self.element = ElementStructurel.objects.create(
            projet=self.projet, identifiant="P1", type_element="poteau",
            resultat_calcul={"cote_cm": 25},
        )
        self.ouvrage = OuvrageType.objects.create(
            entreprise=self.cabinet, cree_par=self.admin,
            lot="lot_15_divers", designation="Ouvrage rôle", unite="u", prix_unitaire=10,
        )

    def test_technicien_refuse_sur_toutes_les_methodes_a_role_restreint(self):
        routes = [
            ("get", "/auth/membres/"),
            ("post", "/auth/inviter/"),
            ("post", f"/auth/membres/{self.admin.pk}/desactiver/"),
            ("put", "/entreprise/"),
            ("patch", "/entreprise/"),
            ("delete", f"/projets/{self.projet.pk}/"),
            ("post", f"/projets/{self.projet.pk}/valider_plan_fondation/"),
            ("post", f"/elements/{self.element.pk}/valider/"),
            ("post", f"/elements/{self.element.pk}/deverrouiller/"),
            ("get", "/analytics/staff/"),
            ("post", "/ouvrages/"),
            ("put", f"/ouvrages/{self.ouvrage.pk}/"),
            ("patch", f"/ouvrages/{self.ouvrage.pk}/"),
            ("delete", f"/ouvrages/{self.ouvrage.pk}/"),
            ("post", "/ouvrages/importer/"),
            ("post", "/ouvrages/importer/confirmer/"),
        ]
        for prefix in ("/api", "/api/v1"):
            client = APIClient()
            client.force_authenticate(user=self.tech)
            for method, path in routes:
                response = _appeler(client, method, f"{prefix}{path}")
                self.assertIn(
                    response.status_code, (401, 403),
                    f"Rôle technicien autorisé: {method.upper()} {prefix}{path}",
                )
                self.assertEqual(
                    response.status_code, 403,
                    f"Rôle technicien non refusé: {method.upper()} {prefix}{path} -> {response.status_code}",
                )

        self.assertTrue(User.objects.get(pk=self.admin.pk).is_active)
        self.assertTrue(Projet.objects.filter(pk=self.projet.pk).exists())
        self.assertEqual(OuvrageType.objects.filter(entreprise=self.cabinet).count(), 1)


class T24CrudCompatibiliteOperationnelleTests(APITestCase):
    """Exerce les mutations CRUD principales sur chacun des deux préfixes."""

    def setUp(self):
        self.user, self.cabinet = authentifier(self, nom_cabinet="T24 CRUD v4b")
        self.projet = Projet.objects.create(
            nom="Projet CRUD parent", entreprise=self.cabinet, usage_batiment="habitation",
            nb_niveaux=1,
        )

    def test_projet_create_read_put_patch_delete_legacy_et_v1(self):
        for prefix in ("/api", "/api/v1"):
            creation = self.client.post(
                f"{prefix}/projets/",
                {"nom": f"Projet créé {prefix}", "usage_batiment": "habitation", "nb_niveaux": 2},
                format="json",
            )
            self.assertEqual(creation.status_code, 201, creation.data)
            project_id = creation.data["id"]
            self.assertEqual(Projet.objects.get(pk=project_id).entreprise_id, self.cabinet.pk)

            lecture = self.client.get(f"{prefix}/projets/{project_id}/")
            self.assertEqual(lecture.status_code, 200)
            self.assertEqual(lecture.data["nom"], creation.data["nom"])

            remplacement = self.client.put(
                f"{prefix}/projets/{project_id}/",
                {"nom": f"Projet PUT {prefix}", "usage_batiment": "habitation", "nb_niveaux": 3},
                format="json",
            )
            self.assertEqual(remplacement.status_code, 200, remplacement.data)
            self.assertEqual(remplacement.data["nb_niveaux"], 3)

            modification = self.client.patch(
                f"{prefix}/projets/{project_id}/", {"nom": f"Projet PATCH {prefix}"}, format="json",
            )
            self.assertEqual(modification.status_code, 200, modification.data)
            self.assertEqual(Projet.objects.get(pk=project_id).nom, f"Projet PATCH {prefix}")

            suppression = self.client.delete(f"{prefix}/projets/{project_id}/")
            self.assertEqual(suppression.status_code, 204)
            self.assertFalse(Projet.objects.filter(pk=project_id).exists())

    def test_element_create_read_put_patch_delete_legacy_et_v1(self):
        for prefix in ("/api", "/api/v1"):
            creation = self.client.post(
                f"{prefix}/elements/",
                {"projet": self.projet.pk, "type_element": "poteau", "identifiant": f"P-{prefix[-1]}",
                 "charge_calculee": 250, "hauteur_poteau": 3},
                format="json",
            )
            self.assertEqual(creation.status_code, 201, creation.data)
            element_id = creation.data["id"]
            self.assertEqual(ElementStructurel.objects.get(pk=element_id).projet_id, self.projet.pk)

            liste = self.client.get(f"{prefix}/elements/?projet={self.projet.pk}")
            self.assertEqual(liste.status_code, 200)
            self.assertIn(element_id, {row["id"] for row in liste.data})

            lecture = self.client.get(f"{prefix}/elements/{element_id}/")
            self.assertEqual(lecture.status_code, 200)
            self.assertEqual(lecture.data["identifiant"], creation.data["identifiant"])

            remplacement = self.client.put(
                f"{prefix}/elements/{element_id}/",
                {"projet": self.projet.pk, "type_element": "poteau", "identifiant": f"P-REP-{prefix[-1]}",
                 "charge_calculee": 300, "hauteur_poteau": 3},
                format="json",
            )
            self.assertEqual(remplacement.status_code, 200, remplacement.data)
            self.assertEqual(remplacement.data["charge_calculee"], 300)

            modification = self.client.patch(
                f"{prefix}/elements/{element_id}/", {"charge_calculee": 350}, format="json",
            )
            self.assertEqual(modification.status_code, 200, modification.data)
            self.assertEqual(ElementStructurel.objects.get(pk=element_id).charge_calculee, 350)

            suppression = self.client.delete(f"{prefix}/elements/{element_id}/")
            self.assertEqual(suppression.status_code, 204)
            self.assertFalse(ElementStructurel.objects.filter(pk=element_id).exists())
