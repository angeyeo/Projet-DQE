USAGES_VALIDES = ["HABITATION", "BUREAU", "COMMERCE", "INDUSTRIEL", "AUTRE"]

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

    # 1. Validation de nombre_niveaux
    nombre_niveaux = data.get("nombre_niveaux")
    if nombre_niveaux is not None:
        try:
            val_int = int(nombre_niveaux)
            if val_int < 1 or val_int > 100:
                raise ValueError("Le nombre de niveaux doit être compris entre 1 et 100.")
            res["nombre_niveaux"] = val_int
        except (TypeError, ValueError) as exc:
            if "compris entre" in str(exc):
                raise
            raise ValueError("nombre_niveaux doit être un entier valide.")

    # 2. Validation de la configuration (ex: "R+2")
    config = data.get("configuration")
    if config is not None:
        res["configuration"] = str(config).strip()

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
        try:
            val_float = float(portee_m)
            if val_float <= 0:
                raise ValueError("La portée doit être strictement positive.")
            res["portee_m"] = val_float
        except (TypeError, ValueError) as exc:
            if "strictement positive" in str(exc):
                raise
            raise ValueError("portee_m doit être un nombre décimal valide.")

    # 5. Validation de hauteur_niveau_m
    hauteur_niveau_m = data.get("hauteur_niveau_m")
    if hauteur_niveau_m is not None:
        try:
            val_float = float(hauteur_niveau_m)
            if val_float <= 0:
                raise ValueError("La hauteur de niveau doit être strictement positive.")
            res["hauteur_niveau_m"] = val_float
        except (TypeError, ValueError) as exc:
            if "strictement positive" in str(exc):
                raise
            raise ValueError("hauteur_niveau_m doit être un nombre décimal valide.")

    # 6. Validation de contrainte_sol_kn_m2
    contrainte_sol = data.get("contrainte_sol_kn_m2")
    if contrainte_sol is not None:
        try:
            val_float = float(contrainte_sol)
            if val_float <= 0:
                raise ValueError("La contrainte de sol doit être strictement positive.")
            res["contrainte_sol_kn_m2"] = val_float
        except (TypeError, ValueError) as exc:
            if "strictement positive" in str(exc):
                raise
            raise ValueError("contrainte_sol_kn_m2 doit être un nombre décimal valide.")

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
