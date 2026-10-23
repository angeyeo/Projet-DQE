"""
Création des éléments d'une trame régulière -- partagée par l'endpoint
generer_trame et par le calcul de variantes (même moteur, même chemin).
"""

from moteur_calcul.formules.trame import (
    cle_segment, detecter_poutres_adjacentes, generer_poteau_depuis_position_reelle, generer_poteau_sur_grille,
    generer_poutre_sur_grille,
)

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
                origine_geometrie=ElementStructurel.OrigineGeometrie.TRAME,
            )
            poteaux[(i, j)] = poteau
            semelle = ElementStructurel.objects.create(
                projet=projet, identifiant=f"S_{i}_{j}",
                type_element=ElementStructurel.TypeElement.SEMELLE,
                position=ElementStructurel.Position.INFRASTRUCTURE,
                position_x=d["x"], position_y=d["y"], poteau_associe=poteau,
                charge_calculee=d["charge_elu_semelle_kn"], charge_service=d["charge_els_semelle_kn"],
                taux_travail_sol=prm["contrainte_sol_kn_m2"],
                resultat_calcul=d["resultat_semelle"],
                origine_geometrie=ElementStructurel.OrigineGeometrie.TRAME,
            )
            elements_crees += [poteau, semelle]

    def creer_poutre(ident, portee, largeur_influence, origine, destination, x, y, rive):
        cle = cle_segment((origine.position_x, origine.position_y), (destination.position_x, destination.position_y))
        d = generer_poutre_sur_grille(portee, largeur_influence, q, hyp=prm["hyp"], nb_niveaux=prm["nb_niveaux"],
                                      hauteur_etage=prm["hauteur_etage"], cle=cle, rive=rive)
        hypotheses.extend(m for m in d["hypotheses"] if m.startswith("ALERTE : poutre"))
        return ElementStructurel.objects.create(
            projet=projet, identifiant=ident,
            type_element=ElementStructurel.TypeElement.POUTRE,
            nombre_identiques=prm["nb_niveaux"],
            position=ElementStructurel.Position.SUPERSTRUCTURE,
            position_x=x, position_y=y, portee=portee,
            charge_lineaire=d["charge_lineaire_kn_m"], resultat_calcul=d["resultat_poutre"],
            poteau_origine=origine, poteau_destination=destination,
            origine_geometrie=ElementStructurel.OrigineGeometrie.TRAME,
        )

    for j in range(nb_y + 1):
        for i in range(nb_x):
            largeur = py if 0 < j < nb_y else py / 2
            elements_crees.append(creer_poutre(
                f"PX_{i}_{j}", px, largeur, poteaux[(i, j)], poteaux[(i + 1, j)],
                (i + 0.5) * px, j * py, rive=j in (0, nb_y),
            ))
    for i in range(nb_x + 1):
        for j in range(nb_y):
            largeur = px if 0 < i < nb_x else px / 2
            elements_crees.append(creer_poutre(
                f"PY_{i}_{j}", py, largeur, poteaux[(i, j)], poteaux[(i, j + 1)],
                i * px, (j + 0.5) * py, rive=i in (0, nb_x),
            ))
    hypotheses.extend(murs_orphelins(prm["hyp"], elements_crees))
    return elements_crees, hypotheses


def _virgule_m(v):
    return f"{round(v, 2):g} m".replace(".", ",")


def creer_elements_depuis_positions(projet, empreinte, prm, origine):
    """Remplace poteaux / semelles / poutres du projet par ceux construits
    sur des positions RÉELLES de poteaux (x, y en mètres) : poteaux lus
    dans un plan importé (origine « plan ») ou placés par l'utilisateur
    sur un plan d'architecte (origine « saisi »). Même moteur dans les
    deux cas : seule la source des positions change.

    Un poteau sans trame 2D exploitable (aucun voisin sur un axe) n'est
    pas créé : il est signalé dans les avertissements, jamais inventé.
    À appeler DANS une transaction (tout ou rien).

    empreinte : liste de dicts {"x", "y", "guid", ...} ; une clé "origine"
    facultative fixe l'origine de CE poteau (sinon `origine`).
    Renvoie (elements_crees, hypotheses, avertissements, troncons_non_calcules).
    """
    q = prm["charge_exploitation"]
    avertissements = []
    hypotheses = list(prm["hypotheses"])
    elements_crees = []
    projet.elements.filter(type_element__in=TYPES_TRAME).delete()
    poteau_par_guid = {}
    compteur = 0
    for p in empreinte:
        try:
            d = generer_poteau_depuis_position_reelle(
                p, empreinte, q, prm["hauteur_etage"],
                nb_niveaux=prm["nb_niveaux"], usage_batiment=prm["usage_batiment"],
                taux_travail_sol=prm["contrainte_sol_kn_m2"], hyp=prm["hyp"],
            )
        except ValueError as exc:
            # Poteau sans trame 2D exploitable : signalé, jamais inventé.
            avertissements.append(str(exc))
            continue
        hypotheses.extend(d.get("hypotheses", []))
        compteur += 1
        poteau = ElementStructurel.objects.create(
            projet=projet, identifiant=f"P{compteur}",
            type_element=ElementStructurel.TypeElement.POTEAU,
            nombre_identiques=prm["nb_niveaux"],
            position=ElementStructurel.Position.SUPERSTRUCTURE,
            position_x=d["x"], position_y=d["y"],
            hauteur_poteau=prm["hauteur_etage"], charge_calculee=d["charge_elu_kn"],
            charge_service=d["charge_els_kn"],
            resultat_calcul=d["resultat_poteau"], origine_geometrie=p.get("origine", origine),
        )
        poteau_par_guid[p.get("guid")] = poteau
        semelle = ElementStructurel.objects.create(
            projet=projet, identifiant=f"S{compteur}",
            type_element=ElementStructurel.TypeElement.SEMELLE,
            position=ElementStructurel.Position.INFRASTRUCTURE,
            position_x=d["x"], position_y=d["y"], poteau_associe=poteau,
            charge_calculee=d["charge_elu_semelle_kn"], charge_service=d["charge_els_semelle_kn"],
            taux_travail_sol=prm["contrainte_sol_kn_m2"],
            resultat_calcul=d["resultat_semelle"], origine_geometrie=p.get("origine", origine),
        )
        elements_crees += [poteau, semelle]

    compteur_poutre = 0
    segments_ignores, troncons_non_calcules = [], []
    poutres_detectees = detecter_poutres_adjacentes(
        empreinte, q, hyp=prm["hyp"], nb_niveaux=prm["nb_niveaux"],
        hauteur_etage=prm["hauteur_etage"], segments_ignores=segments_ignores)
    avertissements.extend(segments_ignores)
    for pd in poutres_detectees:
        hypotheses.extend(m for m in pd["hypotheses"] if m.startswith("ALERTE : poutre"))
        debut = poteau_par_guid.get(pd["poteau_origine_guid"])
        fin = poteau_par_guid.get(pd["poteau_destination_guid"])
        if debut is None or fin is None:
            troncons_non_calcules.append(pd["resultat_poutre"].get("cle_segment"))
            avertissements.append(
                f"Poutre de {_virgule_m(pd['portee_m'])} (axe {pd['axe']}) non créée : un de ses deux "
                "poteaux n'a pas pu être calculé (voir l'avertissement du poteau).")
            continue
        compteur_poutre += 1
        elements_crees.append(ElementStructurel.objects.create(
            projet=projet,
            identifiant=f"{'PX' if pd['axe'] == 'x' else 'PY'}{compteur_poutre}",
            type_element=ElementStructurel.TypeElement.POUTRE,
            nombre_identiques=prm["nb_niveaux"],
            position=ElementStructurel.Position.SUPERSTRUCTURE,
            position_x=(debut.position_x + fin.position_x) / 2,
            position_y=(debut.position_y + fin.position_y) / 2,
            portee=pd["portee_m"], charge_lineaire=pd["charge_lineaire_kn_m"],
            resultat_calcul=pd["resultat_poutre"],
            poteau_origine=debut, poteau_destination=fin,
            # Une poutre suit ses deux poteaux : même origine s'ils
            # concordent, sinon « saisi » (elle dépend d'un choix manuel).
            origine_geometrie=(debut.origine_geometrie if debut.origine_geometrie == fin.origine_geometrie
                               else ElementStructurel.OrigineGeometrie.SAISI),
        ))
    return elements_crees, hypotheses, avertissements, troncons_non_calcules


def murs_orphelins(hyp, elements, troncons_non_calcules=()):
    """Murs du plan qui ne portent sur aucune poutre créée : signalés,
    jamais comptés. Deux causes, dites séparément : la poutre existe dans
    le plan mais un de ses poteaux n'a pas pu être calculé, ou la
    géométrie a changé depuis le placement des murs."""
    cles = {(e.resultat_calcul or {}).get("cle_segment") for e in elements
            if e.type_element == ElementStructurel.TypeElement.POUTRE}
    sans_poutre = (set(hyp.murs_rdc) | set(hyp.tous_murs_etages)) - cles
    non_calcules = sans_poutre & set(troncons_non_calcules)
    orphelins = sans_poutre - non_calcules
    messages = []
    if non_calcules:
        messages.append(f"ALERTE : {len(non_calcules)} mur(s) posé(s) sur des poutres non calculées (un de leurs "
                        f"poteaux n'a pas pu l'être, voir les avertissements) : leur charge n'est pas comptée.")
    if orphelins:
        messages.append(f"ALERTE : {len(orphelins)} tronçon(s) de mur du plan des murs ne correspondent plus à aucune "
                        f"poutre (trame modifiée) : ils ne sont pas comptés. Replacez les murs sur le plan.")
    return messages
