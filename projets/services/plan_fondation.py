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


def generer_plan_fondation_dxf(
    semelles,
    tolerance_position_m: float = 0.01,
    poutres: list = None,
    longrines: list = None,
    chainages_identifies: list = None,
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
    for (x1, y1), (x2, y2) in segments:
        msp.add_line((x1, y1), (x2, y2), dxfattribs={"layer": "CHAINAGE"})
        longueur_totale_ml += math.hypot(x2 - x1, y2 - y1)

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

    tampon = io.StringIO()
    doc.write(tampon)
    return tampon.getvalue().encode("utf-8")