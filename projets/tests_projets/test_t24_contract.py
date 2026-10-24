"""Tests de caractérisation de l'API T24, sans changer ses réponses."""

import importlib
import os
import io
from unittest import mock

from django.test import override_settings
from django.urls import clear_url_caches, resolve, reverse
from drf_spectacular.generators import SchemaGenerator
from PIL import Image
from rest_framework.test import APIClient, APITestCase

from projets.models import CoucheCharge, ElementStructurel, Profil, Projet
from projets.tests_projets.utils import BAREME_TEST, authentifier, creer_cabinet, creer_membre


class ContratOpenAPITests(APITestCase):
    def setUp(self):
        self.user, self.entreprise = authentifier(self, nom_cabinet="T24 Contrat")
        self.projet = Projet.objects.create(
            nom="Projet contrat", entreprise=self.entreprise, usage_batiment="habitation",
        )

    def test_schema_version_et_endpoints_prioritaires(self):
        schema = SchemaGenerator(urlconf="api.legacy_urls").get_schema(request=None, public=True)
        self.assertEqual(schema["openapi"], "3.0.3")
        self.assertEqual(schema["info"]["version"], "1.0.0")
        paths = schema["paths"]
        attendus = {
            "/api/auth/token/": {"post"},
            "/api/auth/moi/consentement-ia/": {"post"},
            "/api/assistant/structurer-projet/": {"post"},
            "/api/referentiel/": {"get"},
            "/api/projets/": {"get", "post"},
            "/api/elements/": {"get", "post"},
            "/api/couches-charges/": {"get", "post"},
            "/api/ouvrages/importer/": {"post"},
        }
        for path, methods in attendus.items():
            self.assertIn(path, paths, path)
            self.assertTrue(methods <= paths[path].keys(), path)

    def test_operation_ids_sont_uniques_et_docs_exclues_du_schema(self):
        schema = SchemaGenerator(urlconf="api.legacy_urls").get_schema(request=None, public=True)
        operation_ids = [
            operation["operationId"]
            for path, item in schema["paths"].items()
            for method, operation in item.items()
            if method.lower() in {"get", "post", "put", "patch", "delete"}
        ]
        self.assertEqual(len(operation_ids), len(set(operation_ids)))
        self.assertNotIn("/api/schema/", schema["paths"])
        self.assertNotIn("/api/docs/", schema["paths"])

    def test_schema_documente_multipart_et_fichiers_binaires(self):
        schema = SchemaGenerator(urlconf="api.legacy_urls").get_schema(request=None, public=True)
        importer = schema["paths"][f"/api/projets/{{id}}/importer_plan/"]["post"]
        self.assertIn("multipart/form-data", importer["requestBody"]["content"])
        self.assertIn("application/json", importer["requestBody"]["content"])
        vision = schema["paths"][f"/api/projets/{{id}}/analyser_plan_image/"]["post"]
        self.assertIn("multipart/form-data", vision["requestBody"]["content"])
        self.assertNotIn("application/x-www-form-urlencoded", vision["requestBody"]["content"])
        excel = schema["paths"]["/api/ouvrages/importer/"]["post"]
        self.assertEqual(set(excel["requestBody"]["content"]), {"multipart/form-data"})
        plan = schema["paths"][f"/api/projets/{{id}}/plan_fondation/"]["get"]
        self.assertIn("application/pdf", plan["responses"]["200"]["content"])
        self.assertIn("application/dxf", plan["responses"]["200"]["content"])
        variantes_export = schema["paths"][f"/api/projets/{{id}}/generer-dqe/"]["get"]
        export_param = next(p for p in variantes_export["parameters"] if p["name"] == "export")
        self.assertEqual(set(export_param["schema"]["enum"]), {"pdf", "excel"})
        self.assertTrue(next(p for p in variantes_export["parameters"] if p["in"] == "path")["required"])
        generation_post = schema["paths"][f"/api/projets/{{id}}/generer-dqe/"]["post"]
        corps_export = generation_post["requestBody"]["content"]["application/json"]["schema"]
        self.assertIn("ExportRequest", str(corps_export))

    def test_schemas_decrivent_erreurs_communes_permissions_et_routes_publiques(self):
        for urlconf, prefix in (("api.legacy_urls", "/api/"), ("api.v1_urls", "/api/v1/")):
            schema = SchemaGenerator(urlconf=urlconf).get_schema(request=None, public=True)
            inscription = schema["paths"][f"{prefix}auth/inscription/"]["post"]
            self.assertIn(inscription.get("security"), (None, []))
            self.assertNotIn("401", inscription["responses"])
            jwt_obtain = schema["paths"][f"{prefix}token/"]["post"]
            self.assertIn("401", jwt_obtain["responses"])

            liste = schema["paths"][f"{prefix}projets/"]["get"]
            self.assertIn("401", liste["responses"])
            self.assertIn("403", liste["responses"])
            creation = schema["paths"][f"{prefix}projets/"]["post"]
            self.assertIn("400", creation["responses"])
            detail = schema["paths"][f"{prefix}projets/{{id}}/"]["get"]
            self.assertIn("404", detail["responses"])

            operation_ids = [
                operation["operationId"]
                for item in schema["paths"].values()
                for method, operation in item.items()
                if method.lower() in {"get", "post", "put", "patch", "delete"}
            ]
            self.assertEqual(len(operation_ids), len(set(operation_ids)))

            for item in schema["paths"].values():
                for method, operation in item.items():
                    if method.lower() not in {"get", "post", "put", "patch", "delete"}:
                        continue
                    for code, response in operation.get("responses", {}).items():
                        if int(code) < 400:
                            continue
                        json_schema = response.get("content", {}).get("application/json", {}).get("schema", {})
                        serialized = str(json_schema)
                        self.assertIn("ApiErrorEnvelope", serialized, f"{method} {code}")

            for path, item in schema["paths"].items():
                for method, operation in item.items():
                    if method.lower() not in {"get", "post", "put", "patch", "delete"}:
                        continue
                    for parameter in operation.get("parameters", []):
                        if parameter["in"] == "path":
                            self.assertTrue(parameter["required"], f"{method} {path}: {parameter['name']}")

            def examples_present(value):
                if isinstance(value, dict):
                    return any(key in {"example", "examples"} or examples_present(item)
                               for key, item in value.items())
                if isinstance(value, list):
                    return any(examples_present(item) for item in value)
                return False
            self.assertFalse(examples_present(schema))

            schema_text = str(schema)
            self.assertNotIn("PRIVATE_API_KEY", schema_text)
            self.assertNotIn("fixture-client", schema_text)

    def test_documentation_existe_uniquement_en_debug(self):
        # Django force DEBUG=False pendant les tests. Recharger l'URLconf sous
        # override_settings permet de caractériser les deux configurations.
        import backend.urls as root_urls

        try:
            with override_settings(DEBUG=True):
                importlib.reload(root_urls)
                clear_url_caches()
                self.assertEqual(resolve("/api/schema/").url_name, "schema")
                self.assertEqual(resolve("/api/docs/").url_name, "swagger-ui")
                self.assertEqual(resolve("/api/v1/schema/").url_name, "schema-v1")
                self.assertEqual(resolve("/api/v1/docs/").url_name, "swagger-ui-v1")
            importlib.reload(root_urls)
            clear_url_caches()
            pattern_names = [getattr(pattern, "name", None) for pattern in root_urls.urlpatterns]
            self.assertNotIn("schema", pattern_names)
            self.assertNotIn("swagger-ui", pattern_names)
            self.assertNotIn("schema-v1", pattern_names)
            self.assertNotIn("swagger-ui-v1", pattern_names)
        finally:
            # Ne pas laisser l'URLconf importé avec DEBUG=True pour les autres tests.
            importlib.reload(root_urls)
            clear_url_caches()

    def test_schema_v1_est_canonique_et_sans_routes_legacy(self):
        schema = SchemaGenerator(urlconf="api.v1_urls").get_schema(request=None, public=True)
        self.assertEqual(schema["info"]["version"], "1.0.0")
        paths = schema["paths"]
        self.assertIn("/api/v1/projets/", paths)
        self.assertIn("/api/v1/token/", paths)
        self.assertIn("/api/v1/auth/moi/consentement-ia/", paths)
        self.assertNotIn("/api/projets/", paths)
        importer = paths["/api/v1/projets/{id}/importer_plan/"]["post"]
        self.assertIn("multipart/form-data", importer["requestBody"]["content"])
        vision = paths["/api/v1/projets/{id}/analyser_plan_image/"]["post"]
        self.assertIn("multipart/form-data", vision["requestBody"]["content"])
        plan = paths["/api/v1/projets/{id}/plan_fondation/"]["get"]
        self.assertIn("application/pdf", plan["responses"]["200"]["content"])
        self.assertIn("application/dxf", plan["responses"]["200"]["content"])
        schemas = schema["components"]["schemas"]
        self.assertIn("ApiErrorEnvelope", schemas)
        erreur_validation = paths["/api/v1/assistant/structurer-projet/"]["post"]["responses"]["400"]
        self.assertIn(
            {"$ref": "#/components/schemas/ApiErrorEnvelope"},
            erreur_validation["content"]["application/json"]["schema"]["allOf"],
        )
        ids = [op["operationId"] for item in paths.values() for method, op in item.items()
               if method.lower() in {"get", "post", "put", "patch", "delete"}]
        self.assertEqual(len(ids), len(set(ids)))

    def test_schema_v1_reprend_toutes_les_routes_et_methodes_legacy(self):
        legacy = SchemaGenerator(urlconf="api.legacy_urls").get_schema(request=None, public=True)["paths"]
        v1 = SchemaGenerator(urlconf="api.v1_urls").get_schema(request=None, public=True)["paths"]
        v1_rebase = {path.replace("/api/v1/", "/api/", 1): operations for path, operations in v1.items()}
        self.assertEqual(set(legacy), set(v1_rebase))
        for path, operations in legacy.items():
            self.assertEqual(set(operations), set(v1_rebase[path]), path)

    def test_reverse_historique_et_namespace_v1(self):
        self.assertEqual(reverse("projet-list"), "/api/projets/")
        self.assertEqual(reverse("api_v1:projet-list"), "/api/v1/projets/")
        self.assertEqual(reverse("projet-generer-dqe", kwargs={"pk": 23}), "/api/projets/23/generer-dqe/")
        self.assertEqual(reverse("api_v1:projet-generer-dqe", kwargs={"pk": 23}),
                         "/api/v1/projets/23/generer-dqe/")


class CompatibiliteApiV1Tests(APITestCase):
    """Compare les alias v1 et legacy sur les mêmes vues et données isolées."""

    def setUp(self):
        self.user, self.entreprise = authentifier(
            self, nom_cabinet="T24 compatibilité", bareme=BAREME_TEST,
        )
        self.projet = Projet.objects.create(nom="Projet compatibilité", entreprise=self.entreprise)

    def comparer_json(self, method, legacy_path, v1_path, data=None, format="json", compare_data=True):
        legacy = getattr(self.client, method)(legacy_path, data, format=format) if data is not None else getattr(
            self.client, method
        )(legacy_path)
        v1 = getattr(self.client, method)(v1_path, data, format=format) if data is not None else getattr(
            self.client, method
        )(v1_path)
        self.assertEqual(legacy.status_code, v1.status_code)
        if compare_data and hasattr(legacy, "data"):
            self.assertEqual(legacy.data, v1.data)
        return legacy, v1

    def test_routes_et_reponses_crud_legacy_et_v1(self):
        legacy, v1 = self.comparer_json("get", "/api/projets/", "/api/v1/projets/")
        self.assertEqual(legacy.status_code, 200)
        self.assertEqual(len(legacy.data), 1)
        self.assertEqual(v1.data[0]["id"], self.projet.pk)

        for path in (f"/api/projets/{self.projet.pk}/", f"/api/v1/projets/{self.projet.pk}/"):
            self.assertEqual(resolve(path).func.cls.__name__, "ProjetViewSet")

    def test_jwt_et_profil_fonctionnent_sur_les_deux_prefixes(self):
        credentials = {"username": self.user.username, "password": "MotDePasse-Test-2026!"}
        legacy_token = APIClient().post("/api/token/", credentials, format="json")
        v1_token = APIClient().post("/api/v1/token/", credentials, format="json")
        self.assertEqual((legacy_token.status_code, v1_token.status_code), (200, 200))
        self.assertEqual(set(legacy_token.data), {"refresh", "access"})
        self.assertEqual(set(v1_token.data), {"refresh", "access"})

        legacy_client, v1_client = APIClient(), APIClient()
        legacy_client.credentials(HTTP_AUTHORIZATION=f"Bearer {legacy_token.data['access']}")
        v1_client.credentials(HTTP_AUTHORIZATION=f"Bearer {v1_token.data['access']}")
        legacy_me = legacy_client.get("/api/me/")
        v1_me = v1_client.get("/api/v1/me/")
        self.assertEqual((legacy_me.status_code, v1_me.status_code), (200, 200))
        self.assertEqual(legacy_me.data["id"], v1_me.data["id"])
        self.assertEqual(legacy_me.data["consentement_ia_valide"], v1_me.data["consentement_ia_valide"])

    def test_jwt_legacy_et_v1_obtain_refresh_verify(self):
        credentials = {"username": self.user.username, "password": "MotDePasse-Test-2026!"}
        for prefix in ("/api", "/api/v1"):
            for route in ("token", "auth/token"):
                obtenu = APIClient().post(f"{prefix}/{route}/", credentials, format="json")
                self.assertEqual(obtenu.status_code, 200, f"{prefix}/{route}/")
                self.assertEqual(set(obtenu.data), {"refresh", "access"})

                rafraichi = APIClient().post(
                    f"{prefix}/{route}/refresh/", {"refresh": obtenu.data["refresh"]}, format="json",
                )
                self.assertEqual(rafraichi.status_code, 200, f"{prefix}/{route}/refresh/")
                self.assertIn("access", rafraichi.data)

                if route == "token":
                    verification = APIClient().post(
                        f"{prefix}/{route}/verify/", {"token": rafraichi.data["access"]}, format="json",
                    )
                    self.assertEqual(verification.status_code, 200)
                    invalide = APIClient().post(
                        f"{prefix}/{route}/verify/", {"token": "jeton-invalide"}, format="json",
                    )
                    self.assertEqual(invalide.status_code, 401)

    def test_aliases_assistant_sont_fonctionnels_legacy_et_v1(self):
        from projets.models import ElementStructurel

        self.client.post("/api/auth/moi/consentement-ia/", {"decision": "accepte"}, format="json")
        element = ElementStructurel.objects.create(
            projet=self.projet, identifiant="T24-P1", type_element="poteau",
            resultat_calcul={"cote_cm": 25},
        )
        proposition = {
            "donnees": {"nombre_niveaux": 1}, "donnees_manquantes": [],
            "avertissements": [], "confirmation_requise": True, "source": "MOCK",
        }
        explication = {
            "explication": "Explication simulée.", "source": "MOCK",
            "explication_technique_disponible": True, "validation_humaine_requise": True,
        }
        with mock.patch("projets.views.structurer_description_projet", return_value=proposition) as structurer, \
                mock.patch("projets.views.expliquer_resultat_element", return_value=explication) as expliquer:
            for prefix in ("/api", "/api/v1"):
                for route in ("assistant/structurer-projet/", "assistant/structurer/"):
                    response = self.client.post(
                        f"{prefix}/{route}", {"description": "Projet simulé"}, format="json",
                    )
                    self.assertEqual(response.status_code, 200, response.data)
                    self.assertEqual(response.data["source"], "MOCK")
                    self.assertTrue(response.data["preuve_proposition"])
                for route in ("assistant/expliquer-element/", "assistant/expliquer/"):
                    response = self.client.post(
                        f"{prefix}/{route}", {"element_id": element.pk}, format="json",
                    )
                    self.assertEqual(response.status_code, 200, response.data)
                    self.assertEqual(response.data["source"], "MOCK")
        self.assertEqual(structurer.call_count, 4)
        self.assertEqual(expliquer.call_count, 4)

    def test_isolation_cabinet_identique_sur_les_deux_prefixes(self):
        autre_cabinet = creer_cabinet("Autre cabinet T24")
        autre_membre = creer_membre(autre_cabinet, "autre_membre_t24")
        self.client.force_authenticate(user=autre_membre)
        legacy, v1 = self.comparer_json(
            "get", f"/api/projets/{self.projet.pk}/", f"/api/v1/projets/{self.projet.pk}/",
        )
        self.assertEqual((legacy.status_code, v1.status_code), (404, 404))

    def test_t11_validation_identique_sur_les_deux_prefixes(self):
        body = {"nom": "Niveaux hors limites", "nb_niveaux": 21}
        legacy, v1 = self.comparer_json("post", "/api/projets/", "/api/v1/projets/", body)
        self.assertEqual(legacy.status_code, 400)

    def test_t12_consentement_et_blocage_ia_identiques(self):
        # Les tests de compatibilité voisins peuvent avoir consommé le quota
        # de throttling scoped de ces deux alias. Ici on caractérise le code
        # de consentement indépendamment de cet état global de cache.
        from django.core.cache import cache
        cache.clear()
        legacy, v1 = self.comparer_json(
            "post", "/api/auth/moi/consentement-ia/", "/api/v1/auth/moi/consentement-ia/",
            {"decision": "refuse"}, compare_data=False,
        )
        self.assertEqual(legacy.status_code, 200)
        self.assertEqual(legacy.data["consentement_ia"], "refuse")
        self.assertEqual(legacy.data["consentement_ia_valide"], v1.data["consentement_ia_valide"])

        with mock.patch.dict(os.environ, {"LLM_PROVIDER": "gemini"}), mock.patch(
            "projets.views.structurer_description_projet"
        ) as fournisseur:
            legacy, v1 = self.comparer_json(
                "post", "/api/assistant/structurer-projet/", "/api/v1/assistant/structurer-projet/",
                {"description": "Projet R+1"}, compare_data=False,
            )
        self.assertEqual(legacy.status_code, 403)
        self.assertEqual(legacy.data["code"], v1.data["code"])
        fournisseur.assert_not_called()

    def test_t10_preuve_de_proposition_disponible_en_v1_sans_appel_reel(self):
        self.client.post("/api/v1/auth/moi/consentement-ia/", {"decision": "accepte"}, format="json")
        proposition = {
            "source": "MOCK",
            "donnees": {"portee_x_m": 4},
            "donnees_manquantes": ["portee_y_m"],
            "avertissements": [],
            "confirmation_requise": True,
        }
        with mock.patch.dict(os.environ, {"LLM_PROVIDER": "gemini"}), mock.patch(
            "projets.views.structurer_description_projet", return_value=proposition
        ) as fournisseur:
            legacy, v1 = self.comparer_json(
                "post", "/api/assistant/structurer-projet/", "/api/v1/assistant/structurer-projet/",
                {"description": "Portée X 4 m"}, compare_data=False,
            )
        self.assertEqual(legacy.status_code, 200)
        self.assertEqual(legacy.data["source"], "MOCK")
        self.assertTrue(legacy.data["preuve_proposition"])
        self.assertEqual(legacy.data["donnees"], v1.data["donnees"])
        self.assertTrue(v1.data["preuve_proposition"])
        self.assertEqual(fournisseur.call_count, 2)

    def test_uploads_multipart_et_erreurs_identiques(self):
        from django.core.files.uploadedfile import SimpleUploadedFile

        for prefix in ("/api", "/api/v1"):
            response = self.client.post(
                f"{prefix}/projets/{self.projet.pk}/importer_plan/",
                {"fichier": SimpleUploadedFile("plan.txt", b"format invalide", "application/octet-stream")},
                format="multipart",
            )
            self.assertEqual(response.status_code, 400)
            if prefix == "/api":
                legacy_import = response.data
            else:
                self.assertEqual(response.data, legacy_import)

        self.client.post("/api/auth/moi/consentement-ia/", {"decision": "accepte"}, format="json")
        stream = io.BytesIO()
        Image.new("RGB", (2, 2), color="white").save(stream, format="PNG")
        image_bytes = stream.getvalue()
        with mock.patch(
            "projets.views.analyser_plan_2d",
            return_value={
                "annotations_lues": [], "textes_non_classes": [], "source": "MOCK",
                "validation_humaine_requise": True,
            },
        ) as analyser:
            for prefix in ("/api", "/api/v1"):
                response = self.client.post(
                    f"{prefix}/projets/{self.projet.pk}/analyser_plan_image/",
                    {"fichier": SimpleUploadedFile("plan.png", image_bytes, "image/png")},
                    format="multipart",
                )
                self.assertEqual(response.status_code, 200)
                self.assertEqual(response.data["source"], "MOCK")
                self.assertEqual(response.data["mode_import"], "VISION")
                analyser.assert_called()

    def test_exports_et_permissions_d_ingenieur_identiques(self):
        legacy, v1 = self.comparer_json(
            "get", f"/api/projets/{self.projet.pk}/plan_fondation/?export=pdf",
            f"/api/v1/projets/{self.projet.pk}/plan_fondation/?export=pdf",
        )
        self.assertEqual(legacy.status_code, 400)

        ElementStructurel.objects.create(
            projet=self.projet,
            type_element=ElementStructurel.TypeElement.POTEAU,
            identifiant="P1",
            hauteur_poteau=3.0,
            resultat_calcul={"cote_cm": 20, "largeur_cm": 20, "profondeur_cm": 20},
            resultat_valide={"cote_cm": 20, "largeur_cm": 20, "profondeur_cm": 20},
            statut=ElementStructurel.Statut.VALIDE,
        )
        for export, content_type, signature in (
            ("pdf", "application/pdf", b"%PDF"),
            ("excel", "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", b"PK"),
        ):
            legacy = self.client.get(f"/api/projets/{self.projet.pk}/generer-dqe/?export={export}")
            v1 = self.client.get(f"/api/v1/projets/{self.projet.pk}/generer-dqe/?export={export}")
            self.assertEqual((legacy.status_code, v1.status_code), (200, 200))
            self.assertEqual(legacy["Content-Type"], content_type)
            self.assertEqual(v1["Content-Type"], content_type)
            self.assertTrue(legacy.content.startswith(signature))
            self.assertTrue(v1.content.startswith(signature))

        for prefix in ("/api", "/api/v1"):
            underscore = f"{prefix}/projets/{self.projet.pk}/generer_dqe/"
            fichier = self.client.get(underscore, {"export": "pdf"})
            self.assertEqual(fichier.status_code, 200)
            self.assertEqual(fichier["Content-Type"], "application/pdf")
            self.assertTrue(fichier.content.startswith(b"%PDF"))
            fichier_post = self.client.post(underscore, {"export": "pdf"}, format="json")
            self.assertEqual(fichier_post.status_code, 200)
            self.assertEqual(fichier_post["Content-Type"], "application/pdf")
            self.assertTrue(fichier_post.content.startswith(b"%PDF"))

        for prefix in ("/api", "/api/v1"):
            projet_plan = Projet.objects.create(
                nom=f"Plan DXF {prefix}", nb_travees_x=1, nb_travees_y=1,
                portee_x=4.0, portee_y=3.0, usage_batiment="habitation",
                nb_niveaux=1, hauteur_etage=3.0, entreprise=self.entreprise,
            )
            generation = self.client.post(
                f"{prefix}/projets/{projet_plan.pk}/generer_trame/", {}, format="json",
            )
            self.assertEqual(generation.status_code, 201, generation.data)
            plan = self.client.get(
                f"{prefix}/projets/{projet_plan.pk}/plan_fondation/?export=dxf",
            )
            self.assertEqual(plan.status_code, 200, getattr(plan, "data", None))
            self.assertEqual(plan["Content-Type"], "application/dxf")
            self.assertIn(b"SECTION", plan.content)

        autre_user = creer_membre(self.entreprise, "technicien_v1", role=Profil.Role.TECHNICIEN)
        self.client.force_authenticate(user=autre_user)
        legacy, v1 = self.comparer_json(
            "post", f"/api/projets/{self.projet.pk}/valider_plan_fondation/",
            f"/api/v1/projets/{self.projet.pk}/valider_plan_fondation/", {},
        )
        self.assertEqual(legacy.status_code, v1.status_code)
        self.assertEqual(legacy.status_code, 403)


class ContratCouchesChargesTests(APITestCase):
    def setUp(self):
        self.user, self.entreprise = authentifier(self, nom_cabinet="T24 Couches")
        self.projet = Projet.objects.create(nom="Projet", entreprise=self.entreprise)

    def test_crud_couche_et_format_actuel(self):
        for prefix in ("/api", "/api/v1"):
            body = {
                "projet": self.projet.pk,
                "designation": f"Dalle béton {prefix}",
                "epaisseur_cm": 15,
                "poids_volumique_kn_m3": 25,
            }
            response = self.client.post(f"{prefix}/couches-charges/", body, format="json")
            self.assertEqual(response.status_code, 201, response.data)
            self.assertEqual(response.data["designation"], body["designation"])
            self.assertEqual(response.data["poids_surfacique_kn_m2"], 3.75)
            couche_id = response.data["id"]

            liste = self.client.get(f"{prefix}/couches-charges/")
            self.assertEqual(liste.status_code, 200)
            self.assertIn(couche_id, {row["id"] for row in liste.data})

            detail = self.client.get(f"{prefix}/couches-charges/{couche_id}/")
            self.assertEqual(detail.status_code, 200)
            self.assertEqual(detail.data["designation"], body["designation"])

            remplacement = self.client.put(
                f"{prefix}/couches-charges/{couche_id}/",
                {**body, "epaisseur_cm": 18}, format="json",
            )
            self.assertEqual(remplacement.status_code, 200, remplacement.data)
            self.assertEqual(remplacement.data["poids_surfacique_kn_m2"], 4.5)

            modification = self.client.patch(
                f"{prefix}/couches-charges/{couche_id}/", {"epaisseur_cm": 20}, format="json",
            )
            self.assertEqual(modification.status_code, 200)
            self.assertEqual(modification.data["poids_surfacique_kn_m2"], 5)

            suppression = self.client.delete(f"{prefix}/couches-charges/{couche_id}/")
            self.assertEqual(suppression.status_code, 204)
            self.assertFalse(CoucheCharge.objects.filter(pk=couche_id).exists())

    def test_couche_inaccessible_entre_cabinets_et_anonyme_refuse(self):
        couche = CoucheCharge.objects.create(
            projet=self.projet, designation="Enduit", epaisseur_cm=2, poids_volumique_kn_m3=20,
        )
        autre_cabinet = creer_cabinet("Autre cabinet")
        autre_membre = creer_membre(autre_cabinet, "autre_membre")
        self.client.force_authenticate(user=autre_membre)
        self.assertEqual(self.client.get(f"/api/couches-charges/{couche.pk}/").status_code, 404)

        self.client.force_authenticate(user=None)
        self.assertIn(self.client.get("/api/couches-charges/").status_code, (401, 403))
