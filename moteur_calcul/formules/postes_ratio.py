"""
Postes du DQE type CIMBAT sans dimensionnement structurel dédié
(maçonnerie, enduit, chaînage, raidisseur, acrotère) -- Phase 2/3,
feuille de route "Ma partie -- Backend", Jour 1, §1.2.

Ces quantités ne sortent pas d'un calcul de résistance mais de la
géométrie générale du bâtiment (périmètre, hauteurs, nombre de
niveaux...). Voir moteur_calcul/constantes.py pour le détail des
ratios utilisés et l'avertissement sur leur statut provisoire.

calculer_poste_ratio() ne renvoie JAMAIS de prix -- uniquement des
lignes {designation, unite, quantite}, exactement comme les autres
sorties du moteur. La valorisation (prix unitaires) reste la
responsabilité de dqe_calculator.py, pas de ce module.
"""

from ..constantes import (
    EPAISSEUR_AGGLOS_15_M,
    EPAISSEUR_AGGLOS_10_M,
    COEFFICIENT_PLEIN_MACONNERIE_ELEVATION,
    RATIO_ACIER_ELEMENT_LINEAIRE_LEGER_KG_M3,
    RATIO_ACIER_RAIDISSEUR_AMORCE_KG_M3,
    RATIO_COFFRAGE_ELEMENT_LINEAIRE_LEGER_M2_M3,
    RATIO_COFFRAGE_ACROTERE_M2_M3,
    SECTION_CHAINAGE_M2,
    SECTION_ACROTERE_M2,
    LARGEUR_CHAINAGE_CM_DEFAUT,
    HAUTEUR_CHAINAGE_CM_DEFAUT,
)
from ..validators import EntreeInvalide

TYPES_POSTES = ("maconnerie", "enduit", "chainage", "raidisseur", "acrotere")

# Schéma des données géométriques attendues par chaque poste -- exposé au
# frontend (GET /api/referentiel/) pour qu'il construise le formulaire
# sans recopier ces clés. "requis" : obligatoire pour obtenir AU MOINS une
# ligne ; les champs optionnels ajoutent une ligne ou remplacent une
# hypothèse par défaut signalée.
SCHEMA_GEOMETRIE = {
    "maconnerie": [
        {"cle": "perimetre_batiment_m", "libelle": "Périmètre du bâtiment", "unite": "m", "requis": True},
        {"cle": "hauteur_soubassement_m", "libelle": "Hauteur de soubassement (agglos pleins)", "unite": "m", "requis": False},
        {"cle": "hauteur_etage_m", "libelle": "Hauteur d'étage (agglos creux)", "unite": "m", "requis": False},
        {"cle": "nb_niveaux", "libelle": "Nombre de niveaux en élévation", "unite": "", "requis": False},
        {"cle": "coefficient_plein", "libelle": "Coefficient de plein des murs (0 à 1)", "unite": "", "requis": False},
    ],
    "enduit": [
        {"cle": "surface_murs_a_enduire_m2", "libelle": "Surface de murs à enduire (2 faces)", "unite": "m²", "requis": False},
        {"cle": "surface_dalle_m2", "libelle": "Surface de sous-face de dalle", "unite": "m²", "requis": False},
    ],
    "chainage": [
        {"cle": "longueur_chainage_m", "libelle": "Longueur de chaînage bas", "unite": "m", "requis": True},
        {"cle": "longueur_chainage_haut_m", "libelle": "Longueur de chaînage haut / linteaux", "unite": "m", "requis": False},
    ],
    "raidisseur": [
        {"cle": "nb_poteaux", "libelle": "Nombre de raidisseurs", "unite": "", "requis": True},
        {"cle": "hauteur_raidisseur_m", "libelle": "Hauteur d'un raidisseur", "unite": "m", "requis": True},
    ],
    "acrotere": [
        {"cle": "perimetre_acrotere_m", "libelle": "Périmètre de l'acrotère", "unite": "m", "requis": True},
    ],
}


def _lignes_element_lineaire(prefixe, longueur_m, section_m2, ratio_acier_kg_m3, ratio_coffrage_m2_m3):
    """
    Factorise le calcul commun à tous les éléments "linéaires" en béton
    armé (chaînage, raidisseur, acrotère) : béton = longueur x section,
    acier et coffrage déduits par ratio du volume de béton.
    """
    if longueur_m is None or longueur_m <= 0:
        raise ValueError(f"Longueur de {prefixe} invalide : {longueur_m!r} (doit être > 0 m).")
    volume_beton = longueur_m * section_m2
    return [
        {"designation": f"Béton dosé à 350 kg/m³ (C25/30) — {prefixe}", "unite": "m³", "quantite": round(volume_beton, 2)},
        {"designation": f"Acier HA {ratio_acier_kg_m3:.0f} kg/m³ — {prefixe}", "unite": "kg", "quantite": round(volume_beton * ratio_acier_kg_m3, 2)},
        {"designation": f"Coffrage — {prefixe}", "unite": "m²", "quantite": round(volume_beton * ratio_coffrage_m2_m3, 2)},
    ]


def _poste_maconnerie(geometrie):
    perimetre = geometrie["perimetre_batiment_m"]
    lignes = []

    h_soubassement = geometrie.get("hauteur_soubassement_m")
    if h_soubassement:
        # Métré en m² de mur (unité validée par le technicien BTP) : la
        # surface ne dépend pas de l'épaisseur (15 cm), qui figure dans la
        # désignation et dans le prix unitaire.
        surface_infra = perimetre * h_soubassement
        lignes.append({
            "designation": "Agglos 15 pleins (infrastructure)",
            "unite": "m²", "quantite": round(surface_infra, 2),
            "formule": f"périmètre × hauteur de soubassement = {perimetre:g} × {h_soubassement:g}".replace(".", ","),
        })

    h_etage = geometrie.get("hauteur_etage_m")
    nb_niveaux = geometrie.get("nb_niveaux")
    if h_etage and nb_niveaux:
        surface_brute = perimetre * h_etage * nb_niveaux
        coeff_plein = geometrie.get("coefficient_plein")
        ligne = {"designation": "Agglos 15 creux (élévation)", "unite": "m²"}
        if coeff_plein is None:
            coeff_plein = COEFFICIENT_PLEIN_MACONNERIE_ELEVATION
            ligne["hypothese"] = (
                f"Coefficient de plein des murs non fourni : hypothèse "
                f"{COEFFICIENT_PLEIN_MACONNERIE_ELEVATION} (ouvertures = "
                f"{100 - COEFFICIENT_PLEIN_MACONNERIE_ELEVATION * 100:.0f} % de la surface)."
            )
        if not 0 < coeff_plein <= 1:
            raise ValueError("coefficient_plein doit être compris entre 0 (exclu) et 1.")
        ligne["quantite"] = round(surface_brute * coeff_plein, 2)
        lignes.append(ligne)

    return lignes


def _poste_enduit(geometrie):
    """Enduit des murs (2 faces) + enduit sous plafond (surface de dalle)."""
    lignes = []
    surface_murs = geometrie.get("surface_murs_a_enduire_m2")
    if surface_murs:
        lignes.append({"designation": "Enduits dosé à 350 kg/m³", "unite": "m²", "quantite": round(surface_murs, 2)})

    surface_dalle = geometrie.get("surface_dalle_m2")
    if surface_dalle:
        lignes.append({
            "designation": "Enduits sous plafond dosé à 350 kg/m³",
            "unite": "m²", "quantite": round(surface_dalle, 2),
        })
    return lignes


def _poste_chainage(geometrie):
    """
    Chaînage bas + chaînage haut (linteaux). Attend `longueur_chainage_m`
    (typiquement la sortie de trame.calculer_longueur_chainage() -- Jour 2).
    """
    longueur = geometrie["longueur_chainage_m"]
    lignes = _lignes_element_lineaire(
        "chaînage bas", longueur, SECTION_CHAINAGE_M2,
        RATIO_ACIER_ELEMENT_LINEAIRE_LEGER_KG_M3, RATIO_COFFRAGE_ELEMENT_LINEAIRE_LEGER_M2_M3,
    )
    # Chaînage haut / linteaux : même trame en général -- hypothèse
    # signalée sur les lignes quand la longueur n'est pas fournie.
    longueur_haut = geometrie.get("longueur_chainage_haut_m")
    hypothese = None
    if longueur_haut is None:
        longueur_haut = longueur
        hypothese = "Longueur du chaînage haut non fournie : prise égale au chaînage bas."
    lignes_haut = _lignes_element_lineaire(
        "chaînage haut / linteaux", longueur_haut, SECTION_CHAINAGE_M2,
        RATIO_ACIER_ELEMENT_LINEAIRE_LEGER_KG_M3, RATIO_COFFRAGE_ELEMENT_LINEAIRE_LEGER_M2_M3,
    )
    if hypothese:
        for l in lignes_haut:
            l["hypothese"] = hypothese
    return lignes + lignes_haut


def _poste_raidisseur(geometrie):
    """
    Un raidisseur par poteau (hypothèse -- un vrai plan de ferraillage
    peut en vouloir moins). hauteur_raidisseur_m : hauteur d'un raidisseur
    (souvent la hauteur d'étage).
    """
    nb_poteaux = geometrie["nb_poteaux"]
    hauteur = geometrie.get("hauteur_raidisseur_m") or geometrie.get("hauteur_etage_m")
    if not hauteur:
        raise KeyError("hauteur_raidisseur_m (ou hauteur_etage_m)")
    longueur_totale = nb_poteaux * hauteur
    return _lignes_element_lineaire(
        "raidisseurs", longueur_totale, SECTION_CHAINAGE_M2,
        RATIO_ACIER_RAIDISSEUR_AMORCE_KG_M3, RATIO_COFFRAGE_ELEMENT_LINEAIRE_LEGER_M2_M3,
    )


def _poste_acrotere(geometrie):
    perimetre_toiture = geometrie.get("perimetre_acrotere_m") or geometrie["perimetre_batiment_m"]
    return _lignes_element_lineaire(
        "acrotère", perimetre_toiture, SECTION_ACROTERE_M2,
        RATIO_ACIER_ELEMENT_LINEAIRE_LEGER_KG_M3, RATIO_COFFRAGE_ACROTERE_M2_M3,
    )


_HANDLERS = {
    "maconnerie": _poste_maconnerie,
    "enduit": _poste_enduit,
    "chainage": _poste_chainage,
    "raidisseur": _poste_raidisseur,
    "acrotere": _poste_acrotere,
}


def calculer_poste_ratio(type_poste, geometrie):
    """
    Retourne une liste de lignes {designation, unite, quantite} pour le
    poste demandé -- pas de prix (voir docstring du module).

    Paramètres
    ----------
    type_poste : str, un de TYPES_POSTES.
    geometrie : dict, clés attendues selon type_poste (voir chaque
        fonction _poste_xxx ci-dessus) ; toujours `perimetre_batiment_m`.

    Lève KeyError si une clé requise manque -- volontairement : mieux
    vaut un échec explicite qu'une quantité à zéro silencieuse dans un
    devis destiné à être chiffré.
    """
    if type_poste not in _HANDLERS:
        raise ValueError(f"type_poste inconnu : {type_poste!r} (attendu un de {TYPES_POSTES})")
    return _HANDLERS[type_poste](geometrie)


def dimensionner_chainage(longueur_m, largeur_cm=None, hauteur_cm=None, ratio_acier_kg_m3=None):
    """
    Chaînage identifié INDIVIDUELLEMENT (Phase C, repère CH1) -- pendant
    par-élément de _poste_chainage()/calculer_poste_ratio("chainage", ...),
    pour un chaînage annexe que le plan de référence identifie comme un
    ouvrage à part entière (repère propre, ligne DQE dédiée), plutôt
    qu'une ligne forfaitaire globale noyée dans le lot maçonnerie.

    Pas de calcul de résistance (un chaînage n'est pas dimensionné en
    flexion comme une poutre -- c'est un élément de ceinturage) : section
    forfaitaire et acier au ratio volumique, EXACTEMENT les mêmes
    constantes que le poste ratio existant, pour que les deux chemins
    restent cohérents entre eux si ces valeurs sont un jour révisées
    avec le technicien (voir l'avertissement "provisoire" dans
    constantes.py).

    Paramètres
    ----------
    longueur_m : float
        Longueur totale du chaînage (ce repère), en mètres.
    largeur_cm, hauteur_cm : float, optionnels
        Dimensions de la section. Défaut : 15x20 cm
        (LARGEUR_CHAINAGE_CM_DEFAUT / HAUTEUR_CHAINAGE_CM_DEFAUT,
        cohérent avec SECTION_CHAINAGE_M2 = 0,03 m² déjà utilisé par le
        poste ratio).
    ratio_acier_kg_m3 : float, optionnel
        Défaut : RATIO_ACIER_ELEMENT_LINEAIRE_LEGER_KG_M3 (90 kg/m³,
        même source CIMBAT que le poste ratio -- provisoire).

    Retour
    ------
    dict : {
        "largeur_cm", "hauteur_cm",       # section retenue
        "volume_beton_m3",
        "poids_acier_total_kg",
        "hypothese_section": bool,        # True si dimensions par défaut
        "hypothese_ratio_acier": bool,    # True si ratio par défaut
    }
    """
    if longueur_m is None or longueur_m <= 0:
        raise EntreeInvalide("La longueur du chaînage doit être positive.")
    if (largeur_cm is not None and largeur_cm <= 0) or (hauteur_cm is not None and hauteur_cm <= 0):
        raise EntreeInvalide("Les dimensions de la section doivent être positives.")
    if ratio_acier_kg_m3 is not None and ratio_acier_kg_m3 <= 0:
        raise EntreeInvalide("Le ratio d'acier doit être positif.")

    hypothese_section = largeur_cm is None and hauteur_cm is None
    largeur_cm = largeur_cm or LARGEUR_CHAINAGE_CM_DEFAUT
    hauteur_cm = hauteur_cm or HAUTEUR_CHAINAGE_CM_DEFAUT

    hypothese_ratio_acier = ratio_acier_kg_m3 is None
    ratio_acier_kg_m3 = ratio_acier_kg_m3 or RATIO_ACIER_ELEMENT_LINEAIRE_LEGER_KG_M3

    volume_beton_m3 = (largeur_cm / 100) * (hauteur_cm / 100) * longueur_m
    poids_acier_total_kg = volume_beton_m3 * ratio_acier_kg_m3

    return {
        "largeur_cm": largeur_cm,
        "hauteur_cm": hauteur_cm,
        "volume_beton_m3": round(volume_beton_m3, 4),
        "poids_acier_total_kg": round(poids_acier_total_kg, 2),
        "hypothese_section": hypothese_section,
        "hypothese_ratio_acier": hypothese_ratio_acier,
    }