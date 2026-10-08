"""
Résolution des paramètres d'un projet nécessaires au moteur de trame.

Remplace les valeurs inventées que les vues injectaient en silence
(2 travées, 5 m de portée, 3 m d'étage, 1,5 kN/m², usage "habitations"
-- avec un "s" que le moteur ne reconnaissait pas --, taux de travail du
sol 0.2 en MPa au lieu de kN/m²...). Une donnée manquante produit
désormais une erreur explicite, jamais une valeur par défaut cachée.
"""

from moteur_calcul.constantes import CHARGE_EXPLOITATION_TOITURE_KN_M2, CHARGES_EXPLOITATION
from moteur_calcul.hypotheses import HypothesesCalcul, resoudre_charge_permanente


class ParametresIncomplets(Exception):
    def __init__(self, manquants):
        self.manquants = manquants
        super().__init__(
            "Paramètres du projet incomplets : " + ", ".join(m["libelle"] for m in manquants) + "."
        )


def resoudre_charge_exploitation(projet):
    """(valeur kN/m², origine) -- origine = "saisie" ou "usage:<clé>".

    None si ni saisie ni déduisible (usage inconnu ou sans valeur
    normative, ex. "industriel").
    """
    if projet.charge_exploitation is not None:
        return projet.charge_exploitation, "saisie"
    valeur = CHARGES_EXPLOITATION.get(projet.usage_batiment or "")
    if valeur is None:
        return None, None
    return valeur, f"usage:{projet.usage_batiment}"


def _manquant(champ, libelle):
    return {"champ": champ, "libelle": libelle}


def parametres_structure(projet, avec_grille: bool):
    """Paramètres communs à generer_trame (avec_grille=True) et
    importer_plan (avec_grille=False, la géométrie vient de l'IFC).

    Lève ParametresIncomplets avec la liste COMPLÈTE de ce qui manque.
    """
    manquants = []
    if not projet.usage_batiment:
        manquants.append(_manquant("usage_batiment", "usage du bâtiment"))
    if not projet.nb_niveaux:
        manquants.append(_manquant("nb_niveaux", "nombre de niveaux"))
    if not projet.hauteur_etage:
        manquants.append(_manquant("hauteur_etage", "hauteur d'étage (m)"))
    charge_q, origine_q = resoudre_charge_exploitation(projet)
    if charge_q is None and projet.usage_batiment:
        manquants.append(_manquant(
            "charge_exploitation",
            f"charge d'exploitation (kN/m²) -- aucune valeur normative pour l'usage « {projet.usage_batiment} »",
        ))
    if avec_grille:
        if not projet.nb_travees_x:
            manquants.append(_manquant("nb_travees_x", "nombre de travées en X"))
        if not projet.nb_travees_y:
            manquants.append(_manquant("nb_travees_y", "nombre de travées en Y"))
        if not projet.portee_x:
            manquants.append(_manquant("portee_x", "portée en X (m)"))
        if not projet.portee_y:
            manquants.append(_manquant("portee_y", "portée en Y (m)"))
    if manquants:
        raise ParametresIncomplets(manquants)

    try:
        g, origine_g, detail_g = resoudre_charge_permanente(
            projet.charge_permanente_kn_m2, projet.couches_permanentes or None)
    except ValueError as exc:
        raise ParametresIncomplets([_manquant("couches_permanentes", f"composition du plancher invalide ({exc})")])
    hyp = HypothesesCalcul(
        g_plancher_kn_m2=g, origine_g=origine_g, detail_g=detail_g,
        q_kn_m2=charge_q, origine_q=origine_q,
        q_toiture_kn_m2=CHARGE_EXPLOITATION_TOITURE_KN_M2, origine_q_toiture="valide_technicien",
        inclure_poids_propre_ossature=projet.inclure_poids_propre_ossature,
        methode_semelles=projet.methode_semelles,
        contrainte_sol_kn_m2=projet.contrainte_sol_kn_m2,
    )
    hypotheses = hyp.messages()

    params = {
        "usage_batiment": projet.usage_batiment,
        "nb_niveaux": projet.nb_niveaux,
        "hauteur_etage": projet.hauteur_etage,
        "charge_exploitation": charge_q,
        "contrainte_sol_kn_m2": projet.contrainte_sol_kn_m2,
        "hypotheses": hypotheses,
        "hyp": hyp,
    }
    if avec_grille:
        params.update({
            "nb_travees_x": projet.nb_travees_x,
            "nb_travees_y": projet.nb_travees_y,
            "portee_x": projet.portee_x,
            "portee_y": projet.portee_y,
        })
    return params


def messages_hypotheses(projet):
    """Hypothèses de calcul lisibles du projet, ou la liste de ce qui manque."""
    try:
        return {"hypotheses": parametres_structure(projet, avec_grille=False)["hypotheses"], "manquants": []}
    except ParametresIncomplets as exc:
        return {"hypotheses": [], "manquants": [m["libelle"] for m in exc.manquants]}


def statut_projet(nb_elements: int, nb_valides: int, dqe_genere: bool) -> str:
    """Statut DÉRIVÉ des données réelles (aucun champ saisi à la main) :
    brouillon -> en_etude -> valide -> dqe_genere."""
    if nb_elements == 0:
        return "brouillon"
    if nb_valides < nb_elements:
        return "en_etude"
    return "dqe_genere" if dqe_genere else "valide"
