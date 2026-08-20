import json
import logging

from .client import get_ai_client, MockAIClient
from .prompts import PROMPT_SUGGESTION_POSTE, PROMPT_RELECTURE_PLAN
from .schemas import valider_suggestion_poste, valider_relecture_plan
from .explanations import (
    extraire_nombres,
    TERMES_INTERDITS,
    json_compact,
)

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Fonctionnalité 1 : Suggestion automatique de poste complémentaire
# ---------------------------------------------------------------------------

def suggerer_poste_complementaire(description: str) -> dict:
    """
    Analyse une description libre saisie par l'ingénieur et retourne
    une suggestion normalisée : désignation, unité, lot et confiance.

    Lève ValueError si la description est vide ou si le LLM renvoie
    quelque chose d'invalide après validation.
    """
    if not description or not isinstance(description, str) or not description.strip():
        raise ValueError("La description du poste ne doit pas être vide.")

    # 1. Récupération du client LLM
    client = get_ai_client()

    # 2. Formatage du prompt
    prompt = PROMPT_SUGGESTION_POSTE.format(description=description.strip())

    # 3. Appel du LLM
    raw_response = client.appeler_llm(prompt, forcer_json=True)

    # 4. Extraction du JSON entre accolades (tolérance Markdown / texte autour)
    cleaned = raw_response.strip()
    first_brace = cleaned.find("{")
    last_brace = cleaned.rfind("}")
    if first_brace != -1 and last_brace != -1 and last_brace > first_brace:
        cleaned = cleaned[first_brace:last_brace + 1]

    try:
        data = json.loads(cleaned)
    except json.JSONDecodeError as exc:
        raise ValueError("La réponse du LLM n'est pas un JSON valide.") from exc

    # 5. Validation stricte via le schéma
    validated = valider_suggestion_poste(data)

    # 6. Détermination de la source
    is_mock = isinstance(client, MockAIClient)
    source = "MOCK" if is_mock else "GEMINI"

    return {
        "suggestion": validated,
        "source": source,
    }


# ---------------------------------------------------------------------------
# Fonctionnalité 2 : Relecture de cohérence du plan de fondation
# ---------------------------------------------------------------------------

FALLBACK_RELECTURE = {
    "alertes": [],
    "nombre_alertes": 0,
    "erreur": "relecture non disponible",
}


def relire_plan_fondation(semelles: list) -> dict:
    """
    Relit la liste des semelles du plan de fondation et émet des
    remarques de cohérence relative via le LLM.

    Paramètre semelles : liste de dicts contenant position, dimensions
    et poteau associé (format défini par le service plan_fondation).

    Retourne un dict {"alertes": [...], "nombre_alertes": int, "source": str}.
    En cas de dérive détectée (hallucination), retourne le fallback local.
    """
    if not semelles or not isinstance(semelles, list):
        return {
            "alertes": [],
            "nombre_alertes": 0,
            "source": "FALLBACK_LOCAL",
        }

    # 1. Récupération du client LLM
    client = get_ai_client()

    # 2. Sérialisation des semelles pour le prompt
    semelles_json_str = json_compact(semelles)

    # 3. Formatage du prompt
    prompt = PROMPT_RELECTURE_PLAN.format(semelles_json=semelles_json_str)

    # 4. Appel du LLM
    raw_response = client.appeler_llm(prompt, forcer_json=True)

    # 5. Extraction du JSON
    cleaned = raw_response.strip()
    first_brace = cleaned.find("{")
    last_brace = cleaned.rfind("}")
    if first_brace != -1 and last_brace != -1 and last_brace > first_brace:
        cleaned = cleaned[first_brace:last_brace + 1]

    try:
        data = json.loads(cleaned)
    except json.JSONDecodeError:
        logger.warning("Relecture plan : réponse LLM non parsable, fallback.")
        return {**FALLBACK_RELECTURE, "source": "FALLBACK_LOCAL"}

    # 6. Validation du schéma
    validated = valider_relecture_plan(data)

    # 7. Contrôle anti-hallucination : vérifier que chaque nombre
    #    mentionné dans les alertes est bien présent dans les données d'entrée
    nombres_autorises = extraire_nombres(semelles_json_str)
    for alerte in validated["alertes"]:
        nombres_alerte = extraire_nombres(alerte)
        nombres_inventes = nombres_alerte - nombres_autorises
        if nombres_inventes:
            logger.warning(
                "Relecture plan : hallucination détectée (nombres inventés : %s), fallback.",
                nombres_inventes,
            )
            return {**FALLBACK_RELECTURE, "source": "FALLBACK_LOCAL"}

    # 8. Filtrage des termes interdits dans les alertes
    phrase_validation = "cette proposition doit être vérifiée et validée par l'ingénieur structure."
    for alerte in validated["alertes"]:
        alerte_lower = alerte.lower().replace(phrase_validation, "")
        if any(terme in alerte_lower for terme in TERMES_INTERDITS):
            logger.warning("Relecture plan : terme interdit détecté, fallback.")
            return {**FALLBACK_RELECTURE, "source": "FALLBACK_LOCAL"}

    # 9. Source
    is_mock = isinstance(client, MockAIClient)
    source = "MOCK" if is_mock else "GEMINI"

    return {
        "alertes": validated["alertes"],
        "nombre_alertes": validated["nombre_alertes"],
        "source": source,
    }
