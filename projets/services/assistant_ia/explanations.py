from .client import get_ai_client, MockAIClient
from .prompts import PROMPT_EXPLICATION

FALLBACK_MESSAGE = (
    "Aucun résultat technique exploitable n'est disponible "
    "pour cet élément."
)


def expliquer_resultat_element(element_data: dict) -> dict:
    """
    Prend les données structurées d'un élément (entrées et résultats de calcul),
    filtre les valeurs None, et appelle le LLM.

    Retourne un dictionnaire structuré contenant l'explication, sa source,
    et des indicateurs de fiabilité pour le frontend.

    Lève ValueError si des champs requis de base sont absents.
    """
    if not isinstance(element_data, dict):
        raise ValueError("Les données de l'élément doivent être fournies sous forme de dictionnaire.")

    # Validation des champs obligatoires
    repere = element_data.get("repere")
    type_element = element_data.get("type_element")
    parametres = element_data.get("parametres")
    resultats = element_data.get("resultats")

    if not all(v is not None for v in [repere, type_element, parametres, resultats]):
        raise ValueError("Les champs 'repere', 'type_element', 'parametres' et 'resultats' sont obligatoires.")

    # Filtrer les valeurs None pour ne pas les transmettre au LLM
    parametres_filtres = {k: v for k, v in parametres.items() if v is not None}
    resultats_filtres = {k: v for k, v in resultats.items() if v is not None}

    # Sécurité : si aucune donnée technique calculée n'est présente,
    # on renvoie un fallback local sans appeler le LLM.
    if not resultats_filtres:
        return {
            "explication": FALLBACK_MESSAGE,
            "source": "FALLBACK_LOCAL",
            "explication_technique_disponible": False,
            "validation_humaine_requise": True,
        }

    # 1. Récupération du client LLM
    client = get_ai_client()

    # 2. Formatage du prompt d'explication
    prompt = PROMPT_EXPLICATION.format(
        repere=str(repere).strip(),
        type_element=str(type_element).upper().strip(),
        parametres=json_compact(parametres_filtres),
        resultats=json_compact(resultats_filtres)
    )

    # 3. Appel du LLM
    raw_explanation = client.appeler_llm(prompt, forcer_json=False)

    # 4. Détermination de la source réelle
    source = "MOCK" if isinstance(client, MockAIClient) else "GEMINI"

    return {
        "explication": raw_explanation.strip(),
        "source": source,
        "explication_technique_disponible": True,
        "validation_humaine_requise": True,
    }


def json_compact(data) -> str:
    """Helper pour sérialiser en JSON compact pour les prompts."""
    try:
        import json
        return json.dumps(data, ensure_ascii=False)
    except Exception:
        return str(data)
