import json
from .client import get_ai_client
from .prompts import PROMPT_STRUCTURATION
from .schemas import valider_donnees_extraites

def structurer_description_projet(description: str) -> dict:
    """
    Prend une description en langage naturel d'un projet de bâtiment,
    la transmet au LLM configuré, et valide les paramètres structurés
    extraits.

    Lève ValueError en cas d'erreur de saisie, de parsing JSON ou de validation.
    """
    if not description or not isinstance(description, str) or not description.strip():
        raise ValueError("La description fournie ne doit pas être vide.")

    # 1. Récupération du client LLM
    client = get_ai_client()

    # 2. Appel du LLM avec prompt de structuration
    prompt = PROMPT_STRUCTURATION.format(description=description.strip())
    raw_response = client.appeler_llm(prompt, forcer_json=True)

    # 3. Extraction et Parsing du JSON retourné
    cleaned_response = raw_response.strip()
    first_brace = cleaned_response.find("{")
    last_brace = cleaned_response.rfind("}")
    if first_brace != -1 and last_brace != -1 and last_brace > first_brace:
        cleaned_response = cleaned_response[first_brace:last_brace + 1]

    try:
        data = json.loads(cleaned_response)
    except json.JSONDecodeError as exc:
        raise ValueError("La réponse du LLM n'est pas un JSON valide.") from exc

    # 4. Validation des types et bornes
    validated_data = valider_donnees_extraites(data)

    # 5. Ajout d'une clé de décision pour l'ingénieur
    # On demande une confirmation si des données de base sont manquantes ou s'il y a des avertissements
    confirmation_requise = bool(validated_data["donnees_manquantes"]) or bool(validated_data["avertissements"])

    return {
        "donnees": {
            "nombre_niveaux": validated_data["nombre_niveaux"],
            "configuration": validated_data["configuration"],
            "usage": validated_data["usage"],
            "portee_m": validated_data["portee_m"],
            "hauteur_niveau_m": validated_data["hauteur_niveau_m"],
            "contrainte_sol_kn_m2": validated_data["contrainte_sol_kn_m2"],
        },
        "donnees_manquantes": validated_data["donnees_manquantes"],
        "avertissements": validated_data["avertissements"],
        "confirmation_requise": confirmation_requise,
    }
