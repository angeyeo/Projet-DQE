from .client import get_ai_client
from .prompts import PROMPT_EXPLICATION

def expliquer_resultat_element(element_data: dict) -> str:
    """
    Prend les données structurées d'un élément (entrées et résultats de calcul),
    filtre les valeurs None, et appelle le LLM.

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

    # Sécurité supplémentaire : si aucune donnée technique calculée n'est présente,
    # on renvoie une explication par défaut locale sans appeler le LLM.
    if not resultats_filtres:
        return "Le résultat détaillé de cet élément n’est pas disponible. Aucune explication technique ne peut être générée pour le moment."

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

    return raw_explanation.strip()


def json_compact(data) -> str:
    """Helper pour sérialiser en JSON compact pour les prompts."""
    try:
        import json
        return json.dumps(data, ensure_ascii=False)
    except Exception:
        return str(data)
