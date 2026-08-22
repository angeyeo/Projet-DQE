import math
import re
from projets.models import PosteComplementaire

USAGES_VALIDES = ["HABITATION", "BUREAU", "COMMERCE", "INDUSTRIEL", "AUTRE"]

# Source unique des lots issus du modèle Django (pas de copie statique)
LOTS_VALIDES = set(PosteComplementaire.Lot.values)

# Constante IA pour la validation des unités (le modèle Django PosteComplementaire n'a pas de choices Enum pour l'unité)
UNITES_VALIDES = {"ens.", "m²", "m³", "kg", "ml", "u"}

CONFIANCES_VALIDES = {"haute", "moyenne", "basse"}


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


def valider_reponse_ocr(data: dict) -> dict:
    """
    Valide strictement le schéma JSON brut de la réponse OCR retournée par Gemini.
    Vérifie que la structure contient 'annotations_lues' et 'textes_non_classes'
    avec les types et contraintes appropriés. Les champs inconnus sont ignorés.
    """
    if not isinstance(data, dict):
        raise ValueError("La réponse de l'assistant doit être un objet JSON.")

    annotations = data.get("annotations_lues")
    if not isinstance(annotations, list):
        raise ValueError("Le champ 'annotations_lues' doit être une liste.")

    annotations_valides = []
    for idx, item in enumerate(annotations):
        if not isinstance(item, dict):
            raise ValueError(f"L'élément à l'index {idx} de 'annotations_lues' doit être un objet JSON (dict).")

        texte_lu = item.get("texte_lu")
        if not isinstance(texte_lu, str) or isinstance(texte_lu, bool):
            raise ValueError(f"Le champ 'texte_lu' de l'élément à l'index {idx} doit être une chaîne de caractères (str).")
        texte_lu = texte_lu.strip()
        if not texte_lu:
            raise ValueError(f"Le champ 'texte_lu' de l'élément à l'index {idx} ne doit pas être vide.")

        repere = item.get("repere")
        if not isinstance(repere, str) or isinstance(repere, bool):
            raise ValueError(f"Le champ 'repere' de l'élément à l'index {idx} doit être une chaîne de caractères (str).")
        repere = repere.strip()
        if not repere:
            raise ValueError(f"Le champ 'repere' de l'élément à l'index {idx} ne doit pas être vide.")

        annotations_valides.append({
            "texte_lu": texte_lu,
            "repere": repere,
        })

    non_classes = data.get("textes_non_classes")
    if not isinstance(non_classes, list):
        raise ValueError("Le champ 'textes_non_classes' doit être une liste.")

    non_classes_valides = []
    for idx, val in enumerate(non_classes):
        if not isinstance(val, str) or isinstance(val, bool):
            raise ValueError(f"L'élément à l'index {idx} de 'textes_non_classes' doit être une chaîne de caractères (str).")
        non_classes_valides.append(val.strip())

    return {
        "annotations_lues": annotations_valides,
        "textes_non_classes": non_classes_valides,
    }