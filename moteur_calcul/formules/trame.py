"""
Trame structurelle -- feuille de route "Ma partie -- Backend", Jour 1
§1.3 et Jour 2 §2.3, et Phase B de la feuille de route "Import plan
automatique" (positions réelles, sans grille uniforme).

generer_poteau_sur_grille() est appelée en boucle par Samuel dans son
endpoint generer_trame/ (son Jour 2) : elle doit rester prête AVANT
qu'il attaque cette partie -- c'est la priorité du jour.

generer_poteau_depuis_position_reelle() et generer_poutre_depuis_positions_reelles()
(Phase B) couvrent le cas import : une trame réelle n'est jamais une
grille parfaite (poteaux manquants, décrochés, portées irrégulières --
voir import_ifc/lecture_ifc.py), donc au lieu d'indices (i, j) sur une
grille régulière, on part du nuage de points réel détecté dans l'IFC et
on retrouve les voisins direct de chaque poteau par proximité.

Ne touche à aucun modèle Django ni à la base : ce sont des fonctions
pures, testables en isolation sans dépendre des champs pas encore
ajoutés côté Projet/ElementStructurel (nb_travees_x, position_x...).
"""

from ..constantes import CHARGES_EXPLOITATION
from ..import_ifc.lecture_ifc import TOLERANCE_ALIGNEMENT_M
from .descente_charges import calculer_surface_influence
from .dimensionnement_poteaux import dimensionner_poteau
from .dimensionnement_poutres import dimensionner_poutre
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


def _trouver_voisin_direct(poteau, voisins, axe, sens):
    """
    Cherche, parmi `voisins` (nuage de points détecté, ex. sortie
    d'extraire_poteaux()), le voisin direct de `poteau` dans une seule
    direction cardinale :
        axe  : "x" ou "y" -- l'axe sur lequel on avance.
        sens : +1 (droite/arrière) ou -1 (gauche/avant).

    "Aligné" = même ligne/colonne de grille au sens de la Phase A :
    écart <= TOLERANCE_ALIGNEMENT_M sur l'axe PERPENDICULAIRE (mêmes
    poteaux réels ne sont jamais parfaitement alignés). Parmi les
    poteaux alignés situés dans la bonne direction, on retient celui à
    distance minimale -- c'est le voisin "direct" (rien entre les deux).

    Retour : (voisin, distance) -- (None, 0.0) si aucun voisin dans
    cette direction (poteau en bord de trame réelle).
    """
    axe_perp = "y" if axe == "x" else "x"
    meilleur = None
    meilleure_distance = None
    for v in voisins:
        if v is poteau or v.get("guid") == poteau.get("guid"):
            continue
        if abs(v[axe_perp] - poteau[axe_perp]) > TOLERANCE_ALIGNEMENT_M:
            continue
        delta = (v[axe] - poteau[axe]) * sens
        # delta doit dépasser la tolérance pour compter comme un voisin
        # distinct dans cette direction (évite qu'un point quasi-confondu,
        # bruit de relevé, ne soit pris pour un voisin direct).
        if delta <= TOLERANCE_ALIGNEMENT_M:
            continue
        if meilleure_distance is None or delta < meilleure_distance:
            meilleure_distance = delta
            meilleur = v
    return meilleur, (meilleure_distance or 0.0)


def generer_poteau_depuis_position_reelle(poteau_ifc, voisins, charge_exploitation, hauteur_etage):
    """
    Phase B (import) -- équivalent de generer_poteau_sur_grille() mais
    sans grille régulière : la position et la charge du poteau sont
    calculées à partir de ses voisins RÉELLEMENT détectés dans le nuage
    de points, pas d'une portée fixe.

    poteau_ifc : un élément de extraire_poteaux() -- dict avec au moins
    "x", "y" (mètres) ; "guid"/"nom" transmis dans le résultat s'ils
    existent.
    voisins : le nuage de points complet dans lequel chercher les
    voisins de poteau_ifc (typiquement tous les poteaux du même niveau,
    poteau_ifc inclus -- il est exclu automatiquement de la recherche).

    Réutilise calculer_surface_influence() (Module 1) exactement comme
    generer_poteau_sur_grille(), en lui passant les 4 distances réelles
    aux voisins directs (0 si aucun voisin dans une direction : bord de
    la trame réelle) au lieu de portee_x/y fixes.

    Retour : même forme que generer_poteau_sur_grille(), plus "guid",
    "nom" (traçabilité vers le poteau IFC d'origine) et
    "portees_detectees" (diagnostic : les 4 distances utilisées).
    """
    _, portee_gauche = _trouver_voisin_direct(poteau_ifc, voisins, axe="x", sens=-1)
    _, portee_droite = _trouver_voisin_direct(poteau_ifc, voisins, axe="x", sens=+1)
    _, portee_avant = _trouver_voisin_direct(poteau_ifc, voisins, axe="y", sens=-1)
    _, portee_arriere = _trouver_voisin_direct(poteau_ifc, voisins, axe="y", sens=+1)

    surface = calculer_surface_influence(portee_gauche, portee_droite, portee_avant, portee_arriere)
    if surface <= 0:
        # Surface nulle = aucun voisin détecté sur tout un axe (poteau
        # isolé, en bout de ligne sans direction perpendiculaire, ou mal
        # aligné/hors tolérance) -- pas une trame 2D exploitable pour ce
        # poteau. On lève une erreur explicite plutôt que de laisser
        # dimensionner_poteau échouer plus loin avec une charge nulle.
        raise ValueError(
            f"Impossible de calculer la surface d'influence du poteau "
            f"{poteau_ifc.get('nom') or poteau_ifc.get('guid') or '(sans nom)'} : "
            f"aucun voisin direct détecté sur un axe entier (portées : "
            f"gauche={portee_gauche}, droite={portee_droite}, avant={portee_avant}, "
            f"arriere={portee_arriere}). Vérifiez le nuage de points -- poteau "
            f"isolé, en bout de ligne, ou hors tolérance d'alignement "
            f"({TOLERANCE_ALIGNEMENT_M} m)."
        )

    charge_exploitation = charge_exploitation or CHARGES_EXPLOITATION.get("habitation")
    charge_g = surface * CHARGE_PERMANENTE_FORFAITAIRE_KN_M2
    charge_q = surface * charge_exploitation
    charge_elu = 1.35 * charge_g + 1.5 * charge_q

    resultat_poteau = dimensionner_poteau(charge_calculee=charge_elu, hauteur_poteau=hauteur_etage)
    # Même fix Module 6 que generer_poteau_sur_grille : côté réel transmis à la semelle.
    resultat_semelle = dimensionner_semelle(
        charge_poteau=charge_elu, cote_poteau_cm=resultat_poteau["cote_cm"]
    )

    return {
        "guid": poteau_ifc.get("guid"),
        "nom": poteau_ifc.get("nom"),
        "x": poteau_ifc["x"],
        "y": poteau_ifc["y"],
        "charge_elu_kn": charge_elu,
        "resultat_poteau": resultat_poteau,
        "resultat_semelle": resultat_semelle,
        "portees_detectees": {
            "gauche": portee_gauche,
            "droite": portee_droite,
            "avant": portee_avant,
            "arriere": portee_arriere,
        },
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


def generer_poutre_sur_grille(portee, largeur_influence, charge_exploitation):
    """
    Poutre reliant deux poteaux adjacents de la grille (horizontale ou
    verticale selon l'appelant -- cette fonction ne connaît que la
    portée du tronçon).

    `largeur_influence` (m) : largeur de dalle reprise par cette poutre
    -- portee_perpendiculaire pour une poutre "intérieure" (dalle des
    deux côtés), portee_perpendiculaire / 2 pour une poutre de rive
    (dalle d'un seul côté). Reprend le même forfait de charge permanente
    que generer_poteau_sur_grille() pour rester cohérent sur toute la
    trame.

    Retour : {"charge_lineaire_kn_m": ..., "resultat_poutre": {...}}
    (sortie de dimensionner_poutre()).
    """
    charge_exploitation = charge_exploitation or CHARGES_EXPLOITATION.get("habitation")
    charge_surfacique_elu = (
        1.35 * CHARGE_PERMANENTE_FORFAITAIRE_KN_M2 + 1.5 * charge_exploitation
    )
    charge_lineaire_kn_m = charge_surfacique_elu * largeur_influence

    resultat_poutre = dimensionner_poutre(portee=portee, charge_lineaire=charge_lineaire_kn_m)

    return {
        "charge_lineaire_kn_m": charge_lineaire_kn_m,
        "resultat_poutre": resultat_poutre,
    }


def generer_poutre_depuis_positions_reelles(poteau_a, poteau_b, axe, voisins, charge_exploitation):
    """
    Phase B (import) -- une poutre entre deux poteaux RÉELLEMENT
    adjacents (au lieu d'une boucle i, i+1 sur une grille). `axe`
    ("x" ou "y") précise la direction du tronçon ; `portee` est déduite
    de la distance réelle entre poteau_a et poteau_b.

    Largeur d'influence : approximée par la demi-somme des portées
    perpendiculaires détectées à CHAQUE extrémité (chacune divisée par
    2 comme pour une poutre "intérieure" -- voir generer_poutre_sur_grille),
    moyennée entre les deux poteaux. Une extrémité en rive (aucun voisin
    perpendiculaire d'un côté) réduit naturellement sa moitié à 0, comme
    calculer_surface_influence() le fait déjà pour les poteaux de bord.
    C'est une approximation tant qu'une reconstruction 2D complète des
    mailles de dalle n'est pas faite -- à vérifier si les poteaux ne
    sont pas répartis de façon à peu près régulière autour de la poutre.

    Retour : même forme que generer_poutre_sur_grille(), plus
    "poteau_origine_guid", "poteau_destination_guid", "axe" et
    "portee_m" (traçabilité et diagnostic).
    """
    axe_perp = "y" if axe == "x" else "x"
    portee = abs(poteau_b[axe] - poteau_a[axe])

    _, perp_a_pos = _trouver_voisin_direct(poteau_a, voisins, axe=axe_perp, sens=+1)
    _, perp_a_neg = _trouver_voisin_direct(poteau_a, voisins, axe=axe_perp, sens=-1)
    _, perp_b_pos = _trouver_voisin_direct(poteau_b, voisins, axe=axe_perp, sens=+1)
    _, perp_b_neg = _trouver_voisin_direct(poteau_b, voisins, axe=axe_perp, sens=-1)

    largeur_influence = (
        ((perp_a_pos + perp_a_neg) / 2) + ((perp_b_pos + perp_b_neg) / 2)
    ) / 2

    resultat = generer_poutre_sur_grille(
        portee=portee, largeur_influence=largeur_influence, charge_exploitation=charge_exploitation
    )
    resultat["poteau_origine_guid"] = poteau_a.get("guid")
    resultat["poteau_destination_guid"] = poteau_b.get("guid")
    resultat["axe"] = axe
    resultat["portee_m"] = portee
    return resultat


def detecter_poutres_adjacentes(voisins, charge_exploitation):
    """
    Phase B (import) -- génère une poutre par paire de poteaux
    directement adjacents dans le nuage de points détecté, sans passer
    par une grille i, i+1 régulière.

    Pour chaque poteau, on ne regarde que ses voisins directs dans le
    sens +x et +y : le voisin +x d'un poteau est le voisin -x de ce
    voisin, donc chaque segment du nuage de points n'est généré qu'une
    seule fois (pas de doublon).

    Retour : liste de résultats de generer_poutre_depuis_positions_reelles(),
    un par segment détecté.
    """
    poutres = []
    for poteau in voisins:
        for axe in ("x", "y"):
            voisin, _ = _trouver_voisin_direct(poteau, voisins, axe=axe, sens=+1)
            if voisin is None:
                continue
            poutres.append(
                generer_poutre_depuis_positions_reelles(poteau, voisin, axe, voisins, charge_exploitation)
            )
    return poutres