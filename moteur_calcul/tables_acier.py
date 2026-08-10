"""
Table des sections d'acier réelles (diamètres commerciaux HA), reprise
du fichier de référence du technicien BTP ("Mon Métreur", feuille
"Sections d'aciers").

Permet de passer d'une section théorique (cm²) à un vrai choix de
barres (diamètre + nombre), au lieu de garder juste un chiffre abstrait.
"""

# Section d'une seule barre (cm²) et masse linéique (kg/m), par diamètre (mm)
BARRES = {
    5:  {"section_cm2": 0.196, "masse_kg_m": 0.154},
    6:  {"section_cm2": 0.283, "masse_kg_m": 0.222},
    8:  {"section_cm2": 0.503, "masse_kg_m": 0.395},
    10: {"section_cm2": 0.785, "masse_kg_m": 0.617},
    12: {"section_cm2": 1.131, "masse_kg_m": 0.888},
    14: {"section_cm2": 1.539, "masse_kg_m": 1.208},
    16: {"section_cm2": 2.011, "masse_kg_m": 1.578},
    20: {"section_cm2": 3.142, "masse_kg_m": 2.466},
    25: {"section_cm2": 4.909, "masse_kg_m": 3.853},
    32: {"section_cm2": 8.042, "masse_kg_m": 6.313},
    40: {"section_cm2": 12.566, "masse_kg_m": 9.865},
}


def proposer_barres(section_requise_cm2, diametres_autorises=None, nb_barres_min=2, nb_barres_max=8):
    """
    Propose une combinaison réelle de barres (diamètre + nombre) qui
    couvre au moins la section requise, en minimisant l'excès de
    matière (pas juste le premier choix qui dépasse).

    Paramètres
    ----------
    section_requise_cm2 : float
        Section d'acier nécessaire, en cm².
    diametres_autorises : list[int], optionnel
        Diamètres à considérer (mm). Par défaut, une plage courante en
        bâtiment (10 à 25mm) -- évite de proposer du Ø40 pour un petit
        poteau, ou du Ø5 pour une grosse charge.
    nb_barres_min / nb_barres_max : int
        Nombre de barres acceptable pour rester constructif (2 minimum
        pour une section symétrique, 8 maximum pour rester réaliste
        dans un coffrage courant).

    Retour
    ------
    dict : {
        "diametre_mm": int,
        "nombre_barres": int,
        "section_reelle_cm2": float,
        "exces_pourcent": float,   # (reelle - requise) / requise x 100
    }
    ou None si aucune combinaison raisonnable ne convient (section
    requise trop grande pour la plage de diamètres/nombre autorisée).
    """
    if section_requise_cm2 <= 0:
        raise ValueError("La section requise doit être positive.")

    diametres = diametres_autorises or [10, 12, 14, 16, 20, 25]
    meilleure_option = None

    for diametre in diametres:
        section_barre = BARRES[diametre]["section_cm2"]
        for nb in range(nb_barres_min, nb_barres_max + 1):
            section_reelle = section_barre * nb
            if section_reelle >= section_requise_cm2:
                exces = (section_reelle - section_requise_cm2) / section_requise_cm2 * 100
                if meilleure_option is None or exces < meilleure_option["exces_pourcent"]:
                    meilleure_option = {
                        "diametre_mm": diametre,
                        "nombre_barres": nb,
                        "section_reelle_cm2": round(section_reelle, 3),
                        "exces_pourcent": round(exces, 1),
                    }
                break  # pas la peine de tester plus de barres pour ce diamètre, l'excès ne fera qu'augmenter

    return meilleure_option


def poids_barres(diametre_mm, nombre_barres, longueur_m):
    """Poids total (kg) d'un jeu de barres d'un diamètre donné."""
    if diametre_mm not in BARRES:
        raise ValueError(f"Diamètre non répertorié : {diametre_mm} mm")
    return BARRES[diametre_mm]["masse_kg_m"] * nombre_barres * longueur_m