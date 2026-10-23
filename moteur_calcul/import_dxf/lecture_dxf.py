"""
Import de plan DXF (AutoCAD, ArchiCAD...) -- lecture des POTEAUX et des
MURS, pour construire la trame réelle avec le même moteur que l'import
IFC (generer_poteau_depuis_position_reelle).

Ce que le module lit, et rien d'autre :
  - les unités déclarées par le fichier ($INSUNITS : mm, cm ou m) ;
    sans unité déclarée, le fichier est refusé (aucune échelle supposée) ;
  - les poteaux = blocs insérés dont le NOM ou le CALQUE désigne un poteau
    (Column_12, POTEAU, Poteaux...) ; position = centre de l'emprise du
    bloc ;
  - les murs = blocs dont le nom ou le calque désigne un mur, rectilignes
    et parallèles aux axes ; axe = ligne médiane du rectangle ;
  - les dalles (issue #80) = blocs, ou polylignes fermées, dont le nom ou le
    calque désigne une dalle ou un plancher (Slab_1, DALLES, PLANCHER...),
    seulement si leur contour est un RECTANGLE parallèle aux axes : Lx, Ly
    = côtés du rectangle. Une autre forme n'est pas lue (signalée) : elle se
    saisit à la main. Les dalles sont PROPOSÉES, jamais créées sans accord.

Un DXF peut contenir plusieurs plans posés côte à côte (rez-de-chaussée,
étage...) sans que le fichier dise lequel est lequel : les poteaux sont
regroupés en PLANS par proximité, et l'UTILISATEUR choisit celui qui
porte les fondations. Rien n'est deviné : ce qui n'est pas reconnu est
compté et signalé.
"""

import math
import re

# Unités DXF ($INSUNITS) -> mètres. Les autres codes (pouces, pieds,
# 0 = sans unité) sont refusés : aucune échelle n'est supposée.
ECHELLES_UNITES = {4: ("mm", 0.001), 5: ("cm", 0.01), 6: ("m", 1.0)}

# Deux poteaux plus proches que ceci sont le même poteau dessiné deux fois.
TOLERANCE_DOUBLON_M = 0.10
# Deux plans posés côte à côte sont séparés par un vide plus grand que
# ceci entre leurs poteaux (une travée de bâtiment courant fait < 8 m).
ECART_ENTRE_PLANS_M = 8.0
# Mur rectiligne : rectangle dont le petit côté (l'épaisseur) ne dépasse
# pas ceci ; au-delà, mur oblique, en L ou autre forme -- non lu.
EPAISSEUR_MUR_MAX_M = 0.40
LONGUEUR_MUR_MIN_M = 0.30
# Association d'un mur à une poutre : axe du mur à moins de cette
# distance de l'axe de la poutre, et recouvrement d'au moins cette part
# de la portée.
ECART_MUR_POUTRE_MAX_M = 0.25
RECOUVREMENT_MUR_MIN = 0.5

MOTIF_POTEAU = re.compile(r"(^|[^a-z])(columns?|colonnes?|poteaux?)([^a-z]|$)", re.IGNORECASE)
MOTIF_MUR = re.compile(r"(^|[^a-z])(walls?|murs?)([^a-z]|$)", re.IGNORECASE)
MOTIF_DALLE = re.compile(r"(^|[^a-z])(slabs?|dalles?|planchers?|floors?)([^a-z]|$)", re.IGNORECASE)
# Contour d'une dalle accepté comme rectangle si son aire diffère de moins
# de ceci de l'aire de son rectangle englobant (tracés arrondis au mm).
TOLERANCE_RECTANGLE = 0.01
COTE_DALLE_MIN_M = 0.50
NUMERO_FINAL = re.compile(r"[_ ]?\d+$")


class FichierDXFInvalide(Exception):
    """Fichier illisible ou inexploitable (format, unités)."""


class AucunPoteauDXF(Exception):
    """Aucun poteau reconnu : le message dit ce que le fichier contient."""


def _ouvrir(chemin):
    try:
        import ezdxf
        from ezdxf import bbox  # noqa: F401 -- vérifie la présence du module
    except ImportError as exc:  # pragma: no cover - dépendance installée
        raise FichierDXFInvalide(f"Lecteur DXF indisponible sur ce serveur : {exc}") from exc
    try:
        return ezdxf.readfile(chemin)
    except (IOError, OSError) as exc:
        raise FichierDXFInvalide(f"Fichier DXF illisible : {exc}") from exc
    except ezdxf.DXFError as exc:
        raise FichierDXFInvalide(
            f"Ce fichier n'est pas un DXF valide ({exc}). Réexportez le plan au format DXF depuis votre logiciel."
        ) from exc


def _echelle(doc):
    code = doc.header.get("$INSUNITS", 0)
    if code not in ECHELLES_UNITES:
        raise FichierDXFInvalide(
            "Unités du dessin non déclarées ou non gérées dans ce DXF "
            f"(code $INSUNITS = {code}). Réexportez le plan en millimètres, centimètres ou mètres."
        )
    return ECHELLES_UNITES[code]


def _emprise(insert, echelle, sans_blocs_imbriques=False):
    """(x_min, y_min, x_max, y_max) en mètres de la géométrie d'un bloc inséré.
    sans_blocs_imbriques : ignore les blocs contenus (portes et fenêtres
    d'un mur, dont le symbole d'ouverture déborde de l'épaisseur)."""
    from ezdxf import bbox

    entites = insert.virtual_entities()
    if sans_blocs_imbriques:
        entites = [e for e in entites if e.dxftype() != "INSERT"]
    b = bbox.extents(entites, fast=True)
    if not b.has_data:
        return None
    return (b.extmin.x * echelle, b.extmin.y * echelle, b.extmax.x * echelle, b.extmax.y * echelle)


def _nature(insert):
    """"poteau", "mur" ou None, d'après le nom du bloc puis son calque."""
    nom, calque = insert.dxf.name or "", insert.dxf.layer or ""
    for texte in (nom, calque):
        if MOTIF_POTEAU.search(texte.replace("_", " ")):
            return "poteau"
        if MOTIF_MUR.search(texte.replace("_", " ")):
            return "mur"
        if MOTIF_DALLE.search(texte.replace("_", " ")):
            return "dalle"
    return None


def _aire_polyligne(points):
    """Aire (formule du lacet) d'un contour fermé, en unités du dessin²."""
    n = len(points)
    return abs(sum(points[i][0] * points[(i + 1) % n][1] - points[(i + 1) % n][0] * points[i][1]
                   for i in range(n))) / 2


def _dalle_rectangulaire(entites, echelle):
    """(x0, y0, x1, y1) en mètres si le plus grand contour fermé est un
    rectangle parallèle aux axes ; sinon None (forme non lue)."""
    contours = []
    for e in entites:
        if e.dxftype() == "LWPOLYLINE" and e.closed:
            contours.append([(p[0], p[1]) for p in e.get_points("xy")])
        elif e.dxftype() == "POLYLINE" and e.is_closed:
            contours.append([(v.dxf.location.x, v.dxf.location.y) for v in e.vertices])
    contours = [c for c in contours if len(c) >= 4]
    if not contours:
        return None
    c = max(contours, key=_aire_polyligne)
    xs, ys = [p[0] for p in c], [p[1] for p in c]
    x0, x1, y0, y1 = min(xs), max(xs), min(ys), max(ys)
    englobant = (x1 - x0) * (y1 - y0)
    if englobant <= 0 or abs(_aire_polyligne(c) - englobant) > TOLERANCE_RECTANGLE * englobant:
        return None
    return (x0 * echelle, y0 * echelle, x1 * echelle, y1 * echelle)


def _regrouper_en_plans(poteaux):
    """Groupes de poteaux connexes (lien simple : un poteau rejoint un
    groupe s'il est à moins de ECART_ENTRE_PLANS_M d'un de ses poteaux)."""
    groupes = []
    restants = list(poteaux)
    while restants:
        groupe = [restants.pop(0)]
        i = 0
        while i < len(groupe):
            p = groupe[i]
            proches = [q for q in restants if math.hypot(p["x"] - q["x"], p["y"] - q["y"]) <= ECART_ENTRE_PLANS_M]
            for q in proches:
                restants.remove(q)
            groupe.extend(proches)
            i += 1
        groupes.append(groupe)
    # Ordre de lecture : de gauche à droite, puis de haut en bas.
    groupes.sort(key=lambda g: (round(min(p["x"] for p in g), 0), -max(p["y"] for p in g)))
    return groupes


def _fusionner_doublons(poteaux):
    uniques, doublons = [], []
    for p in poteaux:
        jumeau = next((u for u in uniques if math.hypot(p["x"] - u["x"], p["y"] - u["y"]) < TOLERANCE_DOUBLON_M), None)
        if jumeau is None:
            uniques.append(p)
        else:
            doublons.append((p["nom"], jumeau["nom"]))
    return uniques, doublons


def _mur_rectiligne(emprise):
    """Axe d'un mur rectangulaire parallèle aux axes, ou None."""
    x0, y0, x1, y1 = emprise
    larg, haut = x1 - x0, y1 - y0
    epaisseur, longueur = min(larg, haut), max(larg, haut)
    if epaisseur > EPAISSEUR_MUR_MAX_M or longueur < LONGUEUR_MUR_MIN_M:
        return None
    if larg >= haut:
        ym = (y0 + y1) / 2
        return {"axe": "x", "debut": (x0, ym), "fin": (x1, ym), "epaisseur_m": round(epaisseur, 3)}
    xm = (x0 + x1) / 2
    return {"axe": "y", "debut": (xm, y0), "fin": (xm, y1), "epaisseur_m": round(epaisseur, 3)}


def lire_dxf(chemin):
    """Lecture brute : poteaux et murs en mètres (coordonnées du dessin).
    Lève FichierDXFInvalide / AucunPoteauDXF."""
    doc = _ouvrir(chemin)
    unite, echelle = _echelle(doc)
    poteaux, murs, murs_ignores, murs_courts, inconnus = [], [], 0, 0, {}
    dalles, dalles_ignorees = [], 0

    def ajouter_dalle(rect, nom, handle):
        nonlocal dalles_ignorees
        if rect is None:
            dalles_ignorees += 1
            return
        x0, y0, x1, y1 = rect
        cotes = sorted((x1 - x0, y1 - y0))
        if cotes[0] < COTE_DALLE_MIN_M:
            dalles_ignorees += 1
            return
        dalles.append({"id": f"dxf-{handle}", "nom": nom, "x": (x0 + x1) / 2, "y": (y0 + y1) / 2,
                       "lx": round(cotes[0], 3), "ly": round(cotes[1], 3),
                       "emprise": (x0, y0, x1, y1)})

    # Dalles dessinées en polylignes fermées sur un calque « dalle ».
    for pl in doc.modelspace().query("LWPOLYLINE POLYLINE"):
        if MOTIF_DALLE.search((pl.dxf.layer or "").replace("_", " ")) and \
                (pl.closed if pl.dxftype() == "LWPOLYLINE" else pl.is_closed):
            ajouter_dalle(_dalle_rectangulaire([pl], echelle), pl.dxf.layer, pl.dxf.handle)
    for insert in doc.modelspace().query("INSERT"):
        nature = _nature(insert)
        if nature == "dalle":
            ajouter_dalle(_dalle_rectangulaire(list(insert.virtual_entities()), echelle), insert.dxf.name,
                          insert.dxf.handle)
            continue
        if nature is None:
            cle = f"{insert.dxf.layer} / {NUMERO_FINAL.sub('', insert.dxf.name)}"
            inconnus[cle] = inconnus.get(cle, 0) + 1
            continue
        emprise = _emprise(insert, echelle, sans_blocs_imbriques=(nature == "mur"))
        if emprise is None:
            continue
        if nature == "poteau":
            x0, y0, x1, y1 = emprise
            poteaux.append({"nom": insert.dxf.name, "guid": f"dxf-{insert.dxf.handle}",
                            "x": (x0 + x1) / 2, "y": (y0 + y1) / 2,
                            "emprise_cm": (round((x1 - x0) * 100), round((y1 - y0) * 100))})
        else:
            mur = _mur_rectiligne(emprise)
            if mur is None and max(emprise[2] - emprise[0], emprise[3] - emprise[1]) < LONGUEUR_MUR_MIN_M:
                murs_courts += 1
            elif mur is None:
                murs_ignores += 1
            else:
                murs.append({**mur, "nom": insert.dxf.name})
    if not poteaux:
        apercu = ", ".join(f"{k} ({n})" for k, n in sorted(inconnus.items(), key=lambda kv: -kv[1])[:12])
        raise AucunPoteauDXF(
            "Aucun poteau reconnu dans ce DXF. Le logiciel lit les blocs dont le nom ou le calque contient "
            "« poteau » ou « column » (ex. calque POTEAUX, bloc Column_1). "
            + (f"Blocs trouvés (calque / bloc) : {apercu}." if apercu else "Le fichier ne contient aucun bloc : "
               "les poteaux sont sans doute dessinés en simples traits ; regroupez-les en blocs sur un calque POTEAUX.")
        )
    return {"unite": unite, "poteaux": poteaux, "murs": murs, "murs_ignores": murs_ignores, "murs_courts": murs_courts,
            "dalles": dalles, "dalles_ignorees": dalles_ignorees}


def _dans_emprise(point, plan, marge=1.0):
    return (plan["x_min"] - marge <= point[0] <= plan["x_max"] + marge
            and plan["y_min"] - marge <= point[1] <= plan["y_max"] + marge)


def analyser_fichier_dxf(chemin, plan=None):
    """Aperçu de l'import : plans détectés et, si `plan` est choisi (ou
    s'il n'y en a qu'un), ses poteaux et murs en coordonnées LOCALES
    (origine = coin inférieur gauche de ses poteaux, en mètres).

    Retour : {"format", "unite", "plans": [...], "plan_retenu", et pour le
    plan retenu : "poteaux", "murs", "avertissements"}.
    """
    brut = lire_dxf(chemin)
    groupes = _regrouper_en_plans(brut["poteaux"])
    plans = []
    for i, g in enumerate(groupes, start=1):
        uniques, doublons = _fusionner_doublons(g)
        x_min, y_min = min(p["x"] for p in g), min(p["y"] for p in g)
        x_max, y_max = max(p["x"] for p in g), max(p["y"] for p in g)
        info = {"id": f"plan-{i}", "x_min": x_min, "y_min": y_min, "x_max": x_max, "y_max": y_max}
        murs = [m for m in brut["murs"]
                if _dans_emprise(m["debut"], info) and _dans_emprise(m["fin"], info)]
        dalles = [d for d in brut["dalles"] if _dans_emprise((d["x"], d["y"]), info)]
        plans.append({
            **info, "_poteaux": uniques, "_doublons": doublons, "_murs": murs, "_dalles": dalles,
            "nb_poteaux": len(uniques), "nb_doublons": len(doublons), "nb_murs": len(murs),
            "largeur_m": round(x_max - x_min, 2), "profondeur_m": round(y_max - y_min, 2),
            # Positions locales (m) pour la vignette de choix du plan.
            "poteaux_apercu": [[round(p["x"] - x_min, 2), round(p["y"] - y_min, 2)] for p in uniques],
        })

    if plan is None and len(plans) == 1:
        plan = plans[0]["id"]
    retenu = next((p for p in plans if p["id"] == plan), None)
    if plan is not None and retenu is None:
        raise FichierDXFInvalide(f"Plan « {plan} » introuvable dans ce fichier (plans : "
                                 f"{', '.join(p['id'] for p in plans)}).")

    resultat = {
        "format": "dxf", "unite": brut["unite"],
        "plans": [{k: v for k, v in p.items() if not k.startswith("_")} for p in plans],
        "plan_retenu": retenu["id"] if retenu else None,
        "nb_poteaux_detectes": sum(p["nb_poteaux"] for p in plans),
        "avertissements": [],
    }
    if len(plans) > 1:
        resultat["avertissements"].append(
            f"{len(plans)} plans dans le fichier : plan {retenu['id'].removeprefix('plan-')} retenu pour les "
            "fondations, les autres ne sont pas utilisés pour la trame." if retenu else
            f"{len(plans)} plans détectés côte à côte dans le fichier : choisissez celui des fondations "
            "(rez-de-chaussée). Les autres ne sont pas utilisés pour la trame.")
    if brut["murs_courts"]:
        resultat["avertissements"].append(
            f"{brut['murs_courts']} morceau(x) de mur de moins de {LONGUEUR_MUR_MIN_M * 100:g} cm ignoré(s) "
            "(trumeaux, retours) : sans effet sur la trame.")
    if brut["murs_ignores"]:
        resultat["avertissements"].append(
            f"{brut['murs_ignores']} mur(s) non lu(s) : obliques, en L ou plus épais que "
            f"{EPAISSEUR_MUR_MAX_M:g} m. Placez-les à la main sur le plan des murs.")
    if retenu is None:
        return resultat

    x0, y0 = retenu["x_min"], retenu["y_min"]
    resultat["poteaux"] = [{**p, "x": p["x"] - x0, "y": p["y"] - y0, "niveau_elevation_m": 0.0,
                            "niveau_nom": retenu["id"]} for p in retenu["_poteaux"]]
    resultat["murs"] = [{**m, "debut": (m["debut"][0] - x0, m["debut"][1] - y0),
                         "fin": (m["fin"][0] - x0, m["fin"][1] - y0)} for m in retenu["_murs"]]
    resultat["dalles"] = [{"id": d["id"], "nom": d["nom"], "lx": d["lx"], "ly": d["ly"],
                           "x": round(d["x"] - x0, 3), "y": round(d["y"] - y0, 3),
                           "emprise": [round(d["emprise"][0] - x0, 3), round(d["emprise"][1] - y0, 3),
                                       round(d["emprise"][2] - x0, 3), round(d["emprise"][3] - y0, 3)]}
                          for d in retenu["_dalles"]]
    if brut["dalles_ignorees"]:
        resultat["avertissements"].append(
            f"{brut['dalles_ignorees']} dalle(s) non lue(s) : contour non rectangulaire ou côté de moins de "
            f"{COTE_DALLE_MIN_M:g} m. Saisissez-les à l'étape Dalles.")
    if retenu["_doublons"]:
        resultat["avertissements"].append(
            f"{len(retenu['_doublons'])} poteau(x) dessiné(s) deux fois au même endroit, comptés une seule fois : "
            + ", ".join(f"{a} = {b}" for a, b in retenu["_doublons"]) + ".")
    resultat["avertissements"].append(
        "Section des poteaux non lue dans le DXF : elle est calculée par le moteur. Nombre de niveaux et "
        "hauteur d'étage non lus : à renseigner dans le formulaire.")
    return resultat


def associer_murs_aux_poutres(murs, troncons):
    """Tronçons de poutre qui portent un mur du plan.

    troncons : [(cle, (xa, ya), (xb, yb))] -- poutres entre poteaux voisins.
    Un mur est rattaché à un tronçon de même direction si son axe est à
    moins de ECART_MUR_POUTRE_MAX_M de celui de la poutre et s'il recouvre
    au moins RECOUVREMENT_MUR_MIN de sa portée (plusieurs murs bout à bout
    s'additionnent). Renvoie la liste triée des clés retenues.
    """
    retenues = []
    for cle, a, b in troncons:
        horizontal = abs(a[1] - b[1]) < abs(a[0] - b[0])
        k_long, k_trav = (0, 1) if horizontal else (1, 0)
        lo, hi = sorted((a[k_long], b[k_long]))
        portee = hi - lo
        if portee <= 0:
            continue
        ligne = (a[k_trav] + b[k_trav]) / 2
        couvert = 0.0
        for m in murs:
            if (m["axe"] == "x") != horizontal:
                continue
            if abs(m["debut"][k_trav] - ligne) > ECART_MUR_POUTRE_MAX_M:
                continue
            m_lo, m_hi = sorted((m["debut"][k_long], m["fin"][k_long]))
            couvert += max(0.0, min(hi, m_hi) - max(lo, m_lo))
        if couvert >= RECOUVREMENT_MUR_MIN * portee:
            retenues.append(cle)
    return sorted(set(retenues))
