"""
Données de test pour le moteur de calcul.
"""

CAS_DESCENTE_CHARGES_1 = {
    "entrees": {"surface": 30.0, "usage_batiment": "habitation"},
    "resultat_attendu": 45.0,
}

CAS_DIMENSIONNEMENT_POTEAU_1 = {
    "entrees": {"charge_calculee": 150.0, "hauteur_poteau": 3.0},
    "resultat_attendu": {
        "cote_cm": 20,
        "section_cm2": 400,
        "coefficient_alpha": 0.556,
        "elancement": 52.0,
        "nu_lim_beton_seul_kn": 333.3,
        "section_theorique_cm2": 111.4,
        "verification_beton_seul_suffisante": True,
    },
}

CAS_DIMENSIONNEMENT_POUTRE_1 = {
    "entrees": {"portee": 5.0, "charge_lineaire": 15.0},
    "resultat_attendu": {"largeur_cm": 20, "hauteur_cm": 40},
}

CAS_DIMENSIONNEMENT_SEMELLE_1 = {
    "entrees": {"charge_poteau": 200.0, "taux_travail_sol": 2.0},
    "resultat_attendu": {"cote_cm": 150, "hauteur_cm": 40},
}