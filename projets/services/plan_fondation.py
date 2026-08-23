"""
Plan de fondation DXF -- feuille de route "Ma partie -- Backend", Jour 3
§3.2 (extension trame).

Différence par rapport à la première version de ce document : Samuel
stocke maintenant position_x/position_y directement sur chaque
ElementStructurel (remplis à la génération de la grille, son Jour 2) --
plus besoin d'inventer une disposition en grille arbitraire ici, on
dessine directement aux vraies coordonnées reçues.

Comme trame.py, generer_plan_fondation_dxf() est une fonction pure : elle
ne touche à aucun modèle Django ni à la base. Elle prend en entrée le
format exact retourné par GET /api/projets/{id}/plan_fondation/ (Samuel,
Jour 2.4) -- une simple liste de dicts, pas des ElementStructurel.

Adjacence pour le chaînage dessiné
-----------------------------------
Point ouvert de la feuille de route, tranché ici en attendant Samuel :
deux méthodes sont supportées, avec priorité à la plus robuste.

1. Indices de grille (i, j) -- si CHAQUE semelle transmet "indice_i" et
   "indice_j" (clés optionnelles), on relie deux poteaux directement
   adjacents dans le graphe (i, j) : même i et |j1-j2|==1, ou même j et
   |i1-i2|==1. C'est la méthode robuste demandée dans la feuille de
   route -- aucun risque d'erreur d'arrondi.
2. Positions en mètres -- si les indices ne sont pas fournis (ou
   incomplets), on retombe sur la méthode "trier par position_x puis
   position_y, relier chaque poteau à son voisin immédiat dans chaque
   direction" décrite dans la feuille de route, avec une tolérance
   (`tolerance_position_m`, 1 cm par défaut) pour absorber les flottants.

À TRANCHER AVEC SAMUEL (comme prévu) : lui demander de transmettre
systématiquement indice_i/indice_j dans plan_fondation/ pour basculer
définitivement sur la méthode 1 et supprimer la méthode 2.
"""

import io
import math

import ezdxf

from moteur_calcul.formules.complements_plan_coffrage import (
    calculer_contour_dallage,
    calculer_joints_dilatation,
)
from moteur_calcul.formules.dimensionnement_dalles import predimensionner_dalle
from moteur_calcul.validators import EntreeInvalide

# Couleurs DXF (index ACI) -- cohérent avec l'image d'exemple de la
# feuille de route ("poteaux reliés par des segments verts").
COULEUR_SEMELLES = 5   # bleu
COULEUR_POTEAUX = 1    # rouge
COULEUR_CHAINAGE = 3   # vert
COULEUR_ANNOTATIONS = 7  # blanc/noir (couleur du calque courant)
# Phase C (voir Feuille_de_route_Import_Plan_Automatique.md) : nouveaux
# types d'ouvrages transmis par _ouvrages_lineaires_pour_dxf() (Samuel,
# projets/views.py) -- couleurs distinctes du chaînage "implicite"
# (segments recalculés entre semelles adjacentes, COULEUR_CHAINAGE
# ci-dessus) pour ne pas les confondre visuellement sur le plan.
COULEUR_POUTRES = 4          # cyan
COULEUR_LONGRINES = 6        # magenta
COULEUR_CHAINAGES_IDENTIFIES = 2  # jaune
# Compléments Phase C (dallage, joints de dilatation, cotations) --
# géométrie calculée par moteur_calcul/formules/complements_plan_coffrage.py,
# tracé ici uniquement.
COULEUR_DALLAGE = 8              # gris -- discret, en arrière-plan
COULEUR_JOINTS_DILATATION = 30   # orange -- doit ressortir, ouvrage sensible
COULEUR_COTATIONS = 7            # blanc/noir, calque dédié COTATIONS


def _cm_vers_m(valeur_cm) -> float:
    return float(valeur_cm) / 100.0


def _polygone_carre(centre_x, centre_y, cote_m):
    """Retourne les 5 sommets (fermés) d'un carré centré sur (centre_x, centre_y)."""
    demi = cote_m / 2
    return [
        (centre_x - demi, centre_y - demi),
        (centre_x + demi, centre_y - demi),
        (centre_x + demi, centre_y + demi),
        (centre_x - demi, centre_y + demi),
        (centre_x - demi, centre_y - demi),
    ]


def _segments_par_indices(semelles):
    """
    Méthode robuste : relie les poteaux adjacents dans le graphe (i, j).
    Suppose que chaque semelle a "indice_i" et "indice_j".
    """
    par_indice = {(s["indice_i"], s["indice_j"]): s for s in semelles}
    segments = []
    vus = set()
    for (i, j), semelle in par_indice.items():
        for di, dj in ((1, 0), (0, 1)):
            voisin = par_indice.get((i + di, j + dj))
            if voisin is None:
                continue
            cle = frozenset({(i, j), (i + di, j + dj)})
            if cle in vus:
                continue
            vus.add(cle)
            segments.append((
                (semelle["position_x"], semelle["position_y"]),
                (voisin["position_x"], voisin["position_y"]),
            ))
    return segments


def _segments_par_position(semelles, tolerance_position_m):
    """
    Méthode de secours : regroupe par position_x puis position_y (et
    inversement), relie chaque poteau à son voisin immédiat dans
    chaque alignement. Tolérance pour absorber les erreurs de flottants.
    """
    if tolerance_position_m <= 0:
        raise ValueError("tolerance_position_m doit être strictement positif.")

    def cle_arrondie(valeur):
        return round(valeur / tolerance_position_m)

    segments = []

    # Alignements verticaux (même x, y variable)
    par_x = {}
    for s in semelles:
        par_x.setdefault(cle_arrondie(s["position_x"]), []).append(s)
    for groupe in par_x.values():
        groupe.sort(key=lambda s: s["position_y"])
        for a, b in zip(groupe, groupe[1:]):
            segments.append(((a["position_x"], a["position_y"]), (b["position_x"], b["position_y"])))

    # Alignements horizontaux (même y, x variable)
    par_y = {}
    for s in semelles:
        par_y.setdefault(cle_arrondie(s["position_y"]), []).append(s)
    for groupe in par_y.values():
        groupe.sort(key=lambda s: s["position_x"])
        for a, b in zip(groupe, groupe[1:]):
            segments.append(((a["position_x"], a["position_y"]), (b["position_x"], b["position_y"])))

    return segments


def _calculer_segments_chainage(semelles, tolerance_position_m):
    tous_ont_indices = all(
        "indice_i" in s and "indice_j" in s and s["indice_i"] is not None and s["indice_j"] is not None
        for s in semelles
    )
    if tous_ont_indices:
        return _segments_par_indices(semelles)
    return _segments_par_position(semelles, tolerance_position_m)


def _dessiner_ouvrages_lineaires(doc, msp, ouvrages, nom_calque, couleur):
    """
    Phase C : dessine une liste plate d'ouvrages linéaires (poutres,
    longrines ou chaînages identifiés -- même forme
    {identifiant, x1, y1, x2, y2, largeur_cm, hauteur_cm}, voir
    _ouvrages_lineaires_pour_dxf() côté vue) : un trait d'axe par
    ouvrage sur son propre calque, annoté de son repère.

    MVP : trait d'axe simple, pas encore le rectangle de largeur réelle
    (largeur_cm/hauteur_cm sont transmis mais pas encore utilisés pour
    dessiner l'emprise -- à enrichir si le plan de coffrage final doit
    montrer l'épaisseur réelle plutôt qu'un simple repère de tracé).
    """
    if not ouvrages:
        return
    if not doc.layers.has_entry(nom_calque):
        doc.layers.add(name=nom_calque, color=couleur)

    for ouvrage in ouvrages:
        x1, y1, x2, y2 = ouvrage["x1"], ouvrage["y1"], ouvrage["x2"], ouvrage["y2"]
        msp.add_line((x1, y1), (x2, y2), dxfattribs={"layer": nom_calque})

        mx, my = (x1 + x2) / 2, (y1 + y2) / 2
        msp.add_text(
            str(ouvrage["identifiant"]),
            dxfattribs={
                "layer": nom_calque,
                "height": 0.15,
                "insert": (mx, my + 0.15),
            },
        )


def _dessiner_dallage(doc, msp, positions_semelles):
    """
    Phase C : trace le contour du dallage (dalle sur terre-plein) en
    arrière-plan du plan, via calculer_contour_dallage() (moteur pur).
    Annote son épaisseur pré-dimensionnée (predimensionner_dalle(),
    BAEL 91) en se basant sur la plus grande portée détectée entre
    semelles adjacentes -- valeur la plus défavorable (dalle la plus
    épaisse), cohérent avec la logique prudente déjà utilisée ailleurs
    dans le moteur (voir predimensionner_dalle : "ratio le plus
    défavorable"). Si aucune portée n'est disponible (une seule
    semelle), le contour est quand même tracé mais sans annotation
    d'épaisseur -- pas assez d'information pour la calculer.
    """
    if not doc.layers.has_entry("DALLAGE"):
        doc.layers.add(name="DALLAGE", color=COULEUR_DALLAGE)

    contour = calculer_contour_dallage(positions_semelles)
    msp.add_lwpolyline(contour, dxfattribs={"layer": "DALLAGE"})

    x_min = min(p[0] for p in contour)
    y_min = min(p[1] for p in contour)
    return x_min, y_min


def _annoter_epaisseur_dallage(msp, x_min, y_min, portee_max_m):
    """
    Annote l'épaisseur pré-dimensionnée du dallage si la plus grande
    portée détectée entre semelles adjacentes reste dans le domaine de
    validité du moteur (PORTEE_MIN_M..PORTEE_MAX_M, voir
    moteur_calcul/validators.py) -- une "portée" de chaînage hors de ce
    domaine (grand bâtiment industriel, chaînage traversant tout un
    pignon...) n'est de toute façon pas représentative d'une vraie
    portée de dalle ; on trace le dallage sans annotation d'épaisseur
    plutôt que de faire échouer tout l'export DXF pour un détail
    secondaire.
    """
    if not portee_max_m or portee_max_m <= 0:
        return
    try:
        epaisseur = predimensionner_dalle(portee_max_m, portant_deux_sens=False)
    except EntreeInvalide:
        return
    msp.add_text(
        f"Dallage e={epaisseur['epaisseur_cm']:.0f} cm (BAEL 91, pré-dim.)",
        dxfattribs={
            "layer": "DALLAGE",
            "height": 0.3,
            "insert": (x_min, y_min - 0.5),
        },
    )


def _dessiner_joints_dilatation(doc, msp, positions_semelles):
    """
    Phase C : trace les joints de dilatation calculés par
    calculer_joints_dilatation() (moteur pur) -- traits discontinus sur
    calque dédié, annotés "JOINT DE DILATATION" à mi-longueur. Aucun
    tracé si le bâtiment tient dans DISTANCE_MAX_JOINT_DILATATION_M sur
    les deux axes (cas courant en petit bâtiment).
    """
    resultat = calculer_joints_dilatation(positions_semelles)
    if not resultat["joints"]:
        return []

    if not doc.linetypes.has_entry("DASHED"):
        doc.linetypes.add("DASHED", pattern="A,.5,-.25", description="Tireté -- joints de dilatation")
    if not doc.layers.has_entry("JOINTS_DILATATION"):
        doc.layers.add(name="JOINTS_DILATATION", color=COULEUR_JOINTS_DILATATION, linetype="DASHED")

    for joint in resultat["joints"]:
        x1, y1, x2, y2 = joint["x1"], joint["y1"], joint["x2"], joint["y2"]
        msp.add_line((x1, y1), (x2, y2), dxfattribs={"layer": "JOINTS_DILATATION", "lineweight": 35})
        mx, my = (x1 + x2) / 2, (y1 + y2) / 2
        msp.add_text(
            "JOINT DE DILATATION",
            dxfattribs={
                "layer": "JOINTS_DILATATION",
                "height": 0.2,
                "insert": (mx + 0.15, my + 0.15),
            },
        )
    return resultat["avertissements"]


def _dessiner_cotations(doc, msp, segments):
    """
    Phase C : cotation automatique de chaque segment de chaînage (même
    liste que le tracé du calque CHAINAGE, voir
    _calculer_segments_chainage()) -- une vraie entité DXF DIMENSION
    (pas un simple texte), pour que la distance s'affiche et se
    recalcule correctement dans un logiciel CAO si le plan est modifié.

    Décalée de DISTANCE_COTATION_M perpendiculairement au segment, du
    côté "extérieur" (direction opposée au reste du nuage de points) --
    évite que la ligne de cote ne traverse le bâtiment. Utilise
    add_aligned_dim() (pas add_linear_dim()) pour fonctionner quelle que
    soit l'orientation du segment, y compris en diagonale.
    """
    DISTANCE_COTATION_M = 0.8
    if not segments:
        return
    if not doc.layers.has_entry("COTATIONS"):
        doc.layers.add(name="COTATIONS", color=COULEUR_COTATIONS)

    # Centroïde du nuage de points du bâtiment, pour choisir le sens du
    # décalage (vers l'extérieur plutôt qu'au hasard).
    tous_points = [pt for seg in segments for pt in seg]
    centre_x = sum(p[0] for p in tous_points) / len(tous_points)
    centre_y = sum(p[1] for p in tous_points) / len(tous_points)

    for (x1, y1), (x2, y2) in segments:
        dx, dy = x2 - x1, y2 - y1
        longueur = math.hypot(dx, dy)
        if longueur == 0:
            continue  # semelles superposées -- rien à coter

        # Vecteur perpendiculaire unitaire, orienté à l'opposé du centre
        # du bâtiment (vers l'extérieur du segment).
        perp_x, perp_y = -dy / longueur, dx / longueur
        milieu_x, milieu_y = (x1 + x2) / 2, (y1 + y2) / 2
        if (perp_x * (milieu_x - centre_x) + perp_y * (milieu_y - centre_y)) < 0:
            perp_x, perp_y = -perp_x, -perp_y

        dim = msp.add_aligned_dim(
            p1=(x1, y1),
            p2=(x2, y2),
            distance=DISTANCE_COTATION_M,
            dxfattribs={"layer": "COTATIONS"},
        )
        dim.render()


def generer_plan_fondation_dxf(
    semelles,
    tolerance_position_m: float = 0.01,
    poutres: list = None,
    longrines: list = None,
    chainages_identifies: list = None,
    dessiner_dallage: bool = True,
    dessiner_joints_dilatation: bool = True,
    dessiner_cotations: bool = True,
) -> bytes:
    """
    semelles : liste de dicts {identifiant, position_x, position_y, cote_cm,
    hauteur_cm, poteau_associe: {identifiant, cote_cm}, [indice_i, indice_j]}
    -- format exact retourné par GET /api/projets/{id}/plan_fondation/
    (Samuel, Jour 2.4). indice_i/indice_j sont optionnels (voir docstring
    du module pour la méthode d'adjacence utilisée selon leur présence).

    poutres, longrines, chainages_identifies (Phase C, optionnels) :
    listes plates {identifiant, x1, y1, x2, y2, largeur_cm, hauteur_cm}
    -- format produit par _ouvrages_lineaires_pour_dxf() (Samuel,
    projets/views.py). Chacune est dessinée sur son propre calque
    (POUTRES, LONGRINES, CHAINAGES_IDENTIFIES), en plus du chaînage
    "implicite" toujours recalculé ci-dessous entre semelles adjacentes
    (COULEUR_CHAINAGE) -- les deux ne se recouvrent pas forcément
    (chainages_identifies ne concerne que les chaînages promus en
    éléments identifiés, ex. chaînages annexes hors trame principale).

    Dessine chaque semelle à sa vraie position (x, y), le poteau associé
    au centre, et les lignes de chaînage reliant les poteaux adjacents de
    la grille (mêmes segments que calculer_longueur_chainage(), mais
    dessinés plutôt que sommés). Annote la longueur totale sur le plan.

    dessiner_dallage, dessiner_joints_dilatation, dessiner_cotations
    (Phase C, tous True par défaut) : activent respectivement le
    contour du dallage + son épaisseur pré-dimensionnée (calque
    DALLAGE, tracé en premier donc en arrière-plan), les joints de
    dilatation si le bâtiment dépasse
    DISTANCE_MAX_JOINT_DILATATION_M (calque JOINTS_DILATATION,
    tireté), et les cotations DXF natives sur chaque segment de
    chaînage (calque COTATIONS). Géométrie calculée par
    moteur_calcul/formules/complements_plan_coffrage.py -- voir ce
    module pour les hypothèses (débord de dallage, distance max avant
    joint). Paramètres exposés pour permettre de désactiver un calque
    encombrant sur un plan avec beaucoup de semelles, sans dupliquer la
    fonction.

    Lève ValueError si une semelle n'a pas de poteau_associe -- une
    semelle orpheline dans un lot généré signale une régression Module 6
    (cf. Jour 5 de la feuille de route) : mieux vaut un échec explicite
    ici que de dessiner un plan de fondation silencieusement incomplet.

    Retour : bytes du fichier DXF.
    """
    if not semelles:
        raise ValueError("Aucune semelle fournie : impossible de générer un plan de fondation.")

    semelles_sans_poteau = [s["identifiant"] for s in semelles if not s.get("poteau_associe")]
    if semelles_sans_poteau:
        raise ValueError(
            "Semelle(s) sans poteau associé (régression Module 6 probable) : "
            + ", ".join(str(i) for i in semelles_sans_poteau)
        )

    doc = ezdxf.new(dxfversion="R2010")
    doc.layers.add(name="SEMELLES", color=COULEUR_SEMELLES)
    doc.layers.add(name="POTEAUX", color=COULEUR_POTEAUX)
    doc.layers.add(name="CHAINAGE", color=COULEUR_CHAINAGE)
    doc.layers.add(name="ANNOTATIONS", color=COULEUR_ANNOTATIONS)
    msp = doc.modelspace()

    positions_semelles = [(s["position_x"], s["position_y"]) for s in semelles]

    # Dallage tracé en tout premier : calque en arrière-plan, sous les
    # semelles/poteaux dessinés juste après.
    if dessiner_dallage:
        dallage_x_min, dallage_y_min = _dessiner_dallage(doc, msp, positions_semelles)

    xs, ys = [], []

    for semelle in semelles:
        cx, cy = semelle["position_x"], semelle["position_y"]
        xs.append(cx)
        ys.append(cy)

        cote_semelle_m = _cm_vers_m(semelle["cote_cm"])
        msp.add_lwpolyline(
            _polygone_carre(cx, cy, cote_semelle_m),
            dxfattribs={"layer": "SEMELLES"},
        )

        poteau = semelle["poteau_associe"]
        cote_poteau_m = _cm_vers_m(poteau["cote_cm"])
        msp.add_lwpolyline(
            _polygone_carre(cx, cy, cote_poteau_m),
            dxfattribs={"layer": "POTEAUX"},
        )

        msp.add_text(
            str(semelle["identifiant"]),
            dxfattribs={
                "layer": "ANNOTATIONS",
                "height": max(cote_semelle_m * 0.3, 0.1),
                "insert": (cx + cote_semelle_m / 2 + 0.1, cy),
            },
        )

    segments = _calculer_segments_chainage(semelles, tolerance_position_m)
    longueur_totale_ml = 0.0
    portee_max_m = 0.0
    for (x1, y1), (x2, y2) in segments:
        msp.add_line((x1, y1), (x2, y2), dxfattribs={"layer": "CHAINAGE"})
        longueur_segment = math.hypot(x2 - x1, y2 - y1)
        longueur_totale_ml += longueur_segment
        portee_max_m = max(portee_max_m, longueur_segment)

    x_min, y_min = min(xs), min(ys)
    msp.add_text(
        f"Chaînage bas total : {longueur_totale_ml:.2f} ml",
        dxfattribs={
            "layer": "ANNOTATIONS",
            "height": 0.4,
            "insert": (x_min, y_min - 1.5),
        },
    )

    _dessiner_ouvrages_lineaires(doc, msp, poutres, "POUTRES", COULEUR_POUTRES)
    _dessiner_ouvrages_lineaires(doc, msp, longrines, "LONGRINES", COULEUR_LONGRINES)
    _dessiner_ouvrages_lineaires(
        doc, msp, chainages_identifies, "CHAINAGES_IDENTIFIES", COULEUR_CHAINAGES_IDENTIFIES
    )

    if dessiner_dallage:
        _annoter_epaisseur_dallage(msp, dallage_x_min, dallage_y_min, portee_max_m)
    if dessiner_joints_dilatation:
        _dessiner_joints_dilatation(doc, msp, positions_semelles)
    if dessiner_cotations:
        _dessiner_cotations(doc, msp, segments)

    tampon = io.StringIO()
    doc.write(tampon)
    return tampon.getvalue().encode("utf-8")