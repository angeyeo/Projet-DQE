"""
Compléments du plan de coffrage -- Phase C (voir
Feuille_de_route_Import_Plan_Automatique.md, §4 "Risques principaux à
surveiller" point 4 : le plan de référence montre une vraie complexité
de chantier -- joints de dilatation et dallage largement au-delà de ce
que le moteur calculait jusqu'ici).

Comme trame.py et import_ifc/lecture_ifc.py, ce module reste une
fonction PURE de géométrie/calcul : aucune dépendance Django, aucun
accès DXF. Il prend en entrée le nuage de positions (x, y) des
poteaux/semelles déjà connu (grille régulière ou positions réelles
importées, peu importe -- ces calculs ne dépendent que de l'emprise
globale du bâtiment) et renvoie des données géométriques exploitables
par n'importe quel appelant, notamment
projets/services/plan_fondation.py (tracé DXF).

Testable en isolation, comme le reste du moteur -- voir
moteur_calcul/tests_moteur_calcul/test_complements_plan_coffrage.py.
"""

import math

from ..constantes import DISTANCE_MAX_JOINT_DILATATION_M, MARGE_DALLAGE_M


def _emprise(positions: list) -> tuple:
    """Bounding box (x_min, x_max, y_min, y_max) d'un nuage de points (x, y)."""
    if not positions:
        raise ValueError("Aucune position fournie : impossible de calculer l'emprise du bâtiment.")
    xs = [p[0] for p in positions]
    ys = [p[1] for p in positions]
    return min(xs), max(xs), min(ys), max(ys)


def calculer_contour_dallage(positions: list, marge_m: float = MARGE_DALLAGE_M) -> list:
    """
    Contour rectangulaire du dallage (dalle sur terre-plein) : l'emprise
    extérieure des poteaux/semelles, augmentée d'un débord constructif
    forfaitaire (`marge_m`, voir MARGE_DALLAGE_M) sur chaque côté.

    MVP volontairement simple : un rectangle englobant, pas le contour
    réel du bâtiment (qui peut être en L, en T, etc.) -- suffisant tant
    que la Phase B ne fournit que des positions de poteaux, pas un
    polygone d'emprise architecturale. À enrichir avec une véritable
    enveloppe (convex hull ou contour architectural importé) si le
    rectangle s'avère trop grossier sur des bâtiments non rectangulaires.

    positions : liste de tuples/list (x, y), en mètres.
    marge_m : débord de la dalle au-delà de l'emprise des poteaux, en
    mètres (doit être >= 0).

    Retour : liste de 5 tuples (x, y) fermée (premier point répété en
    dernier), prête à être dessinée comme une polyligne fermée.

    Lève ValueError si `positions` est vide ou si `marge_m` est négatif.
    """
    if marge_m < 0:
        raise ValueError("marge_m doit être positif ou nul.")

    x_min, x_max, y_min, y_max = _emprise(positions)
    x_min, x_max = x_min - marge_m, x_max + marge_m
    y_min, y_max = y_min - marge_m, y_max + marge_m

    return [
        (x_min, y_min),
        (x_max, y_min),
        (x_max, y_max),
        (x_min, y_max),
        (x_min, y_min),
    ]


def calculer_joints_dilatation(
    positions: list, distance_max_m: float = DISTANCE_MAX_JOINT_DILATATION_M,
    marge_m: float = MARGE_DALLAGE_M,
) -> dict:
    """
    Détermine si le bâtiment nécessite des joints de dilatation (sa plus
    grande dimension, en X ou en Y, dépasse `distance_max_m`) et calcule
    leurs positions, réparties régulièrement pour découper le bâtiment en
    tronçons de longueur égale et toujours <= distance_max_m.

    Ex. un bâtiment de 60 m de long avec distance_max_m=25 est découpé
    en 3 tronçons de 20 m (pas 2 tronçons de 30 m, qui dépasseraient la
    limite) -- 2 joints de dilatation, régulièrement espacés plutôt que
    calés uniquement tous les 25 m depuis une extrémité, pratique plus
    propre pour l'implantation chantier.

    positions : liste de tuples/list (x, y), en mètres -- typiquement
    les positions de poteaux/semelles (Phase A/B).
    distance_max_m : portée maximale sans joint (voir
    DISTANCE_MAX_JOINT_DILATATION_M -- à ajuster selon l'étude
    structurelle réelle si elle diffère de l'hypothèse par défaut).
    marge_m : les joints traversent toute la largeur du dallage
    (calculer_contour_dallage()), pas seulement l'emprise des poteaux --
    cohérence visuelle avec le contour de dallage tracé sur le même plan.

    Retour :
    {
        "joints": [
            {"axe": "X"|"Y", "position": float, "x1", "y1", "x2", "y2"},
            ...
        ],
        "avertissements": [str, ...],
    }

    "axe" == "X" signifie un joint vertical sur le plan, situé à une
    abscisse X donnée (coupe le bâtiment selon sa longueur en X) ; "Y"
    l'inverse. Liste vide si le bâtiment tient dans distance_max_m sur
    les deux axes -- ce n'est pas une erreur, juste l'absence de besoin.
    """
    if distance_max_m <= 0:
        raise ValueError("distance_max_m doit être strictement positif.")

    x_min, x_max, y_min, y_max = _emprise(positions)
    longueur_x = x_max - x_min
    longueur_y = y_max - y_min

    joints = []
    avertissements = []

    joints += _joints_sur_axe(
        "X", x_min, x_max, y_min - marge_m, y_max + marge_m, longueur_x,
        distance_max_m, avertissements,
    )
    joints += _joints_sur_axe(
        "Y", y_min, y_max, x_min - marge_m, x_max + marge_m, longueur_y,
        distance_max_m, avertissements,
    )

    return {"joints": joints, "avertissements": avertissements}


def _joints_sur_axe(axe, debut, fin, perp_min, perp_max, longueur, distance_max_m, avertissements):
    """
    Calcule les positions de joints le long d'un seul axe ("X" ou "Y")
    et les segments perpendiculaires correspondants (qui traversent
    toute la largeur `perp_min`..`perp_max` du bâtiment sur l'autre axe).
    """
    if longueur <= distance_max_m or longueur <= 0:
        return []

    nb_troncons = math.ceil(longueur / distance_max_m)
    longueur_troncon = longueur / nb_troncons
    nb_joints = nb_troncons - 1

    avertissements.append(
        f"Bâtiment de {longueur:.1f} m selon l'axe {axe} > {distance_max_m:.0f} m -- "
        f"{nb_joints} joint(s) de dilatation requis (tronçons de "
        f"{longueur_troncon:.1f} m), à confirmer par l'étude structurelle "
        f"réelle (hypothèse par défaut : DISTANCE_MAX_JOINT_DILATATION_M)."
    )

    joints = []
    for k in range(1, nb_troncons):
        position = debut + k * longueur_troncon
        if axe == "X":
            joints.append({
                "axe": "X", "position": position,
                "x1": position, "y1": perp_min, "x2": position, "y2": perp_max,
            })
        else:
            joints.append({
                "axe": "Y", "position": position,
                "x1": perp_min, "y1": position, "x2": perp_max, "y2": position,
            })
    return joints
