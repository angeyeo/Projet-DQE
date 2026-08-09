"""
Cas de test connus pour valider le moteur de calcul.

Ces valeurs sont réelles (calculées et vérifiées) -- issues des vraies
formules du technicien BTP, alignées sur le fichier de référence "Mon
Métreur".
"""

CAS_DESCENTE_CHARGES_1 = {
    "entrees": {
        "surface": 25,           # m² (5m x 5m, cas Villa R+1)
        "epaisseur_dalle": 0.2,  # m
        "usage_batiment": "habitation",
    },
    "charge_permanente_attendue": 125.0,
    "charge_exploitation_attendue": 37.5,
    "charge_elu_par_niveau_attendue": 225.0,
    "charge_cumulee_2_niveaux_attendue": 450.0,
}

CAS_DIMENSIONNEMENT_POTEAU_1 = {
    "entrees": {
        "charge_calculee": 250,  # kN
        "hauteur_poteau": 3.0,   # m
    },
    "resultat_attendu": {
        "cote_cm": 20,
        "section_cm2": 400,
        "section_theorique_cm2": 185.7,
        "elancement": 52.0,
        "coefficient_alpha": 0.556,
        "nu_lim_beton_seul_kn": 333.3,
        "verification_beton_seul_suffisante": True,
        "section_acier_min_cm2": 3.2,
        "section_acier_max_cm2": 20.0,
        "section_acier_retenue_cm2": 3.2,
        "frettage_necessaire": False,
    },
}

CAS_DIMENSIONNEMENT_POUTRE_1 = {
    "entrees": {
        "portee": 6.0,
        "charge_lineaire": 15,
    },
    "resultat_attendu": {
        "hauteur_cm": 75.0,
        "largeur_cm": 20.0,
        "moment_flechissant_knm": 67.5,
        "moment_reduit": 0.0523,
        "pivot": "A",
        "section_acier_theorique_cm2": 2.36,
        "non_fragilite_respectee": True,
    },
}

CAS_DIMENSIONNEMENT_SEMELLE_1 = {
    "entrees": {
        "charge_poteau": 250,
        "taux_travail_sol": 180,
    },
    "resultat_attendu": {
        "cote_cm": 117.9,
        "surface_m2": 1.39,
        "hauteur_cm": 23.2,
    },
}