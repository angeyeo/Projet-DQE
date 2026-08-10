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

# --- Phase 2 ---------------------------------------------------------

# Bâtiment R+3 : une toiture + 3 étages courants, tous identiques
# (25 m² d'influence, habitation => 37,5 kN de charge d'exploitation
# par niveau). Coefficients de dégression NF P06-001 : 1 / 1 / 0,95 / 0,90.
CAS_DEGRESSION_R3 = {
    "entrees": {
        "charge_toiture_kn": 37.5,
        "charges_etages_kn": [37.5, 37.5, 37.5],
        "usage_batiment": "habitation",
    },
    "cumuls_attendus_kn": [37.5, 75.0, 108.75, 138.75],
    "coefficients_attendus": [1.0, 1.0, 0.95, 0.90],
    "cumul_sans_degression_kn": 150.0,
}

# Plancher terrasse réel : dalle 20 cm + chape 5 cm + carrelage +
# cloisons légères réparties => 7,5 kN/m² au lieu des 5,0 kN/m² de la
# dalle béton seule.
CAS_PLANCHER_COMPOSE = {
    "entrees": {
        "surface": 25,
        "couches": [
            {"type": "dalle_beton_arme", "epaisseur_m": 0.20},
            {"type": "chape_mortier", "epaisseur_m": 0.05},
            {"type": "carrelage_colle"},
            {"designation": "cloisons légères", "poids_surfacique_kn_m2": 1.0},
        ],
    },
    "charge_surfacique_totale_attendue_kn_m2": 7.5,
    "charge_totale_attendue_kn": 187.5,
}

# Poteau 250 kN / 3 m demandé en rapport 2:1 (poteau noyé dans un mur
# de 20 cm) : la section théorique (185,7 cm²) tiendrait dans un 20x20,
# mais la forme demandée impose 20x40.
CAS_POTEAU_RECTANGULAIRE = {
    "entrees": {
        "charge_calculee": 250,
        "hauteur_poteau": 3.0,
        "rapport_forme": 2.0,
    },
    "resultat_attendu": {
        "largeur_cm": 20,
        "profondeur_cm": 40,
        "section_cm2": 800,
        # élancement identique au poteau carré 20x20 : c'est le petit
        # côté qui gouverne l'axe faible
        "elancement": 52.0,
        "coefficient_alpha": 0.556,
        "nu_lim_beton_seul_kn": 703.7,
        "verification_beton_seul_suffisante": True,
        "section_acier_min_cm2": 4.8,   # 4 x périmètre = 4 x 1,20 m
        "section_acier_retenue_cm2": 4.8,
        "frettage_necessaire": False,
    },
}

# Mur porteur : 250 kN/ml sur un sol à 200 kN/m², mur de 20 cm.
CAS_SEMELLE_FILANTE = {
    "entrees": {
        "charge_lineaire_kn_m": 250,
        "taux_travail_sol": 200,
        "epaisseur_mur_cm": 20,
    },
    "resultat_attendu": {
        "largeur_cm": 135,      # 125 théorique, élargie pour absorber le poids propre
        "hauteur_cm": 35,
        "hauteur_utile_cm": 30,
        "acier_transversal_cm2_ml": 2.76,
        "acier_repartition_cm2_ml": 0.69,
        "pression_reelle_kn_m2": 193.9,
        "condition_respectee": True,
    },
}