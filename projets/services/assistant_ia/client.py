import os
import re
import json
import urllib.request
import urllib.error
from abc import ABC, abstractmethod

class LLMServiceError(Exception):
    """Exception levée en cas de défaillance contrôlée du service LLM externe."""
    def __init__(self, message: str, code: str = "LLM_PROVIDER_ERROR", status_code: int = 502):
        super().__init__(message)
        self.code = code
        self.status_code = status_code


class BaseAIClient(ABC):
    @abstractmethod
    def appeler_llm(self, prompt: str, forcer_json: bool = False) -> str:
        """Envoie la requête brute au fournisseur LLM et retourne le texte brut."""
        pass


class MockAIClient(BaseAIClient):
    """
    Client de simulation déterministe locale.
    Utile pour les tests unitaires et le développement déconnecté sans clé API.
    """
    def appeler_llm(self, prompt: str, forcer_json: bool = False) -> str:
        if forcer_json:
            # Extraction de la description utilisateur depuis le prompt
            description = prompt
            parts = prompt.split("Description du projet :")
            if len(parts) > 1:
                description = parts[-1].strip().strip('"')

            description = description.lower()
            # Détection du nombre de niveaux (R+2, R+3, R+0, etc.)
            nb_niveaux = 1
            config = "R+0"
            match_r = re.search(r"r\+(\d+)", description)
            if match_r:
                r_val = int(match_r.group(1))
                nb_niveaux = r_val + 1
                config = f"R+{r_val}"
            else:
                match_niv = re.search(r"(\d+)\s*niveaux", description)
                if match_niv:
                    nb_niveaux = int(match_niv.group(1))
                    config = f"R+{nb_niveaux - 1}"

            # Détection de l'usage
            usage = "AUTRE"
            if "commerc" in description:
                usage = "COMMERCE"
            elif "habit" in description or "résidentiel" in description:
                usage = "HABITATION"
            elif "bureau" in description:
                usage = "BUREAU"
            elif "indust" in description:
                usage = "INDUSTRIEL"

            # Détection de la portée
            portee = None
            match_portee = re.search(r"portée(?:s)? de (\d+(?:\.\d+)?)", description)
            if not match_portee:
                match_portee = re.search(r"(\d+(?:\.\d+)?)\s*mètre", description)
            if match_portee:
                portee = float(match_portee.group(1))

            # Détection de la contrainte de sol
            sol = None
            match_sol = re.search(r"sol de (\d+(?:\.\d+)?)", description)
            if match_sol:
                sol = float(match_sol.group(1))

            data = {
                "nombre_niveaux": nb_niveaux,
                "configuration": config,
                "usage": usage,
                "portee_m": portee,
                "hauteur_niveau_m": None,
                "contrainte_sol_kn_m2": sol,
                "donnees_manquantes": [],
                "avertissements": [],
            }

            # Remplissage automatique des données manquantes pour le mock
            for champ in ["nombre_niveaux", "usage", "portee_m"]:
                if data[champ] is None:
                    data["donnees_manquantes"].append(champ)

            # Avertissement par défaut pour le sol
            if data["contrainte_sol_kn_m2"] is None:
                data["avertissements"].append("La contrainte admissible du sol doit être confirmée par une étude géotechnique.")

            return json.dumps(data)

        else:
            # Simulation d'explication
            repere = "E1"
            match_rep = re.search(r"Repère : (\w+)", prompt)
            if match_rep:
                repere = match_rep.group(1)

            type_elem = "élément"
            match_type = re.search(r"Type d'élément : (\w+)", prompt)
            if match_type:
                type_elem = match_type.group(1).lower()

            return (
                f"Le {type_elem} {repere} a été pré-dimensionné pour répondre aux contraintes du projet. "
                "Les dimensions calculées sont calculées selon les règles BAEL. "
                "Cette proposition doit être vérifiée et validée par l’ingénieur structure."
            )


class GeminiAIClient(BaseAIClient):
    def __init__(self, api_key: str, model: str = "gemini-3.5-flash", timeout: int = 20):
        self.api_key = api_key
        self.model = model
        self.timeout = timeout

    def appeler_llm(self, prompt: str, forcer_json: bool = False) -> str:
        # Sécurité : la clé d'API est transmise uniquement via l'en-tête HTTP x-goog-api-key (jamais dans l'URL)
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{self.model}:generateContent"
        payload = {
            "contents": [{
                "parts": [{"text": prompt}]
            }]
        }
        if forcer_json:
            payload["generationConfig"] = {"responseMimeType": "application/json"}

        req_data = json.dumps(payload).encode("utf-8")
        req = urllib.request.Request(
            url,
            data=req_data,
            headers={
                "Content-Type": "application/json",
                "x-goog-api-key": self.api_key
            },
            method="POST"
        )

        max_bytes = int(os.getenv("LLM_MAX_RESPONSE_BYTES", "65536"))

        try:
            with urllib.request.urlopen(req, timeout=self.timeout) as response:
                raw_bytes = response.read(max_bytes + 1)
                if len(raw_bytes) > max_bytes:
                    raise LLMServiceError(
                        "La réponse du service LLM dépasse la taille maximale autorisée.",
                        code="LLM_RESPONSE_TOO_LARGE",
                        status_code=502
                    )
                res_data = json.loads(raw_bytes.decode("utf-8"))
                text = res_data["candidates"][0]["content"]["parts"][0]["text"]
                return text
        except LLMServiceError:
            raise
        except urllib.error.HTTPError as exc:
            if exc.code == 429:
                raise LLMServiceError(
                    "Le quota du service LLM est temporairement épuisé.",
                    code="LLM_QUOTA_EXCEEDED",
                    status_code=503
                ) from None
            elif exc.code in (401, 403):
                raise LLMServiceError(
                    "Le service d'assistance IA est temporairement indisponible (erreur de configuration serveur).",
                    code="LLM_PROVIDER_AUTH_ERROR",
                    status_code=502
                ) from None
            raise LLMServiceError(
                f"Le fournisseur LLM a retourné une erreur HTTP {exc.code}.",
                code="LLM_PROVIDER_ERROR",
                status_code=502
            ) from None
        except (urllib.error.URLError, TimeoutError) as exc:
            err_str = str(exc).lower()
            if "timed out" in err_str:
                raise LLMServiceError(
                    "Le délai d'attente de réponse du service LLM a expiré.",
                    code="LLM_TIMEOUT",
                    status_code=504
                ) from None
            raise LLMServiceError(
                "Le service LLM est temporairement indisponible.",
                code="LLM_UNAVAILABLE",
                status_code=503
            ) from None
        except Exception as exc:
            raise LLMServiceError(
                "Une erreur inattendue est survenue lors de l'accès au service LLM.",
                code="LLM_UNEXPECTED_ERROR",
                status_code=502
            ) from None


def get_ai_client() -> BaseAIClient:
    """Instancie le client LLM selon les variables d'environnement."""
    provider = os.getenv("LLM_PROVIDER", "mock").strip().lower()
    api_key = os.getenv("LLM_API_KEY", "").strip()
    model = os.getenv("LLM_MODEL", "").strip()

    try:
        timeout = int(os.getenv("LLM_TIMEOUT_SECONDS", "20"))
    except ValueError:
        timeout = 20

    if provider == "mock" or not provider:
        return MockAIClient()

    if not api_key:
        raise ValueError(f"La clé API (LLM_API_KEY) est requise pour le fournisseur '{provider}'.")

    if provider == "gemini":
        model_name = model if model else "gemini-3.5-flash"
        return GeminiAIClient(api_key, model=model_name, timeout=timeout)
    else:
        raise ValueError(f"Fournisseur d'IA '{provider}' non supporté. Choisissez parmi: mock, gemini.")
