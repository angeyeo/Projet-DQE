import os
import re
import json
import urllib.request
import urllib.error
from abc import ABC, abstractmethod

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
                "Les dimensions calculées sont optimisées selon les règles BAEL. "
                "Cette proposition doit être vérifiée et validée par l’ingénieur structure avant son utilisation dans le DQE."
            )


class GeminiAIClient(BaseAIClient):
    def __init__(self, api_key: str, model: str = "gemini-1.5-flash", timeout: int = 20):
        self.api_key = api_key
        self.model = model
        self.timeout = timeout

    def appeler_llm(self, prompt: str, forcer_json: bool = False) -> str:
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{self.model}:generateContent?key={self.api_key}"
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
            headers={"Content-Type": "application/json"}
        )

        try:
            with urllib.request.urlopen(req, timeout=self.timeout) as response:
                res_data = json.loads(response.read().decode("utf-8"))
                text = res_data["candidates"][0]["content"]["parts"][0]["text"]
                return text
        except urllib.error.URLError as exc:
            raise RuntimeError(f"Erreur réseau Gemini : {str(exc)}") from exc
        except Exception as exc:
            raise RuntimeError(f"Erreur inattendue Gemini : {str(exc)}") from exc


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
        model_name = model if model else "gemini-1.5-flash"
        return GeminiAIClient(api_key, model=model_name, timeout=timeout)
    else:
        raise ValueError(f"Fournisseur d'IA '{provider}' non supporté. Choisissez parmi: mock, gemini.")
