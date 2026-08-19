"""
Trame structurelle -- feuille de route "Ma partie -- Backend", Jour 1
§1.3 et Jour 2 §2.3.

generer_poteau_sur_grille() est appelée en boucle par Samuel dans son
endpoint generer_trame/ (son Jour 2) : elle doit rester prête AVANT
qu'il attaque cette partie -- c'est la priorité du jour.

Ne touche à aucun modèle Django ni à la base : ce sont des fonctions
pures, testables en isolation sans dépendre des champs pas encore
ajoutés côté Projet/ElementStructurel (nb_travees_x, position_x...).
"""

from ..constantes import CHARGES_EXPLOITATION
from .descente_charges import calculer_surface_influence
from .dimensionnement_poteaux import dimensionner_poteau
from .dimensionnement_semelles import dimensionner_semelle

# Charge permanente forfaitaire (kN/m²) pour un niveau courant, tant que
# le Module 2 (charges composées) n'est pas branché sur la trame --
# cohérent avec la valeur utilisée ailleurs dans le MVP avant le Module 2.
CHARGE_PERMANENTE_FORFAITAIRE_KN_M2 = 5.0


def generer_poteau_sur_grille(
    i, j, portee_x, portee_y, nb_travees_x, nb_travees_y,
    charge_exploitation, hauteur_etage,
):
    """
    (i, j) : indices de la grille, i de 0 à nb_travees_x inclus, j de 0
    à nb_travees_y inclus (nb_travees_x travées => nb_travees_x + 1
    files de poteaux dans cette direction).

    Calcule la position réelle du poteau et sa charge ELU en réutilisant
    calculer_surface_influence() (Module 1) : les portées vers chaque
    côté valent portee_x/portee_y sauf en bord de grille, où elles
    valent 0 (pas de travée au-delà du bord).

    Retour :
    {
        "x": ..., "y": ...,                # mètres, position réelle
        "charge_elu_kn": ...,
        "resultat_poteau": {...},          # sortie de dimensionner_poteau()
        "resultat_semelle": {...},         # sortie de dimensionner_semelle(),
                                            # avec cote_poteau_cm renseigné (Module 6)
    }
    """
    if not (0 <= i <= nb_travees_x) or not (0 <= j <= nb_travees_y):
        raise ValueError(
            f"Indices hors grille : (i={i}, j={j}) pour une trame "
            f"{nb_travees_x}x{nb_travees_y} (i doit être dans [0, {nb_travees_x}], "
            f"j dans [0, {nb_travees_y}])."
        )

    x = i * portee_x
    y = j * portee_y

    portee_gauche = portee_x if i > 0 else 0
    portee_droite = portee_x if i < nb_travees_x else 0
    portee_avant = portee_y if j > 0 else 0
    portee_arriere = portee_y if j < nb_travees_y else 0

    surface = calculer_surface_influence(portee_gauche, portee_droite, portee_avant, portee_arriere)

    charge_exploitation = charge_exploitation or CHARGES_EXPLOITATION.get("habitation")
    charge_g = surface * CHARGE_PERMANENTE_FORFAITAIRE_KN_M2
    charge_q = surface * charge_exploitation
    charge_elu = 1.35 * charge_g + 1.5 * charge_q

    resultat_poteau = dimensionner_poteau(charge_calculee=charge_elu, hauteur_poteau=hauteur_etage)
    # Fix Module 6 : le côté réel du poteau est transmis à la semelle,
    # pas une hypothèse par défaut.
    resultat_semelle = dimensionner_semelle(
        charge_poteau=charge_elu, cote_poteau_cm=resultat_poteau["cote_cm"]
    )

    return {
        "x": x,
        "y": y,
        "charge_elu_kn": charge_elu,
        "resultat_poteau": resultat_poteau,
        "resultat_semelle": resultat_semelle,
    }


def calculer_longueur_chainage(nb_travees_x, nb_travees_y, portee_x, portee_y):
    """
    Longueur totale de chaînage bas = tous les segments reliant deux
    poteaux directement adjacents de la grille (périmètre + alignements
    internes).

    Vérifiée à la main sur trame 2x1, 5,0x4,0 m -> 32 ml.
    """
    if nb_travees_x < 1 or nb_travees_y < 1:
        raise ValueError("Une trame nécessite au moins 1 travée dans chaque direction.")
    longueur_x = nb_travees_x * portee_x * (nb_travees_y + 1)
    longueur_y = nb_travees_y * portee_y * (nb_travees_x + 1)
    return longueur_x + longueur_y
