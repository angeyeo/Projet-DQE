"""
Import de plans architecte -- Phase A de la feuille de route "Import
plan automatique" (voir Feuille_de_route_Import_Plan_Automatique.md).

Objectif de cette phase : lire un fichier IFC (export ArchiCAD/Robot,
PAS le .pln propriétaire -- voir la feuille de route pour le pourquoi),
en extraire les poteaux et les niveaux, et en déduire des paramètres de
trame RÉGULIÈRE (nb_travees_x/y, portee_x/y, nb_niveaux, hauteur_etage)
qui viennent pré-remplir le formulaire Étape 1 -- l'utilisateur garde la
main pour corriger avant de lancer generer_trame/.

Ne crée aucun ElementStructurel ici : ce module reste une fonction pure
de lecture/analyse, testable en isolation, comme trame.py. La Phase B
(positions réelles individuelles, sans grille uniforme) viendra ajouter
un autre chemin de création d'éléments qui réutilisera extraire_poteaux()
et extraire_niveaux() directement, sans passer par la régularisation en
grille faite ici par detecter_parametres_trame().

Dépendance : ifcopenshell (pip install ifcopenshell). Voir
requirements.txt.
"""

from collections import Counter
from statistics import mean, pstdev

import ifcopenshell
import ifcopenshell.util.element as element_util
import ifcopenshell.util.placement as placement_util

# Tolérance (mètres) pour considérer deux poteaux comme alignés sur la
# même "ligne" de grille -- les relevés réels ne sont jamais parfaitement
# alignés à la coordonnée près. 15 cm est un compromis raisonnable pour
# du gros œuvre BTP (à ajuster si les premiers imports réels du
# technicien montrent qu'il faut resserrer/élargir).
TOLERANCE_ALIGNEMENT_M = 0.15

# Si l'écart-type des portées détectées dépasse ce ratio de leur moyenne,
# on considère la grille trop irrégulière pour qu'une portee_x/y unique
# soit fiable -- on renvoie quand même une valeur (moyenne), mais avec un
# avertissement explicite pour l'utilisateur.
SEUIL_IRREGULARITE = 0.15  # 15% de variation


class FichierIFCInvalide(Exception):
    """Levée quand le fichier fourni n'est pas un IFC exploitable."""


class AucunPoteauDetecte(Exception):
    """Levée quand l'IFC s'ouvre mais ne contient aucun IfcColumn."""


def ouvrir_ifc(chemin_fichier: str):
    """
    Ouvre un fichier IFC. Lève FichierIFCInvalide avec un message clair
    si le fichier n'est pas un IFC lisible (mauvais format, fichier
    corrompu, export .pln renommé en .ifc par erreur, etc.).
    """
    try:
        return ifcopenshell.open(chemin_fichier)
    except Exception as exc:  # ifcopenshell lève des types variés selon la cause
        raise FichierIFCInvalide(
            f"Impossible de lire ce fichier comme un IFC valide : {exc}. "
            f"Vérifiez qu'il s'agit bien d'un export IFC (pas du .pln natif "
            f"ArchiCAD, qui n'est pas un format ouvert -- voir la feuille de "
            f"route pour l'export à demander au technicien)."
        ) from exc


def extraire_niveaux(model) -> list:
    """
    Retourne les IfcBuildingStorey du modèle, triés par élévation
    croissante : [{"nom": ..., "elevation_m": ..., "guid": ...}, ...].
    """
    storeys = model.by_type("IfcBuildingStorey")
    niveaux = [
        {
            "nom": s.Name or f"Niveau {i}",
            "elevation_m": float(s.Elevation) if s.Elevation is not None else 0.0,
            "guid": s.GlobalId,
        }
        for i, s in enumerate(storeys)
    ]
    return sorted(niveaux, key=lambda n: n["elevation_m"])


def extraire_poteaux(model) -> list:
    """
    Retourne la liste des IfcColumn du modèle avec leur position réelle
    et leur niveau d'appartenance :
        [{"nom", "guid", "x", "y", "z", "niveau_nom", "niveau_elevation_m"}, ...]

    Position exprimée dans le placement local de l'objet -- suffisant
    pour la détection de trame (Phase A) ; la Phase B (positions
    absolues précises pour un import multi-bâtiment) pourra affiner en
    composant les placements parents si besoin.
    """
    poteaux = []
    for col in model.by_type("IfcColumn"):
        if not col.ObjectPlacement:
            continue  # élément sans position exploitable -- ignoré, pas bloquant
        matrice = placement_util.get_local_placement(col.ObjectPlacement)
        x, y, z = float(matrice[0][3]), float(matrice[1][3]), float(matrice[2][3])

        storey = element_util.get_container(col)
        niveau_nom = getattr(storey, "Name", None) or "Niveau inconnu"
        niveau_elevation = float(getattr(storey, "Elevation", 0.0) or 0.0)

        poteaux.append({
            "nom": col.Name or col.GlobalId,
            "guid": col.GlobalId,
            "x": x,
            "y": y,
            "z": z,
            "niveau_nom": niveau_nom,
            "niveau_elevation_m": niveau_elevation,
        })

    if not poteaux:
        raise AucunPoteauDetecte(
            "Aucun IfcColumn trouvé dans ce fichier -- vérifiez que l'export "
            "IFC inclut bien la structure porteuse (poteaux) et pas "
            "uniquement l'architecture (murs, portes, etc.)."
        )
    return poteaux


def _clusteriser_1d(valeurs: list, tolerance: float = TOLERANCE_ALIGNEMENT_M) -> list:
    """
    Regroupe des coordonnées proches (relevé réel, jamais parfaitement
    aligné) en "lignes de grille" : trie les valeurs, puis démarre un
    nouveau groupe dès que l'écart avec la valeur précédente dépasse la
    tolérance. Retourne la position moyenne de chaque groupe, triée.

    Ex. [0.0, 0.03, 4.98, 5.02, 10.01] (tolérance 0.15) -> [0.015, 5.0, 10.01]
    """
    if not valeurs:
        return []
    valeurs_triees = sorted(valeurs)
    groupes = [[valeurs_triees[0]]]
    for v in valeurs_triees[1:]:
        if v - groupes[-1][-1] <= tolerance:
            groupes[-1].append(v)
        else:
            groupes.append([v])
    return [mean(g) for g in groupes]


def detecter_parametres_trame(poteaux: list, niveaux: list = None) -> dict:
    """
    À partir de la liste de poteaux (extraire_poteaux()) et, si
    disponible, des niveaux (extraire_niveaux()), déduit des paramètres
    de trame RÉGULIÈRE utilisables pour pré-remplir l'Étape 1 :

    {
        "nb_travees_x": int, "nb_travees_y": int,
        "portee_x": float, "portee_y": float,      # mètres, moyenne
        "nb_niveaux": int, "hauteur_etage": float,  # mètres, moyenne
        "nb_poteaux_detectes": int,
        "avertissements": [str, ...],
    }

    Ne lève pas d'exception sur une grille irrégulière : renvoie une
    meilleure estimation (moyennes) accompagnée d'avertissements
    explicites -- c'est à l'utilisateur de trancher ensuite dans le
    formulaire, pré-rempli mais toujours modifiable (voir Phase A de la
    feuille de route).
    """
    avertissements = []

    xs_lignes = _clusteriser_1d([p["x"] for p in poteaux])
    ys_lignes = _clusteriser_1d([p["y"] for p in poteaux])

    nb_travees_x, portee_x = _travees_et_portee(xs_lignes, "X", avertissements)
    nb_travees_y, portee_y = _travees_et_portee(ys_lignes, "Y", avertissements)

    nb_poteaux_attendu = (nb_travees_x + 1) * (nb_travees_y + 1)
    if nb_travees_x and nb_travees_y and nb_poteaux_attendu != len(poteaux):
        avertissements.append(
            f"{len(poteaux)} poteau(x) détecté(s) mais une grille "
            f"{nb_travees_x}x{nb_travees_y} régulière en compterait "
            f"{nb_poteaux_attendu} -- la trame réelle n'est probablement "
            f"pas parfaitement régulière (poteaux manquants, décrochés, ou "
            f"non structurels inclus par erreur). Vérifiez le formulaire "
            f"avant de valider."
        )

    nb_niveaux, hauteur_etage = _niveaux_et_hauteur(poteaux, niveaux, avertissements)

    return {
        "nb_travees_x": nb_travees_x,
        "nb_travees_y": nb_travees_y,
        "portee_x": round(portee_x, 2) if portee_x else None,
        "portee_y": round(portee_y, 2) if portee_y else None,
        "nb_niveaux": nb_niveaux,
        "hauteur_etage": round(hauteur_etage, 2) if hauteur_etage else None,
        "nb_poteaux_detectes": len(poteaux),
        "avertissements": avertissements,
    }


def _travees_et_portee(lignes: list, axe: str, avertissements: list):
    """Nombre de travées + portée moyenne à partir des lignes de grille
    détectées sur un axe, avec avertissement si la grille est irrégulière."""
    if len(lignes) < 2:
        avertissements.append(
            f"Un seul alignement de poteaux détecté sur l'axe {axe} -- "
            f"impossible de déduire une portée ; à saisir manuellement."
        )
        return max(len(lignes) - 1, 0), None

    portees = [b - a for a, b in zip(lignes, lignes[1:])]
    portee_moyenne = mean(portees)
    if len(portees) > 1 and portee_moyenne > 0:
        variation = pstdev(portees) / portee_moyenne
        if variation > SEUIL_IRREGULARITE:
            avertissements.append(
                f"Portées irrégulières détectées sur l'axe {axe} "
                f"({', '.join(f'{p:.2f}m' for p in portees)}) -- la valeur "
                f"moyenne ({portee_moyenne:.2f}m) est une approximation, à "
                f"vérifier avant de valider le formulaire."
            )
    return len(lignes) - 1, portee_moyenne


def _niveaux_et_hauteur(poteaux: list, niveaux: list, avertissements: list):
    """Nombre de niveaux + hauteur d'étage moyenne, en priorisant les
    IfcBuildingStorey réels ; à défaut, retombe sur les élévations
    distinctes portées par les poteaux eux-mêmes."""
    if niveaux and len(niveaux) >= 1:
        elevations = sorted({n["elevation_m"] for n in niveaux})
    else:
        elevations = sorted({round(p["niveau_elevation_m"], 2) for p in poteaux})
        if not niveaux:
            avertissements.append(
                "Aucun IfcBuildingStorey trouvé -- les niveaux ont été "
                "déduits des élévations des poteaux eux-mêmes (moins fiable)."
            )

    nb_niveaux = len(elevations) or 1

    if len(elevations) >= 2:
        hauteurs = [b - a for a, b in zip(elevations, elevations[1:])]
        hauteur_etage = mean(hauteurs)
        if len(hauteurs) > 1 and hauteur_etage > 0 and pstdev(hauteurs) / hauteur_etage > SEUIL_IRREGULARITE:
            avertissements.append(
                f"Hauteurs d'étage irrégulières détectées "
                f"({', '.join(f'{h:.2f}m' for h in hauteurs)}) -- la valeur "
                f"moyenne ({hauteur_etage:.2f}m) est une approximation."
            )
    else:
        hauteur_etage = None
        avertissements.append(
            "Un seul niveau détecté -- impossible de déduire une hauteur "
            "d'étage ; à saisir manuellement."
        )

    return nb_niveaux, hauteur_etage


def analyser_fichier_ifc(chemin_fichier: str) -> dict:
    """
    Point d'entrée unique de la Phase A : ouvre le fichier, extrait
    poteaux + niveaux, détecte les paramètres de trame. C'est cette
    fonction que l'endpoint de Samuel (importer_plan/) appellera.

    Lève FichierIFCInvalide ou AucunPoteauDetecte en cas de problème --
    l'appelant (vue Django) est responsable de les transformer en
    réponse HTTP explicite pour l'utilisateur.
    """
    model = ouvrir_ifc(chemin_fichier)
    poteaux = extraire_poteaux(model)
    niveaux = extraire_niveaux(model)
    parametres = detecter_parametres_trame(poteaux, niveaux)
    parametres["poteaux"] = poteaux  # conservé : utile pour la Phase B (positions réelles)
    return parametres