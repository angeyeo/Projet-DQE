"""Vérification du consentement explicite avant une transmission à Gemini."""

import os
from django.utils import timezone

from rest_framework.response import Response
from rest_framework import status


CONSENTEMENT_REQUIS = "AI_CONSENT_REQUIRED"
CONSENTEMENT_VERSION = "t12-v2"
def consentement_valide(profil) -> bool:
    return bool(
        profil
        and profil.consentement_ia == "accepte"
        and profil.consentement_ia_version == CONSENTEMENT_VERSION
    )


def enregistrer_consentement(profil, decision: str):
    if decision not in {"accepte", "refuse"}:
        raise ValueError("La décision de consentement doit être 'accepte' ou 'refuse'.")
    profil.consentement_ia = decision
    profil.consentement_ia_version = CONSENTEMENT_VERSION
    profil.consentement_ia_date = timezone.now()
    profil.save(update_fields=["consentement_ia", "consentement_ia_version", "consentement_ia_date"])


def verifier_consentement(request, scope=None):
    """Retourne une réponse HTTP si Gemini est actif et le choix utilisateur invalide."""
    if os.getenv("LLM_PROVIDER", "").strip().lower() != "gemini":
        return None
    profil = getattr(request.user, "profil", None)
    if consentement_valide(profil):
        return None
    if profil and profil.consentement_ia == "refuse" and profil.consentement_ia_version == CONSENTEMENT_VERSION:
        detail = "L'assistance IA est désactivée dans vos paramètres ; aucune donnée n'a été envoyée."
        code = "AI_CONSENT_REFUSED"
        http_status = status.HTTP_403_FORBIDDEN
    else:
        detail = "Votre accord explicite est nécessaire avant la transmission à Google."
        code = CONSENTEMENT_REQUIS
        http_status = status.HTTP_428_PRECONDITION_REQUIRED
    return Response({"detail": detail, "code": code}, status=http_status)
