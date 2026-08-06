import math

USAGES_VALIDES = ["HABITATION", "BUREAU", "COMMERCE", "INDUSTRIEL", "AUTRE"]


def valider_entier(value, nom_champ):
    """Rejette explicitement les booléens et valide que la valeur est un entier."""
    if isinstance(value, bool) or not isinstance(value, int):
        raise ValueError(f"{nom_champ} doit être un entier.")
    return value


def valider_nombre(value, nom_champ):
    """Rejette explicitement les booléens et valide que la valeur est un float fini."""
    if isinstance(value, bool):
        raise ValueError(f"{nom_champ} doit être un nombre.")

    try:
        nombre = float(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{nom_champ} doit être un nombre.") from exc

    if not math.isfinite(nombre):
        raise ValueError(f"{nom_champ} doit être un nombre fini.")

    return nombre


import re

def niveaux_depuis_configuration(configuration: str | None) -> int | None:
    """Déduit le nombre de niveaux théoriques depuis la chaîne de configuration (ex: 'R+2' -> 3, 'RDC' -> 1)."""
    if configuration is None:
        return None

    valeur = str(configuration).strip().upper()

    if valeur in {"RDC", "R+0"}:
        return 1

    match = re.fullmatch(r"R\+(\d+)", valeur)
    if not match:
        return None

    return int(match.group(1)) + 1


def valider_donnees_extraites(data: dict) -> dict:
    """
    Valide de manière rigoureuse les données extraites par le LLM
    pour s'assurer qu'elles respectent les types et limites du backend.
    """
    if not isinstance(data, dict):
        raise ValueError("La réponse de l'assistant doit être un objet JSON.")

    res = {
        "nombre_niveaux": None,
        "configuration": None,
        "usage": None,
        "portee_m": None,
        "hauteur_niveau_m": None,
        "contrainte_sol_kn_m2": None,
        "donnees_manquantes": [],
        "avertissements": [],
    }

    # 1. Validation de la configuration (ex: "R+2")
    config = data.get("configuration")
    if config is not None:
        res["configuration"] = str(config).strip()

    # 2. Validation de nombre_niveaux
    nombre_niveaux = data.get("nombre_niveaux")
    if nombre_niveaux is not None:
        val_int = valider_entier(nombre_niveaux, "nombre_niveaux")
        if val_int < 1 or val_int > 100:
            raise ValueError("Le nombre de niveaux doit être compris entre 1 et 100.")
        res["nombre_niveaux"] = val_int

    # 3. Validation croisée entre configuration et nombre_niveaux
    niveaux_config = niveaux_depuis_configuration(res["configuration"])
    if (
        niveaux_config is not None
        and res["nombre_niveaux"] is not None
        and niveaux_config != res["nombre_niveaux"]
    ):
        raise ValueError("La configuration et le nombre de niveaux sont incohérents.")

    # 3. Validation de l'usage
    usage = data.get("usage")
    if usage is not None:
        usage_str = str(usage).upper().strip()
        if usage_str in USAGES_VALIDES:
            res["usage"] = usage_str
        else:
            res["usage"] = "AUTRE"
            res["avertissements"].append(f"Usage '{usage}' inconnu, classé comme 'AUTRE'.")

    # 4. Validation de portee_m
    portee_m = data.get("portee_m")
    if portee_m is not None:
        val_float = valider_nombre(portee_m, "portee_m")
        if val_float <= 0:
            raise ValueError("La portée doit être strictement positive.")
        res["portee_m"] = val_float

    # 5. Validation de hauteur_niveau_m
    hauteur_niveau_m = data.get("hauteur_niveau_m")
    if hauteur_niveau_m is not None:
        val_float = valider_nombre(hauteur_niveau_m, "hauteur_niveau_m")
        if val_float <= 0:
            raise ValueError("La hauteur de niveau doit être strictement positive.")
        res["hauteur_niveau_m"] = val_float

    # 6. Validation de contrainte_sol_kn_m2
    contrainte_sol = data.get("contrainte_sol_kn_m2")
    if contrainte_sol is not None:
        val_float = valider_nombre(contrainte_sol, "contrainte_sol_kn_m2")
        if val_float <= 0:
            raise ValueError("La contrainte de sol doit être strictement positive.")
        res["contrainte_sol_kn_m2"] = val_float

    # 7. Données manquantes
    donnees_manquantes = data.get("donnees_manquantes")
    if isinstance(donnees_manquantes, list):
        res["donnees_manquantes"] = [str(item).strip() for item in donnees_manquantes]
    else:
        # Détection automatique si non fourni par le LLM
        for champ in ["nombre_niveaux", "usage", "portee_m"]:
            if res[champ] is None:
                res["donnees_manquantes"].append(champ)

    # 8. Avertissements
    avertissements = data.get("avertissements")
    if isinstance(avertissements, list):
        res["avertissements"].extend([str(item).strip() for item in avertissements])

    return res
