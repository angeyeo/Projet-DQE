"""
Résolution des paramètres d'un projet nécessaires au moteur de trame.

Remplace les valeurs inventées que les vues injectaient en silence
(2 travées, 5 m de portée, 3 m d'étage, 1,5 kN/m², usage "habitations"
-- avec un "s" que le moteur ne reconnaissait pas --, taux de travail du
sol 0.2 en MPa au lieu de kN/m²...). Une donnée manquante produit
désormais une erreur explicite, jamais une valeur par défaut cachée.
"""

from moteur_calcul.constantes import CHARGE_EXPLOITATION_TOITURE_KN_M2, CHARGES_EXPLOITATION, G_TOITURE_CHARPENTE_KN_M2
from moteur_calcul.hypotheses import HypothesesCalcul, resoudre_charge_permanente


class ParametresIncomplets(Exception):
    def __init__(self, manquants):
        self.manquants = manquants
        super().__init__(
            "Paramètres du projet incomplets : " + ", ".join(m["libelle"] for m in manquants) + "."
        )


# Messages affichés partout où une structure saisie intervient (résultats, DQE).
AVERTISSEMENT_STRUCTURE_SAISIE = "Structure placée par l'utilisateur, non lue dans le plan."
AVERTISSEMENT_STRUCTURE_MIXTE = ("Structure modifiée par l'utilisateur : {n} poteau(x) ajouté(s) ou déplacé(s) à la "
                                 "main (origine « saisi ») ; les autres viennent du plan ou de la trame.")
# Débuts de ces messages (pour les remplacer après un changement de source).
MESSAGES_SOURCE_STRUCTURE = ("Structure placée par l'utilisateur", "Structure modifiée par l'utilisateur")


def messages_source_structure(projet):
    """Rappel permanent de l'origine de la structure (issues #93 et #94)."""
    if projet.source_structure == "saisie":
        return [AVERTISSEMENT_STRUCTURE_SAISIE]
    if projet.source_structure == "mixte":
        n = sum(1 for p in projet.poteaux_saisis or [] if p.get("origine") == "saisi")
        return [AVERTISSEMENT_STRUCTURE_MIXTE.format(n=n)]
    return []


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
        type_toiture=projet.type_toiture,
        g_toiture_kn_m2=G_TOITURE_CHARPENTE_KN_M2 if projet.type_toiture == "charpente" else None,
        inclure_poids_propre_ossature=projet.inclure_poids_propre_ossature,
        methode_semelles=projet.methode_semelles,
        contrainte_sol_kn_m2=projet.contrainte_sol_kn_m2,
        poids_murs_kn_m2=projet.poids_murs_kn_m2,
        origine_poids_murs="saisie" if projet.poids_murs_kn_m2 is not None else None,
        murs_rdc_sur_semelles=projet.murs_rdc_sur_semelles,
        murs_rdc=frozenset(projet.murs_rdc or ()),
        murs_etages=frozenset(projet.murs_etages or ()),
        pourcentage_baies_murs=projet.pourcentage_baies_murs or 0.0,
    )
    hypotheses = hyp.messages()
    # Rappel permanent (issues #93, #94) : positions des poteaux placées ou
    # modifiées par l'utilisateur, pas (toutes) lues dans le fichier.
    hypotheses = messages_source_structure(projet) + hypotheses

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
