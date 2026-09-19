import re
from .client import get_ai_client, MockAIClient, BaseAIClient
from .prompts import PROMPT_COHERENCE
from .explanations import TERMES_INTERDITS, extraire_nombres, json_compact

MESSAGE_VALIDATION_HUMAINE = (
    "Cette analyse nécessite une vérification humaine par l’ingénieur structure."
)

STATUTS_APPEL_LLM_AUTORISES = {"CRITIQUE", "ATTENTION", "INFORMATION"}


def _construire_fallback_local(analyse: dict) -> dict:
    """Conserve l'intégralité des signaux et décisions Python avec explication locale."""
    res = dict(analyse)
    res["explication_ia"] = None
    res["source_explication"] = "LOCAL"
    res["message_validation"] = MESSAGE_VALIDATION_HUMAINE
    res["validation_humaine_requise"] = True
    return res


def expliquer_analyse_coherence(
    analyse: dict,
    client: BaseAIClient | None = None,
) -> dict:
    """
    Rédige une explication textuelle facultative (via Gemini ou Mock) pour une analyse
    déterministe déjà produite par Python.

    Responsabilités :
    - Recevoir une analyse déterministe sous forme de dictionnaire (jamais d'objet model).
    - Ne jamais modifier les signaux ni le statut_analyse.
    - Ne jamais recalculer ni modifier les résultats métier.
    - Basculer automatiquement en source_explication = "LOCAL" en cas d'erreur LLM,
      de termes interdits, de nombres inventés ou si l'élément n'a pas de signaux.
    """
    if not isinstance(analyse, dict):
        raise ValueError("L'analyse de cohérence doit être fournie sous forme de dictionnaire.")

    statut_analyse = analyse.get("statut_analyse")
    signaux = analyse.get("signaux", [])

    # 1. Vérification des conditions d'appel LLM
    # Pas de LLM si aucun signal ou si le statut ne fait pas partie des statuts analysés
    if statut_analyse not in STATUTS_APPEL_LLM_AUTORISES or not signaux:
        return _construire_fallback_local(analyse)

    # 2. Préparation du prompt
    prompt = PROMPT_COHERENCE.format(
        identifiant=str(analyse.get("identifiant", "")).strip(),
        type_element=str(analyse.get("type_element", "")).strip(),
        statut_analyse=str(statut_analyse).strip(),
        signaux=json_compact(signaux),
    )

    # 3. Appel du service LLM (Gemini / Mock)
    try:
        ai_client = client or get_ai_client()
        raw_explanation = ai_client.appeler_llm(prompt, forcer_json=False)
    except Exception:
        # Fallback local transparent sans exception non gérée (client absent, clé absente, erreur réseau)
        return _construire_fallback_local(analyse)

    if not raw_explanation or not isinstance(raw_explanation, str):
        return _construire_fallback_local(analyse)

    explanation_text = raw_explanation.strip()
    explanation_lower = explanation_text.lower()

    # 4. Garde-fou 1 : Termes interdits
    if any(terme in explanation_lower for terme in TERMES_INTERDITS):
        return _construire_fallback_local(analyse)

    # 5. Garde-fou 2 : Anti-hallucination numérique
    payload_autorise = {
        "identifiant": analyse.get("identifiant"),
        "type_element": analyse.get("type_element"),
        "statut_analyse": analyse.get("statut_analyse"),
        "signaux": signaux,
    }
    nombres_autorises = extraire_nombres(json_compact(payload_autorise))
    if analyse.get("identifiant"):
        digits_in_id = re.findall(r"\d+", str(analyse.get("identifiant")))
        for d in digits_in_id:
            nombres_autorises.add(d)

    nombres_produits = extraire_nombres(explanation_text)
    nombres_inventes = nombres_produits - nombres_autorises
    if nombres_inventes:
        return _construire_fallback_local(analyse)

    # 6. Détermination de la source
    is_mock = isinstance(ai_client, MockAIClient)
    source_explication = "MOCK" if is_mock else "GEMINI"

    # 7. Résultat final enrichi
    res = dict(analyse)
    res["explication_ia"] = explanation_text
    res["source_explication"] = source_explication
    res["message_validation"] = MESSAGE_VALIDATION_HUMAINE
    res["validation_humaine_requise"] = True

    return res
