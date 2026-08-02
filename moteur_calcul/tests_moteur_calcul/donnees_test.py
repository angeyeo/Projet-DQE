"""
Cas de test connus pour valider le moteur de calcul.

IMPORTANT : "resultat_attendu" est à None tant que le technicien BTP n'a
pas confirmé la formule et un résultat de référence calculé à la main.
Ne jamais remplir cette valeur par une estimation -- ça invaliderait le
test (il passerait "par hasard" sans garantir que la formule est juste).
"""

CAS_DESCENTE_CHARGES_1 = {
    "entrees": {
        "surface": 30,  # m²
        "usage_batiment": "habitation",
        "nb_niveaux_superieurs": 2,
    },
    "resultat_attendu": None,  # kN -- à remplir avec le technicien BTP
}

CAS_DIMENSIONNEMENT_POTEAU_1 = {
    "entrees": {
        "charge_calculee": 250,  # kN, valeur fictive
        "hauteur_poteau": 3.0,   # m
    },
    "resultat_attendu": None,  # dict {"largeur_cm": ..., "profondeur_cm": ..., ...}
}

CAS_DIMENSIONNEMENT_POUTRE_1 = {
    "entrees": {
        "portee": 6.0,           # m
        "charge_lineaire": 15,   # kN/m, valeur fictive
    },
    "resultat_attendu": None,
}

CAS_DIMENSIONNEMENT_SEMELLE_1 = {
    "entrees": {
        "charge_poteau": 250,       # kN
        "taux_travail_sol": 2.0,    # bars, valeur fictive -- à confirmer
    },
    "resultat_attendu": None,
}