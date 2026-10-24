"""Erreur API additive : format canonique avec maintien du corps historique."""

from collections.abc import Mapping
import logging

from rest_framework.exceptions import ValidationError
from rest_framework.renderers import JSONRenderer
from rest_framework.response import Response


_CODES_PAR_STATUT = {
    400: "VALIDATION_ERROR",
    401: "AUTHENTICATION_REQUIRED",
    403: "PERMISSION_DENIED",
    404: "NOT_FOUND",
    405: "METHOD_NOT_ALLOWED",
    409: "CONFLICT",
    413: "PAYLOAD_TOO_LARGE",
    428: "PRECONDITION_REQUIRED",
    429: "RATE_LIMITED",
    500: "INTERNAL_SERVER_ERROR",
    502: "BAD_GATEWAY",
    503: "SERVICE_UNAVAILABLE",
    504: "GATEWAY_TIMEOUT",
}

_MESSAGES_SERVEUR = {
    500: "Une erreur interne est survenue. Réessayez plus tard.",
    502: "Le service externe est temporairement indisponible.",
    503: "Le service demandé est temporairement indisponible.",
    504: "Le service demandé met trop de temps à répondre. Réessayez plus tard.",
}

_STRUCTURES_METIER = {
    "champs_manquants", "problemes", "lignes", "elements_en_attente", "elements",
    "issues", "avertissements",
}
_CHAMPS_SENSIBLES = {
    "authorization", "access_token", "refresh_token", "token", "password",
    "mot_de_passe", "secret", "api_key", "llm_api_key", "traceback", "stack",
    "exception", "exception_type", "headers",
}
logger = logging.getLogger(__name__)


def _nettoyer_donnees(value):
    """Retire les propriétés sensibles lorsqu'une structure est recopiée."""
    if isinstance(value, Mapping):
        resultat = {}
        for key, item in value.items():
            compact_key = "".join(char for char in str(key).lower() if char.isalnum())
            sensible = compact_key in {
                "authorization", "accesstoken", "refreshtoken", "token", "password",
                "motdepasse", "secret", "apikey", "llmapikey", "traceback", "stack",
                "exception", "exceptiontype", "headers",
            }
            if not sensible:
                resultat[key] = _nettoyer_donnees(item)
        return resultat
    if isinstance(value, (list, tuple)):
        return [_nettoyer_donnees(item) for item in value]
    return value


def _texte(value):
    if isinstance(value, str):
        return value
    if isinstance(value, (list, tuple)):
        return " ".join(part for part in (_texte(item) for item in value) if part)
    return ""


def _message(data, status_code):
    if status_code >= 500:
        return _MESSAGES_SERVEUR.get(status_code, "Une erreur du serveur est survenue.")
    if isinstance(data, Mapping):
        canonical = data.get("error")
        if isinstance(canonical, Mapping) and _texte(canonical.get("message")):
            return _texte(canonical["message"])
        for key in ("detail", "erreur", "message"):
            result = _texte(data.get(key))
            if result:
                return result
        fragments = []
        for key, value in data.items():
            if key in {"code", "error", "details", "fields", *_STRUCTURES_METIER}:
                continue
            text = _texte(value)
            if text:
                fragments.append(f"{key} : {text}")
        if fragments:
            return " — ".join(fragments)
    elif _texte(data):
        return _texte(data)
    return {
        400: "Les données envoyées sont invalides.",
        401: "Authentification requise.",
        403: "Vous n'avez pas les droits nécessaires pour cette action.",
        404: "Ressource introuvable.",
        405: "Cette méthode n'est pas autorisée pour cette route.",
        409: "Cette action est incompatible avec l'état actuel de la ressource.",
        413: "Le fichier envoyé est trop volumineux.",
        428: "Un consentement préalable est requis.",
        429: "Trop de requêtes. Réessayez plus tard.",
    }.get(status_code, "La requête n'a pas pu être traitée.")


def _fields_and_details(data):
    if not isinstance(data, Mapping):
        return {}, {"legacy": _nettoyer_donnees(data)} if data is not None else {}

    explicit_fields = data.get("fields")
    if isinstance(explicit_fields, Mapping):
        fields = _nettoyer_donnees(explicit_fields)
    else:
        fields = {
            key: _nettoyer_donnees(value)
            for key, value in data.items()
            if key not in {
                "detail", "erreur", "message", "code", "error", "fields", "details",
                *_STRUCTURES_METIER,
            }
        }

    explicit_details = data.get("details")
    details = dict(_nettoyer_donnees(explicit_details)) if isinstance(explicit_details, Mapping) else {}
    for key in _STRUCTURES_METIER:
        if key in data:
            details[key] = _nettoyer_donnees(data[key])
    return fields, details


def envelopper_erreur(data, status_code, code_hint=None):
    """Ajoute `error` et conserve les clés historiques, sauf les détails 5xx."""
    if isinstance(data, Mapping):
        existing = data.get("error")
        if isinstance(existing, Mapping) and all(
            key in existing for key in ("code", "message", "fields", "details")
        ):
            return _nettoyer_donnees(data)
        legacy = dict(data)
    else:
        legacy = {"legacy": _nettoyer_donnees(data)} if data is not None else {}

    if status_code >= 500:
        safe_message = _MESSAGES_SERVEUR.get(status_code, "Une erreur du serveur est survenue.")
        # Les anciennes clés restent présentes, mais leurs valeurs ne peuvent
        # plus révéler de tracebacks, de chemins ou de réponses fournisseur.
        for key in ("detail", "erreur", "message"):
            if key in legacy:
                legacy[key] = safe_message
        fields, details = {}, {}
    else:
        safe_message = _message(data, status_code)
        fields, details = _fields_and_details(data)

    supplied_code = legacy.get("code")
    stable_code = supplied_code if isinstance(supplied_code, str) and supplied_code else (
        code_hint or _CODES_PAR_STATUT.get(status_code, f"HTTP_{status_code}")
    )
    legacy["error"] = {
        "code": stable_code,
        "message": safe_message,
        "fields": fields,
        "details": details,
    }
    return _nettoyer_donnees(legacy)


def api_exception_handler(exc, context):
    # Import tardif : DRF charge ses renderers pendant l'import de views.py,
    # qui référence ce handler via settings.REST_FRAMEWORK.
    from rest_framework.views import exception_handler as drf_exception_handler

    response = drf_exception_handler(exc, context)
    request = context.get("request")
    if request is None or not request.path.startswith("/api/"):
        return response
    if response is None:
        logger.error("Unhandled API exception", extra={"exception_type": type(exc).__name__})
        return Response(
            envelopper_erreur({"detail": _MESSAGES_SERVEUR[500]}, 500),
            status=500,
        )
    code_hint = "VALIDATION_ERROR" if isinstance(exc, ValidationError) else None
    response.data = envelopper_erreur(response.data, response.status_code, code_hint)
    return response


class CompatibleJSONRenderer(JSONRenderer):
    """Normalise également les Response d'erreur construites manuellement."""

    def render(self, data, accepted_media_type=None, renderer_context=None):
        renderer_context = renderer_context or {}
        response = renderer_context.get("response")
        request = renderer_context.get("request")
        if (
            response is not None
            and response.status_code >= 400
            and request is not None
            and request.path.startswith("/api/")
        ):
            data = envelopper_erreur(data, response.status_code)
        return super().render(data, accepted_media_type, renderer_context)
