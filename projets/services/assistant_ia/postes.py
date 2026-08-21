import json
import logging

from .client import get_ai_client, MockAIClient
from .prompts import PROMPT_SUGGESTION_POSTE
from .schemas import valider_suggestion_poste, LOTS_VALIDES

logger = logging.getLogger(__name__)


# DETTE TECHNIQUE TEMPORAIRE : extraction JSON par accolades dupliquée entre parser.py et postes.py.
# À refactoriser dans un helper commun (ex: utils.py) lors d'un futur nettoyage global.
def extraire_et_parser_json(raw_response: str) -> dict:
    """
    Extrait le bloc JSON entre accolades et le parse.
    Lève ValueError si le JSON n'est pas valide ou mal formé.
    """
    cleaned = raw_response.strip()
    first_brace = cleaned.find("{")
    last_brace = cleaned.rfind("}")
    if first_brace != -1 and last_brace != -1 and last_brace > first_brace:
        cleaned = cleaned[first_brace:last_brace + 1]

    try:
        return json.loads(cleaned)
    except json.JSONDecodeError as exc:
        raise ValueError("La réponse du LLM n'est pas un JSON valide.") from exc


def suggerer_poste_complementaire(description: str) -> dict:
    """
    Analyse une description libre saisie par l'ingénieur et retourne
    une suggestion normalisée : désignation, unité, lot et confiance.

    Lève ValueError si la description est vide, non-chaîne, trop longue (>500),
    ou si le LLM renvoie des données invalides ou mal formées.
    """
    if not isinstance(description, str) or isinstance(description, bool) or not description.strip():
        raise ValueError("La description du poste ne doit pas être vide.")

    if len(description) > 500:
        raise ValueError("La description ne doit pas dépasser 500 caractères.")

    # 1. Récupération du client LLM
    client = get_ai_client()

    # 2. Formatage du prompt avec injection dynamique des lots depuis le modèle Django
    lots_str = ", ".join(f'"{lot}"' for lot in sorted(LOTS_VALIDES))
    prompt = PROMPT_SUGGESTION_POSTE.format(
        description=description.strip(),
        lots_valides=lots_str,
    )

    # 3. Appel du LLM
    raw_response = client.appeler_llm(prompt, forcer_json=True)

    # 4. Extraction et parsing du JSON
    data = extraire_et_parser_json(raw_response)

    # 5. Validation stricte via le schéma (lève ValueError sans correction silencieuse si invalide)
    validated = valider_suggestion_poste(data)

    # 6. Détermination de la source
    is_mock = isinstance(client, MockAIClient)
    source = "MOCK" if is_mock else "GEMINI"

    return {
        "suggestion": validated,
        "source": source,
    }