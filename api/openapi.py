"""Personnalisation des identifiants OpenAPI pour les alias conservés."""

from drf_spectacular.openapi import AutoSchema


class DQEAutoSchema(AutoSchema):
    """Rend distincts les operationId des deux alias DQE sans toucher aux routes."""

    def get_operation_id(self):
        operation_id = super().get_operation_id()
        normalized_path = self.path.rstrip("/")
        if normalized_path.endswith("/generer_dqe"):
            return f"{operation_id}_underscore_alias"
        if normalized_path.endswith("/generer-dqe"):
            return f"{operation_id}_hyphen_alias"
        if "/versions-dqe/{numero}" in normalized_path:
            return f"{operation_id}_version_detail"
        if normalized_path.endswith("/versions-dqe"):
            return f"{operation_id}_versions_liste"
        return operation_id


def postprocess_error_envelopes(generator, request, public, result):
    """Documente les erreurs API communes et leur enveloppe runtime additive."""
    schemas = result.setdefault("components", {}).setdefault("schemas", {})
    schemas["ApiError"] = {
        "type": "object",
        "required": ["code", "message", "fields", "details"],
        "properties": {
            "code": {"type": "string", "description": "Code stable de l'erreur."},
            "message": {"type": "string", "description": "Message lisible pour l'utilisateur."},
            "fields": {"type": "object", "additionalProperties": True},
            "details": {"type": "object", "additionalProperties": True},
        },
    }
    schemas["ApiErrorEnvelope"] = {
        "type": "object",
        "required": ["error"],
        "properties": {"error": {"$ref": "#/components/schemas/ApiError"}},
        "additionalProperties": True,
    }

    for path, path_item in result.get("paths", {}).items():
        for method, operation in path_item.items():
            if method.lower() not in {"get", "post", "put", "patch", "delete", "head", "options"}:
                continue
            responses = operation.setdefault("responses", {})

            # DRF valide les corps des écritures avant d'entrer dans la vue.
            # Ces erreurs 400 sont donc possibles même sur les opérations
            # CRUD dont la vue ne déclare explicitement que le succès.
            if operation.get("requestBody") and not path.rstrip("/").endswith(("/token", "/token/refresh", "/token/verify")):
                responses.setdefault("400", {
                    "description": "Données de requête invalides.",
                    "content": {"application/json": {"schema": {"type": "object", "additionalProperties": True}}},
                })

            # Les opérations protégées héritent de l'authentification et du
            # contrôle de membre/cabinet DRF. Une liste security qui contient
            # {} représente au contraire une route publique.
            security = operation.get("security")
            protected = bool(security) and not any(not item for item in security)
            if protected:
                responses.setdefault("401", {
                    "description": "Authentification requise ou jeton invalide.",
                    "content": {"application/json": {"schema": {"$ref": "#/components/schemas/ApiErrorEnvelope"}}},
                })
                responses.setdefault("403", {
                    "description": "Permission insuffisante ou utilisateur sans cabinet autorisé.",
                    "content": {"application/json": {"schema": {"$ref": "#/components/schemas/ApiErrorEnvelope"}}},
                })
            elif path.rstrip("/").endswith(("/token", "/token/refresh", "/token/verify")):
                # Les routes JWT sont publiques au sens où elles n'exigent
                # pas de jeton, mais un identifiant/jeton invalide renvoie 401.
                responses.setdefault("401", {
                    "description": "Identifiants ou jeton JWT invalides.",
                    "content": {"application/json": {"schema": {"$ref": "#/components/schemas/ApiErrorEnvelope"}}},
                })

            # Les paramètres de chemin identifient des ressources ou des
            # membres : le filtrage cabinet renvoie volontairement 404.
            if "{" in path:
                responses.setdefault("404", {
                    "description": "Ressource absente ou inaccessible dans le cabinet courant.",
                    "content": {"application/json": {"schema": {"$ref": "#/components/schemas/ApiErrorEnvelope"}}},
                })

            for response_code, response in operation.get("responses", {}).items():
                try:
                    is_error = int(response_code) >= 400
                except (TypeError, ValueError):
                    is_error = False
                if not is_error:
                    continue
                response_content = response.setdefault("content", {})
                response_content.setdefault("application/json", {})
                response_content["application/json"].setdefault(
                    "schema", {"$ref": "#/components/schemas/ApiErrorEnvelope"}
                )
                for media_type, media in response_content.items():
                    if media_type != "application/json":
                        continue
                    old_schema = media.get("schema")
                    envelope_ref = {"$ref": "#/components/schemas/ApiErrorEnvelope"}
                    if old_schema == envelope_ref:
                        continue
                    media["schema"] = (
                        {"allOf": [envelope_ref, old_schema]}
                        if old_schema
                        else envelope_ref
                    )
    return result
