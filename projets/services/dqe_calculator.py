from decimal import Decimal, ROUND_HALF_UP
from projets.models import Projet, ElementStructurel, PosteMainDoeuvre

# Prix unitaires par défaut en FCFA
PRIX_UNITAIRES_DEFAUT = {
    "beton_m3": Decimal("100000"),
    "acier_kg": Decimal("800"),
    "coffrage_m2": Decimal("12000"),
}

# Ratios d'acier par défaut en kg/m3 (solution de secours en attente de la norme définitive)
RATIOS_ACIER_KG_M3 = {
    "POTEAU": Decimal("100"),
    "POUTRE": Decimal("120"),
    "SEMELLE": Decimal("80"),
}

def cm_vers_m(valeur_cm) -> float:
    """Convertit une dimension en centimètres vers des mètres."""
    if valeur_cm is None:
        return 0.0
    return float(valeur_cm) / 100.0

def calculer_element_dqe(element: ElementStructurel, prix_unitaires: dict) -> list:
    """
    Calcule les quantités et montants (Béton, Coffrage, Acier) pour un élément
    structurel validé.
    
    Retourne une liste de lignes de devis structurées.
    """
    res = element.resultat_valide
    if not res:
        return []

    lignes = []

    # 1. Poteau
    if element.type_element == ElementStructurel.TypeElement.POTEAU:
        largeur_cm = res.get("largeur_cm")
        profondeur_cm = res.get("profondeur_cm")
        hauteur_poteau = element.hauteur_poteau  # En mètres sur le modèle

        if not all(v is not None for v in [largeur_cm, profondeur_cm, hauteur_poteau]):
            return []

        largeur_m = cm_vers_m(largeur_cm)
        profondeur_m = cm_vers_m(profondeur_cm)

        # Béton (m3) = l * p * h
        volume_beton = Decimal(str(largeur_m * profondeur_m * hauteur_poteau))
        # Coffrage (m2) = 2 * (l + p) * h
        surf_coffrage = Decimal(str(2 * (largeur_m + profondeur_m) * hauteur_poteau))

        # Acier (kg)
        # Priorité 1 : Poids total fourni par le moteur (si présent)
        poids_moteur = res.get("poids_acier_total_kg")
        if poids_moteur is not None:
            poids_acier = Decimal(str(poids_moteur))
        else:
            # Priorité 2 : Utilisation du ratio par défaut
            poids_acier = volume_beton * RATIOS_ACIER_KG_M3["POTEAU"]

    # 2. Poutre
    elif element.type_element == ElementStructurel.TypeElement.POUTRE:
        largeur_cm = res.get("largeur_cm")
        hauteur_cm = res.get("hauteur_cm")
        portee = element.portee  # En mètres sur le modèle

        if not all(v is not None for v in [largeur_cm, hauteur_cm, portee]):
            return []

        largeur_m = cm_vers_m(largeur_cm)
        hauteur_m = cm_vers_m(hauteur_cm)

        # Béton (m3) = l * h * L
        volume_beton = Decimal(str(largeur_m * hauteur_m * portee))
        # Coffrage (m2) = (l + 2 * h) * L (face supérieure non coffrée)
        surf_coffrage = Decimal(str((largeur_m + 2 * hauteur_m) * portee))

        # Acier (kg)
        poids_moteur = res.get("poids_acier_total_kg")
        if poids_moteur is not None:
            poids_acier = Decimal(str(poids_moteur))
        else:
            poids_acier = volume_beton * RATIOS_ACIER_KG_M3["POUTRE"]

    # 3. Semelle
    elif element.type_element == ElementStructurel.TypeElement.SEMELLE:
        cote_cm = res.get("cote_cm")
        hauteur_cm = res.get("hauteur_cm")

        if not all(v is not None for v in [cote_cm, hauteur_cm]):
            return []

        cote_m = cm_vers_m(cote_cm)
        hauteur_m = cm_vers_m(hauteur_cm)

        # Béton (m3) = cote_m * cote_m * hauteur_m
        volume_beton = Decimal(str(cote_m * cote_m * hauteur_m))
        # Coffrage latéral (m2) = 4 * cote_m * hauteur_m
        surf_coffrage = Decimal(str(4 * cote_m * hauteur_m))

        # Acier (kg)
        poids_moteur = res.get("poids_acier_total_kg")
        if poids_moteur is not None:
            poids_acier = Decimal(str(poids_moteur))
        else:
            poids_acier = volume_beton * RATIOS_ACIER_KG_M3["SEMELLE"]

    else:
        return []

    # Sécurité anti-valeurs négatives ou nulles
    if volume_beton <= 0 or surf_coffrage <= 0 or poids_acier <= 0:
        return []

    # Construction des lignes de devis
    # Béton
    pu_beton = Decimal(str(prix_unitaires.get("beton_m3", PRIX_UNITAIRES_DEFAUT["beton_m3"])))
    lignes.append({
        "element_id": element.id,
        "repere": element.identifiant,
        "type_element": element.type_element.upper(),
        "designation": f"Béton armé — {element.get_type_element_display()} {element.identifiant}",
        "categorie": "BETON",
        "unite": "m³",
        "quantite": float(volume_beton.quantize(Decimal("0.0001"), rounding=ROUND_HALF_UP)),
        "prix_unitaire": int(pu_beton),
        "montant": int((volume_beton * pu_beton).quantize(Decimal("1"), rounding=ROUND_HALF_UP))
    })

    # Coffrage
    pu_coffrage = Decimal(str(prix_unitaires.get("coffrage_m2", PRIX_UNITAIRES_DEFAUT["coffrage_m2"])))
    lignes.append({
        "element_id": element.id,
        "repere": element.identifiant,
        "type_element": element.type_element.upper(),
        "designation": f"Coffrage — {element.get_type_element_display()} {element.identifiant}",
        "categorie": "COFFRAGE",
        "unite": "m²",
        "quantite": float(surf_coffrage.quantize(Decimal("0.0001"), rounding=ROUND_HALF_UP)),
        "prix_unitaire": int(pu_coffrage),
        "montant": int((surf_coffrage * pu_coffrage).quantize(Decimal("1"), rounding=ROUND_HALF_UP))
    })

    # Acier
    pu_acier = Decimal(str(prix_unitaires.get("acier_kg", PRIX_UNITAIRES_DEFAUT["acier_kg"])))
    lignes.append({
        "element_id": element.id,
        "repere": element.identifiant,
        "type_element": element.type_element.upper(),
        "designation": f"Armatures acier — {element.get_type_element_display()} {element.identifiant}",
        "categorie": "ACIER",
        "unite": "kg",
        "quantite": float(poids_acier.quantize(Decimal("0.0001"), rounding=ROUND_HALF_UP)),
        "prix_unitaire": int(pu_acier),
        "montant": int((poids_acier * pu_acier).quantize(Decimal("1"), rounding=ROUND_HALF_UP))
    })

    return lignes

def calculer_projet_dqe(projet: Projet, prix_unitaires: dict = None) -> dict:
    """
    Parcourt tous les éléments validés d'un projet, calcule leurs métrés,
    y associe les postes de main d'œuvre saisis manuellement, et agrège
    le tout dans un dictionnaire DQE unique.
    """
    if prix_unitaires is None:
        prix_unitaires = PRIX_UNITAIRES_DEFAUT

    # Uniquement les éléments au statut VALIDE
    elements_valides = projet.elements.filter(statut=ElementStructurel.Statut.VALIDE)

    toutes_lignes = []
    sous_totaux = {
        "beton": Decimal("0"),
        "coffrage": Decimal("0"),
        "acier": Decimal("0"),
        "main_doeuvre": Decimal("0"),
    }

    # 1. Calcul pour les éléments structurels
    for element in elements_valides:
        lignes_el = calculer_element_dqe(element, prix_unitaires)
        toutes_lignes.extend(lignes_el)
        for ligne in lignes_el:
            cat = ligne["categorie"].lower()
            if cat in sous_totaux:
                sous_totaux[cat] += Decimal(str(ligne["montant"]))

    # 2. Ajout des postes de main d'œuvre manuels
    postes_mo = projet.postes_main_doeuvre.all()
    for poste in postes_mo:
        q_dec = Decimal(str(poste.quantite))
        pu_dec = Decimal(str(poste.prix_unitaire))
        montant_dec = (q_dec * pu_dec).quantize(Decimal("1"), rounding=ROUND_HALF_UP)

        toutes_lignes.append({
            "element_id": None,
            "repere": "MO",
            "type_element": "MAIN_DOEUVRE",
            "designation": poste.designation,
            "categorie": "MAIN_DOEUVRE",
            "unite": poste.unite,
            "quantite": float(q_dec.quantize(Decimal("0.0001"), rounding=ROUND_HALF_UP)),
            "prix_unitaire": int(pu_dec),
            "montant": int(montant_dec)
        })
        sous_totaux["main_doeuvre"] += montant_dec

    total_general = sum(sous_totaux.values())

    return {
        "projet": {
            "id": projet.id,
            "nom": projet.nom,
        },
        "lignes": toutes_lignes,
        "sous_totaux": {
            "beton": int(sous_totaux["beton"]),
            "coffrage": int(sous_totaux["coffrage"]),
            "acier": int(sous_totaux["acier"]),
            "main_doeuvre": int(sous_totaux["main_doeuvre"]),
        },
        "total_general": int(total_general),
        "devise": "FCFA"
    }
