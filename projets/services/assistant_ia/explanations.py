import re
import json
from .client import get_ai_client, MockAIClient
from .prompts import PROMPT_EXPLICATION

FALLBACK_MESSAGE = (
    "Aucun résultat technique exploitable n'est disponible "
    "pour cet élément."
)

TERMES_INTERDITS = [
    "conforme",
    "validé",
    "sûr",
    "optimal",
    "respecte toutes les normes",
]


def extraire_nombres(texte: str) -> set[str]:
    """Extrait et normalise tous les nombres (entiers, décimaux, négatifs) présents dans une chaîne de texte."""
    cleaned = re.sub(r"(\d)\s+(\d)", r"\1\2", texte)
    cleaned = cleaned.replace(",", ".")
    matches = re.findall(r"(?<!\w)-?\d+(?:\.\d+)?", cleaned)
    normalized = set()
    for m in matches:
        normalized.add(m)
        try:
            val = float(m)
            if val.is_integer():
                normalized.add(str(int(val)))
            normalized.add(str(val))
        except ValueError:
            pass
    return normalized


def json_compact(obj: dict) -> str:
    """Retourne une chaîne JSON sans espaces inutiles pour le prompt."""
    return json.dumps(obj, ensure_ascii=False)


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

    # 4. Post-validation runtime : vérification des termes interdits
    explanation_lower = raw_explanation.lower()
    mandatory_phrase = "cette proposition doit être vérifiée et validée par l’ingénieur structure."
    text_to_check = explanation_lower.replace(mandatory_phrase, "")
    if any(terme in text_to_check for terme in TERMES_INTERDITS):
        return {
            "explication": "L’explication générée contient une affirmation de validation non autorisée.",
            "source": "FALLBACK_LOCAL",
            "explication_technique_disponible": False,
            "validation_humaine_requise": True,
        }

    # 5. Post-validation des valeurs numériques : vérification anti-hallucination
    payload_autorise = {
        "repere": str(repere),
        "type_element": str(type_element),
        "parametres": parametres_filtres,
        "resultats": resultats_filtres,
    }
    nombres_autorises = extraire_nombres(json_compact(payload_autorise))
    nombres_produits = extraire_nombres(raw_explanation)

    nombres_inventes = nombres_produits - nombres_autorises
    if nombres_inventes:
        return {
            "explication": "L’explication générée n’a pas pu être validée (présence de données non vérifiées).",
            "source": "FALLBACK_LOCAL",
            "explication_technique_disponible": False,
            "validation_humaine_requise": True,
        }

    # 6. Détermination de la source et format de retour
    is_mock = isinstance(client, MockAIClient)
    source = "MOCK" if is_mock else "GEMINI"

    return {
        "explication": raw_explanation.strip(),
        "source": source,
        "explication_technique_disponible": True,
        "validation_humaine_requise": True,
    }
