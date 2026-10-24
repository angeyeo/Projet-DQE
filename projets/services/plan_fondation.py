"""
Plan de fondation DXF -- feuille de route "Ma partie -- Backend", Jour 3
§3.2 (extension trame).
"""

import io
import math

import ezdxf
from ezdxf.enums import TextEntityAlignment

from moteur_calcul.formules.complements_plan_coffrage import (
    calculer_contour_dallage,
    calculer_joints_dilatation,
)
from moteur_calcul.formules.dimensionnement_dalles import predimensionner_dalle
from moteur_calcul.validators import EntreeInvalide

COULEUR_SEMELLES = 5   # bleu
COULEUR_POTEAUX = 1    # rouge
COULEUR_CHAINAGE = 3   # vert
COULEUR_ANNOTATIONS = 7  # blanc/noir
COULEUR_POUTRES = 4          # cyan
COULEUR_LONGRINES = 6        # magenta
COULEUR_CHAINAGES_IDENTIFIES = 2  # jaune
COULEUR_DALLAGE = 8              # gris
COULEUR_JOINTS_DILATATION = 30   # orange
COULEUR_COTATIONS = 7            # blanc/noir


def _cm_vers_m(valeur_cm) -> float:
    return float(valeur_cm) / 100.0


def _polygone_carre(centre_x, centre_y, cote_m):
    demi = cote_m / 2
    return [
        (centre_x - demi, centre_y - demi),
        (centre_x + demi, centre_y - demi),
        (centre_x + demi, centre_y + demi),
        (centre_x - demi, centre_y + demi),
        (centre_x - demi, centre_y - demi),
    ]


def _segments_par_indices(semelles):
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
    if tolerance_position_m <= 0:
        raise ValueError("tolerance_position_m doit être strictement positif.")

    def cle_arrondie(valeur):
        return round(valeur / tolerance_position_m)

    segments = []
    par_x = {}
    for s in semelles:
        par_x.setdefault(cle_arrondie(s["position_x"]), []).append(s)
    for groupe in par_x.values():
        groupe.sort(key=lambda s: s["position_y"])
        for a, b in zip(groupe, groupe[1:]):
            segments.append(((a["position_x"], a["position_y"]), (b["position_x"], b["position_y"])))

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
    if not doc.layers.has_entry("DALLAGE"):
        doc.layers.add(name="DALLAGE", color=COULEUR_DALLAGE)

    contour = calculer_contour_dallage(positions_semelles)
    msp.add_lwpolyline(contour, dxfattribs={"layer": "DALLAGE"})

    x_min = min(p[0] for p in contour)
    y_min = min(p[1] for p in contour)
    return x_min, y_min


def _annoter_epaisseur_dallage(msp, x_min, y_min, portee_max_m):
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
    DISTANCE_COTATION_M = 0.8
    if not segments:
        return
    if not doc.layers.has_entry("COTATIONS"):
        doc.layers.add(name="COTATIONS", color=COULEUR_COTATIONS)

    tous_points = [pt for seg in segments for pt in seg]
    centre_x = sum(p[0] for p in tous_points) / len(tous_points)
    centre_y = sum(p[1] for p in tous_points) / len(tous_points)

    for (x1, y1), (x2, y2) in segments:
        dx, dy = x2 - x1, y2 - y1
        longueur = math.hypot(dx, dy)
        if longueur == 0:
            continue

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


def _clusteriser_axe(valeurs, tolerance):
    if not valeurs:
        return []
    valeurs_triees = sorted(valeurs)
    groupes = [[valeurs_triees[0]]]
    for v in valeurs_triees[1:]:
        if v - groupes[-1][-1] <= tolerance:
            groupes[-1].append(v)
        else:
            groupes.append([v])
    return [sum(g) / len(g) for g in groupes]


def _lettre_repere(index_zero_based):
    n = index_zero_based + 1
    lettres = ""
    while n > 0:
        n, reste = divmod(n - 1, 26)
        lettres = chr(65 + reste) + lettres
    return lettres


def _dessiner_axes_reperes(doc, msp, positions_semelles, tolerance_axe_m=0.4, marge_m=1.5):
    if not positions_semelles:
        return {"nb_reperes_numeriques": 0, "nb_reperes_lettres": 0}

    if not doc.layers.has_entry("AXES_REPERES"):
        doc.layers.add(name="AXES_REPERES", color=9)

    xs = [p[0] for p in positions_semelles]
    ys = [p[1] for p in positions_semelles]
    x_min, x_max = min(xs), max(xs)
    y_min, y_max = min(ys), max(ys)

    axes_x = sorted(_clusteriser_axe(xs, tolerance_axe_m))
    axes_y = sorted(_clusteriser_axe(ys, tolerance_axe_m))

    rayon_bulle = max(0.25, min(0.4, marge_m * 0.3))

    for idx, x in enumerate(axes_x, start=1):
        y_bas, y_haut = y_min - marge_m, y_max + marge_m
        msp.add_line((x, y_bas), (x, y_haut), dxfattribs={"layer": "AXES_REPERES"})
        for y_centre in (y_bas - rayon_bulle, y_haut + rayon_bulle):
            centre = (x, y_centre)
            msp.add_circle(centre, rayon_bulle, dxfattribs={"layer": "AXES_REPERES"})
            texte = msp.add_text(
                str(idx), dxfattribs={"layer": "AXES_REPERES", "height": rayon_bulle}
            )
            texte.set_placement(centre, align=TextEntityAlignment.MIDDLE_CENTER)

    for idx, y in enumerate(axes_y, start=0):
        x_gauche, x_droite = x_min - marge_m, x_max + marge_m
        msp.add_line((x_gauche, y), (x_droite, y), dxfattribs={"layer": "AXES_REPERES"})
        lettre = _lettre_repere(idx)
        for x_centre in (x_gauche - rayon_bulle, x_droite + rayon_bulle):
            centre = (x_centre, y)
            msp.add_circle(centre, rayon_bulle, dxfattribs={"layer": "AXES_REPERES"})
            texte = msp.add_text(
                lettre, dxfattribs={"layer": "AXES_REPERES", "height": rayon_bulle}
            )
            texte.set_placement(centre, align=TextEntityAlignment.MIDDLE_CENTER)

    return {"nb_reperes_numeriques": len(axes_x), "nb_reperes_lettres": len(axes_y)}


def _arrondir_taille_superieure(valeur_cm, pas_cm=5):
    return math.ceil(float(valeur_cm) / pas_cm) * pas_cm


def _grouper_par_type(elements, cle_taille, prefixe, pas_cm=5):
    tailles_arrondies = {
        el["identifiant"]: _arrondir_taille_superieure(cle_taille(el), pas_cm) for el in elements
    }
    classes = sorted(set(tailles_arrondies.values()), reverse=True)
    label_par_taille = {taille: f"{prefixe}{i + 1}" for i, taille in enumerate(classes)}
    return {
        identifiant: (label_par_taille[taille], taille)
        for identifiant, taille in tailles_arrondies.items()
    }


def _dessiner_legende_types(msp, x_insert, y_insert, titre, types_comptes, layer="ANNOTATIONS"):
    msp.add_text(
        titre, dxfattribs={"layer": layer, "height": 0.3, "insert": (x_insert, y_insert)}
    )
    for i, (label, taille, hauteur, nb) in enumerate(types_comptes, start=1):
        msp.add_text(
            f"{label} ({taille:.0f}x{taille:.0f}x{hauteur:.0f} cm) : {nb} élément(s)",
            dxfattribs={"layer": layer, "height": 0.22, "insert": (x_insert, y_insert - 0.4 * i)},
        )


def _dessiner_cartouche(msp, x_min, y_min, x_max, y_max, nom_projet=""):
    """
    Dessine et remplit le cartouche technique en bas à droite
    avec des coordonnées parfaitement calées pour l'affichage DXF.
    """
    largeur_cartouche = 10.0
    hauteur_cartouche = 4.0
    
    # Positionné proprement en bas à droite du bâtiment
    x_cart = x_max - largeur_cartouche
    y_cart = y_min - 6.0
    
    if not msp.doc.layers.has_entry("CARTOUCHE"):
        msp.doc.layers.add(name="CARTOUCHE", color=7)
        
    # Cadre extérieur du cartouche
    msp.add_lwpolyline(
        [
            (x_cart, y_cart),
            (x_cart + largeur_cartouche, y_cart),
            (x_cart + largeur_cartouche, y_cart + hauteur_cartouche),
            (x_cart, y_cart + hauteur_cartouche),
            (x_cart, y_cart),
        ],
        dxfattribs={"layer": "CARTOUCHE"}
    )
    
    # Lignes de séparation horizontales internes
    msp.add_line((x_cart, y_cart + 2.6), (x_cart + largeur_cartouche, y_cart + 2.6), dxfattribs={"layer": "CARTOUCHE"})
    msp.add_line((x_cart, y_cart + 1.3), (x_cart + largeur_cartouche, y_cart + 1.3), dxfattribs={"layer": "CARTOUCHE"})
    
    titre_projet = f"PROJET : {nom_projet.upper()}" if nom_projet else "PROJET : BÂTIMENT / STRUCTURE"
    
    # Textes positionnés à l'intérieur des cases du cartouche
    msp.add_text(
        titre_projet,
        dxfattribs={"layer": "CARTOUCHE", "height": 0.3, "insert": (x_cart + 0.3, y_cart + 3.1)}
    )
    msp.add_text(
        "ELEMENT : PLAN DE FONDATION & COFFRAGE",
        dxfattribs={"layer": "CARTOUCHE", "height": 0.2, "insert": (x_cart + 0.3, y_cart + 1.7)}
    )
    msp.add_text(
        "CABINET : BTP INNOVATION -- BAEL 91",
        dxfattribs={"layer": "CARTOUCHE", "height": 0.18, "insert": (x_cart + 0.3, y_cart + 0.5)}
    )


def generer_plan_fondation_dxf(
    nom_projet: str = "",
    semelles=None,
    tolerance_position_m: float = 0.01,
    poutres: list = None,
    longrines: list = None,
    chainages_identifies: list = None,
    dessiner_dallage: bool = True,
    dessiner_joints_dilatation: bool = True,
    dessiner_cotations: bool = True,
    dessiner_axes_reperes: bool = True,
    tolerance_axe_reperes_m: float = 0.4,
    pas_cm_regroupement_semelles: float = 5,
    pas_cm_regroupement_poteaux: float = 5,
) -> bytes:
    if not semelles:
        raise ValueError("Aucune semelle fournie : impossible de générer un plan de fondation.")

    semelles_sans_poteau = [s["identifiant"] for s in semelles if not s.get("poteau_associe")]
    if semelles_sans_poteau:
        raise ValueError(
            "Semelle(s) sans poteau associé : "
            + ", ".join(str(i) for i in semelles_sans_poteau)
        )

    doc = ezdxf.new(dxfversion="R2010")
    doc.layers.add(name="SEMELLES", color=COULEUR_SEMELLES)
    doc.layers.add(name="POTEAUX", color=COULEUR_POTEAUX)
    doc.layers.add(name="CHAINAGE", color=COULEUR_CHAINAGE)
    doc.layers.add(name="ANNOTATIONS", color=COULEUR_ANNOTATIONS)
    msp = doc.modelspace()

    positions_semelles = [(s["position_x"], s["position_y"]) for s in semelles]

    if dessiner_dallage:
        dallage_x_min, dallage_y_min = _dessiner_dallage(doc, msp, positions_semelles)

    if dessiner_axes_reperes:
        diagnostic_axes = _dessiner_axes_reperes(
            doc, msp, positions_semelles, tolerance_axe_m=tolerance_axe_reperes_m
        )

    xs, ys = [], []

    types_semelles = _grouper_par_type(semelles, lambda s: s["cote_cm"], "S", pas_cm=pas_cm_regroupement_semelles)
    types_poteaux = _grouper_par_type(
        [s["poteau_associe"] for s in semelles], lambda p: p["cote_cm"], "P", pas_cm=pas_cm_regroupement_poteaux
    )

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

        label_semelle, taille_semelle = types_semelles[semelle["identifiant"]]
        hauteur_semelle_cm = _arrondir_taille_superieure(semelle.get("hauteur_cm", 40), pas_cm=5)
        msp.add_text(
            f"{label_semelle}({taille_semelle:.0f}x{taille_semelle:.0f}x{hauteur_semelle_cm:.0f})",
            dxfattribs={
                "layer": "ANNOTATIONS",
                "height": max(cote_semelle_m * 0.3, 0.1),
                "insert": (cx + cote_semelle_m / 2 + 0.1, cy),
            },
        )

        label_poteau, _ = types_poteaux[poteau["identifiant"]]
        msp.add_text(
            label_poteau,
            dxfattribs={
                "layer": "POTEAUX",
                "height": max(cote_poteau_m * 0.4, 0.08),
                "insert": (cx - cote_poteau_m / 2 - 0.05, cy + cote_poteau_m / 2 + 0.05),
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

    def _compter_par_type(types_dict, hauteur_par_id=None):
        comptage = {}
        for identifiant, (label, taille) in types_dict.items():
            hauteur = hauteur_par_id.get(identifiant, 0) if hauteur_par_id else 0
            cle = (label, taille, hauteur)
            comptage[cle] = comptage.get(cle, 0) + 1
        return sorted(
            [(label, taille, hauteur, nb) for (label, taille, hauteur), nb in comptage.items()],
            key=lambda t: -t[1],
        )

    hauteur_semelle_par_id = {
        s["identifiant"]: _arrondir_taille_superieure(s.get("hauteur_cm", 40), pas_cm=5) for s in semelles
    }
    _dessiner_legende_types(
        msp, x_min, y_min - 2.3, "Nomenclature semelles :",
        _compter_par_type(types_semelles, hauteur_semelle_par_id),
    )
    poteaux_uniques = {s["poteau_associe"]["identifiant"]: s["poteau_associe"]["cote_cm"] for s in semelles}
    comptage_poteaux = {}
    for identifiant in poteaux_uniques:
        label, taille = types_poteaux[identifiant]
        comptage_poteaux[(label, taille)] = comptage_poteaux.get((label, taille), 0) + 1
    msp.add_text(
        "Nomenclature poteaux :",
        dxfattribs={"layer": "ANNOTATIONS", "height": 0.3, "insert": (x_min + 4.5, y_min - 2.3)},
    )
    for i, ((label, taille), nb) in enumerate(
        sorted(comptage_poteaux.items(), key=lambda t: -t[0][1]), start=1
    ):
        msp.add_text(
            f"{label} ({taille:.0f}x{taille:.0f} cm) : {nb} élément(s)",
            dxfattribs={
                "layer": "ANNOTATIONS", "height": 0.22,
                "insert": (x_min + 4.5, y_min - 2.3 - 0.4 * i),
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

    # Cartouche dynamique sans nom figé
    _dessiner_cartouche(msp, x_min, y_min, max(xs), min(ys), nom_projet=nom_projet)

    tampon = io.StringIO()
    doc.write(tampon)
    return tampon.getvalue().encode("utf-8")