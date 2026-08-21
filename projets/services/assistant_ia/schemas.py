import math
from projets.models import PosteComplementaire

# Source unique des lots issus du modèle Django (pas de copie statique)
LOTS_VALIDES = set(PosteComplementaire.Lot.values)

# Constante IA pour la validation des unités (le modèle Django PosteComplementaire n'a pas de choices Enum pour l'unité)
UNITES_VALIDES = {"ens.", "m²", "m³", "kg", "ml", "u"}

CONFIANCES_VALIDES = {"haute", "moyenne", "basse"}


def niveaux_depuis_configuration(config_str: str) -> int | None:
    """Convertit 'R+N' en nombre de niveaux (R+0 -> 1, R+1 -> 2, etc.)."""
    if not config_str or not isinstance(config_str, str):
        return None
    s = config_str.strip().upper()
    if s.startswith("R+"):
        try:
            val = int(s[2:])
            if val >= 0:
                return val + 1
        except ValueError:
            pass
    return None


def valider_donnees_extraites(data: dict) -> dict:
    """
    Valide et assainit le dictionnaire extrait par le LLM.
    Lève ValueError si le format de base est invalide.
    """
    if not isinstance(data, dict):
        raise ValueError("La réponse de l'assistant doit être un objet JSON.")

    res = {
        "nombre_niveaux": None,
        "configuration": None,
        "usage": "AUTRE",
        "portee_m": None,
        "hauteur_niveau_m": None,
        "contrainte_sol_kn_m2": None,
        "donnees_manquantes": [],
        "avertissements": [],
    }

    # 1. Nombre de niveaux & Configuration
    nb_niveaux = data.get("nombre_niveaux")
    config = data.get("configuration")

    if isinstance(nb_niveaux, (int, float)) and not isinstance(nb_niveaux, bool):
        if not math.isnan(nb_niveaux) and not math.isinf(nb_niveaux):
            val_int = int(nb_niveaux)
            if val_int >= 1:
                res["nombre_niveaux"] = val_int

    if isinstance(config, str) and config.strip():
        config_clean = config.strip().upper()
        res["configuration"] = config_clean
        nb_depuis_config = niveaux_depuis_configuration(config_clean)
        if nb_depuis_config is not None:
            res["nombre_niveaux"] = nb_depuis_config

    if res["nombre_niveaux"] is None:
        res["donnees_manquantes"].append("nombre_niveaux")
    elif res["configuration"] is None:
        res["configuration"] = f"R+{res['nombre_niveaux'] - 1}"

    # 2. Usage
    usage_str = str(data.get("usage") or "").strip().upper()
    usages_valides = {"HABITATION", "BUREAU", "COMMERCE", "INDUSTRIEL", "AUTRE"}
    if usage_str in usages_valides:
        res["usage"] = usage_str
    else:
        res["usage"] = "AUTRE"

    # 3. Portée (m)
    portee = data.get("portee_m")
    if isinstance(portee, (int, float)) and not isinstance(portee, bool):
        if not math.isnan(portee) and not math.isinf(portee) and portee > 0:
            res["portee_m"] = round(float(portee), 2)

    if res["portee_m"] is None:
        res["donnees_manquantes"].append("portee_m")

    # 4. Hauteur niveau (m)
    hauteur = data.get("hauteur_niveau_m")
    if isinstance(hauteur, (int, float)) and not isinstance(hauteur, bool):
        if not math.isnan(hauteur) and not math.isinf(hauteur) and hauteur > 0:
            res["hauteur_niveau_m"] = round(float(hauteur), 2)

    # 5. Contrainte sol (kN/m²)
    sol = data.get("contrainte_sol_kn_m2")
    if isinstance(sol, (int, float)) and not isinstance(sol, bool):
        if not math.isnan(sol) and not math.isinf(sol) and sol > 0:
            res["contrainte_sol_kn_m2"] = round(float(sol), 2)

    # 6. Synchronisation des données manquantes transmises par le LLM
    donnees_manquantes_llm = data.get("donnees_manquantes")
    if isinstance(donnees_manquantes_llm, list):
        for item in donnees_manquantes_llm:
            item_str = str(item).strip()
            if item_str and item_str not in res["donnees_manquantes"]:
                res["donnees_manquantes"].append(item_str)

    # 7. Avertissements
    avertissements = data.get("avertissements")
    if isinstance(avertissements, list):
        res["avertissements"].extend([str(item).strip() for item in avertissements])

    return res


def valider_suggestion_poste(data: dict) -> dict:
    """
    Valide strictement la suggestion de poste renvoyée par le LLM.
    Chaque champ doit être explicitement de type string (str). Aucune conversion automatique (ex: str()) n'est tolérée.
    Lève ValueError si l'un des champs est absent, de mauvais type, vide ou hors bornes autorisées.
    """
    if not isinstance(data, dict):
        raise ValueError("La réponse de l'assistant doit être un objet JSON.")

    designation = data.get("designation")
    if not isinstance(designation, str) or isinstance(designation, bool):
        raise ValueError("Le champ 'designation' doit être une chaîne de caractères (str).")
    designation = designation.strip()
    if not designation:
        raise ValueError("La suggestion de l'assistant doit contenir une désignation non vide.")

    unite = data.get("unite")
    if not isinstance(unite, str) or isinstance(unite, bool):
        raise ValueError("Le champ 'unite' doit être une chaîne de caractères (str).")
    unite = unite.strip().lower()
    if unite not in UNITES_VALIDES:
        raise ValueError(f"L'unité suggérée '{unite}' est invalide. Unités autorisées : {sorted(UNITES_VALIDES)}")

    lot_suggere = data.get("lot_suggere")
    if not isinstance(lot_suggere, str) or isinstance(lot_suggere, bool):
        raise ValueError("Le champ 'lot_suggere' doit être une chaîne de caractères (str).")
    lot_suggere = lot_suggere.strip()
    if lot_suggere not in LOTS_VALIDES:
        raise ValueError(f"Le lot suggéré '{lot_suggere}' est invalide. Lots autorisés issus de PosteComplementaire.Lot.")

    confiance = data.get("confiance")
    if not isinstance(confiance, str) or isinstance(confiance, bool):
        raise ValueError("Le champ 'confiance' doit être une chaîne de caractères (str).")
    confiance = confiance.strip().lower()
    if confiance not in CONFIANCES_VALIDES:
        raise ValueError(f"Le niveau de confiance '{confiance}' est invalide. Niveaux autorisés : {sorted(CONFIANCES_VALIDES)}")

    return {
        "designation": designation,
        "unite": unite,
        "lot_suggere": lot_suggere,
        "confiance": confiance,
    }