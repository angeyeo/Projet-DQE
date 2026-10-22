"""
Fond de plan d'un DXF d'architecte (issue #93) -- AFFICHAGE SEULEMENT.

Le plan d'architecte (murs, mobilier, pièces) sert de fond sur lequel
l'utilisateur place lui-même les poteaux. Ce module renvoie les traits du
dessin en mètres pour les afficher ; il n'interprète RIEN : aucun poteau,
aucun mur, aucune pièce n'est déduit de ces traits, et ils n'entrent dans
aucun calcul.

Repère renvoyé : origine (0, 0) = coin inférieur gauche de l'emprise du
dessin, axes X vers la droite et Y vers le haut, en mètres. Les poteaux
placés par l'utilisateur sont exprimés dans ce même repère.
"""

from .lecture_dxf import FichierDXFInvalide, _echelle, _ouvrir

# Au-delà, le fond est tronqué (signalé) : un navigateur ne dessine pas
# raisonnablement plus de traits, et le placement des poteaux n'en a pas
# besoin.
NB_SEGMENTS_MAX = 40_000
# Finesse du découpage des arcs et courbes en segments (mètres).
FINESSE_COURBES_M = 0.05
# Profondeur maximale de blocs imbriqués explorés (porte dans un mur...).
PROFONDEUR_BLOCS_MAX = 4
# Entités sans contour utile au placement des poteaux.
TYPES_IGNORES = {"TEXT", "MTEXT", "DIMENSION", "HATCH", "ATTRIB", "ATTDEF", "POINT", "IMAGE", "WIPEOUT",
                 "LEADER", "MLEADER", "VIEWPORT", "SOLID", "3DFACE", "MESH"}


class FondPlanVide(Exception):
    """Aucun trait exploitable : rien à afficher."""


def _entites(entites, profondeur=0):
    for e in entites:
        t = e.dxftype()
        if t == "INSERT":
            if profondeur < PROFONDEUR_BLOCS_MAX:
                try:
                    yield from _entites(e.virtual_entities(), profondeur + 1)
                except Exception:  # bloc mal formé : ignoré (compté par l'appelant via le total)
                    continue
        elif t not in TYPES_IGNORES:
            yield e


def lire_fond_plan(chemin):
    """Traits du dessin en mètres, dans le repère local (voir module).

    Retour : {"unite", "largeur_m", "profondeur_m", "segments": [[x1, y1, x2, y2], ...],
              "nb_segments", "tronque", "avertissements"}.
    Lève FichierDXFInvalide (fichier ou unités) ou FondPlanVide.
    """
    from ezdxf import path as ezpath

    doc = _ouvrir(chemin)
    unite, echelle = _echelle(doc)
    finesse = FINESSE_COURBES_M / echelle  # en unités du dessin

    bruts, tronque = [], False
    for e in _entites(doc.modelspace()):
        try:
            p = ezpath.make_path(e)
        except (TypeError, ValueError):
            continue  # entité sans contour (ou non gérée) : ignorée
        sommets = [(v.x, v.y) for v in p.flattening(finesse)] if len(p) else []
        for (x1, y1), (x2, y2) in zip(sommets, sommets[1:]):
            if (x1, y1) == (x2, y2):
                continue
            if len(bruts) >= NB_SEGMENTS_MAX:
                tronque = True
                break
            bruts.append((x1 * echelle, y1 * echelle, x2 * echelle, y2 * echelle))
        if tronque:
            break

    if not bruts:
        raise FondPlanVide("Ce DXF ne contient aucun trait exploitable à afficher comme fond de plan.")

    x_min = min(min(s[0], s[2]) for s in bruts)
    y_min = min(min(s[1], s[3]) for s in bruts)
    x_max = max(max(s[0], s[2]) for s in bruts)
    y_max = max(max(s[1], s[3]) for s in bruts)
    segments = [[round(x1 - x_min, 3), round(y1 - y_min, 3), round(x2 - x_min, 3), round(y2 - y_min, 3)]
                for x1, y1, x2, y2 in bruts]

    avertissements = []
    if tronque:
        avertissements.append(
            f"Dessin très chargé : seuls les {NB_SEGMENTS_MAX} premiers traits sont affichés en fond de plan. "
            "Placez les poteaux avec les cotes, ou allégez l'export (calques de mobilier masqués).")
    largeur, profondeur = x_max - x_min, y_max - y_min
    if max(largeur, profondeur) > 200:
        avertissements.append(
            f"Dessin de {largeur:.0f} × {profondeur:.0f} m : le fichier contient sans doute plusieurs plans ou "
            "des éléments éloignés. Placez les poteaux sur le plan du rez-de-chaussée.")
    return {
        "unite": unite,
        "largeur_m": round(largeur, 3),
        "profondeur_m": round(profondeur, 3),
        "segments": segments,
        "nb_segments": len(segments),
        "tronque": tronque,
        "avertissements": avertissements,
    }


__all__ = ["FichierDXFInvalide", "FondPlanVide", "lire_fond_plan", "NB_SEGMENTS_MAX"]
