"""
Création des éléments d'une trame régulière -- partagée par l'endpoint
generer_trame et par le calcul de variantes (même moteur, même chemin).
"""

from moteur_calcul.formules.trame import generer_poteau_sur_grille, generer_poutre_sur_grille

from ..models import ElementStructurel

TYPES_TRAME = (
    ElementStructurel.TypeElement.POTEAU,
    ElementStructurel.TypeElement.SEMELLE,
    ElementStructurel.TypeElement.POUTRE,
)


def creer_elements_trame(projet, prm):
    """Remplace poteaux / semelles / poutres du projet par ceux de la trame.
    À appeler DANS une transaction (tout ou rien). Renvoie (elements, hypotheses)."""
    nb_x, nb_y = prm["nb_travees_x"], prm["nb_travees_y"]
    px, py = prm["portee_x"], prm["portee_y"]
    q = prm["charge_exploitation"]
    hypotheses = list(prm["hypotheses"])
    # Seuls les types recréés par la trame sont remplacés : les
    # dalles, longrines, chaînages saisis à part sont conservés.
    projet.elements.filter(type_element__in=TYPES_TRAME).delete()
    elements_crees = []
    poteaux = {}
    for i in range(nb_x + 1):
        for j in range(nb_y + 1):
            d = generer_poteau_sur_grille(
                i, j, px, py, nb_x, nb_y, q, prm["hauteur_etage"],
                nb_niveaux=prm["nb_niveaux"], usage_batiment=prm["usage_batiment"],
                taux_travail_sol=prm["contrainte_sol_kn_m2"], hyp=prm["hyp"],
            )
            hypotheses.extend(d.get("hypotheses", []))
            poteau = ElementStructurel.objects.create(
                projet=projet, identifiant=f"P_{i}_{j}",
                type_element=ElementStructurel.TypeElement.POTEAU,
                nombre_identiques=prm["nb_niveaux"],
                position=ElementStructurel.Position.SUPERSTRUCTURE,
                position_x=d["x"], position_y=d["y"],
                hauteur_poteau=prm["hauteur_etage"], charge_calculee=d["charge_elu_kn"],
            charge_service=d["charge_els_kn"],
                resultat_calcul=d["resultat_poteau"],
            )
            poteaux[(i, j)] = poteau
            semelle = ElementStructurel.objects.create(
                projet=projet, identifiant=f"S_{i}_{j}",
                type_element=ElementStructurel.TypeElement.SEMELLE,
                position=ElementStructurel.Position.INFRASTRUCTURE,
                position_x=d["x"], position_y=d["y"], poteau_associe=poteau,
                charge_calculee=d["charge_elu_kn"], charge_service=d["charge_els_kn"],
                taux_travail_sol=prm["contrainte_sol_kn_m2"],
                resultat_calcul=d["resultat_semelle"],
            )
            elements_crees += [poteau, semelle]

    def creer_poutre(ident, portee, largeur_influence, origine, destination, x, y):
        d = generer_poutre_sur_grille(portee, largeur_influence, q, hyp=prm["hyp"])
        return ElementStructurel.objects.create(
            projet=projet, identifiant=ident,
            type_element=ElementStructurel.TypeElement.POUTRE,
            nombre_identiques=prm["nb_niveaux"],
            position=ElementStructurel.Position.SUPERSTRUCTURE,
            position_x=x, position_y=y, portee=portee,
            charge_lineaire=d["charge_lineaire_kn_m"], resultat_calcul=d["resultat_poutre"],
            poteau_origine=origine, poteau_destination=destination,
        )

    for j in range(nb_y + 1):
        for i in range(nb_x):
            largeur = py if 0 < j < nb_y else py / 2
            elements_crees.append(creer_poutre(
                f"PX_{i}_{j}", px, largeur, poteaux[(i, j)], poteaux[(i + 1, j)],
                (i + 0.5) * px, j * py,
            ))
    for i in range(nb_x + 1):
        for j in range(nb_y):
            largeur = px if 0 < i < nb_x else px / 2
            elements_crees.append(creer_poutre(
                f"PY_{i}_{j}", py, largeur, poteaux[(i, j)], poteaux[(i, j + 1)],
                i * px, (j + 0.5) * py,
            ))
    return elements_crees, hypotheses
