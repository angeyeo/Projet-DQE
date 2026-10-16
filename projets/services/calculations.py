from moteur_calcul.formules.descente_charges import calculer_descente_charges_complete
from moteur_calcul.formules.dimensionnement_poteaux import dimensionner_poteau
from moteur_calcul.formules.dimensionnement_poutres import dimensionner_poutre
from moteur_calcul.formules.dimensionnement_semelles import dimensionner_semelle
from moteur_calcul.formules.postes_ratio import dimensionner_chainage
from moteur_calcul.validators import EntreeInvalide

from ..models import ElementStructurel


class CalculNonDisponible(Exception):
    """Levée quand le moteur de calcul n'est pas encore prêt (formules en attente)."""


def calculer_charge_permanente_totale(element: ElementStructurel) -> float | None:
    """Module 2 : charge permanente SURFACIQUE G (kN/m²) = somme des
    couches liées à l'élément, ou None si aucune couche n'est saisie.

    ATTENTION aux unités : c'est une charge par m² de plancher. Elle ne
    peut PAS être passée telle quelle comme charge linéaire (kN/m) d'une
    poutre -- il faudrait la multiplier par la largeur d'influence et la
    pondérer (1,35 G + 1,5 Q). Avant, calculer_element() le faisait pour
    les poutres : erreur de dimension (kN/m² utilisé comme kN/m).
    """
    couches = element.couches_charges.all()
    if not couches.exists():
        return None
    return sum(couche.poids_surfacique_kn_m2 for couche in couches)


def _charge_lineaire_requise(element: ElementStructurel) -> float:
    if element.charge_lineaire is None or element.charge_lineaire <= 0:
        raise EntreeInvalide(
            f"{element.identifiant} : charge linéaire ELU (kN/m) non renseignée -- "
            f"impossible de dimensionner la section."
        )
    return element.charge_lineaire


def degression_renseignee(element: ElementStructurel) -> bool:
    """
    Module 1 : dit si un POTEAU a assez d'information de trame pour
    déclencher la descente de charges complète avec dégression
    (calculer_descente_charges_complete()) plutôt que le comportement
    historique (charge_calculee brute, sans dégression ni cumul réel
    sur les niveaux).

    Condition : les 4 portées ET nb_niveaux_charges doivent être
    renseignées. Une portée à 0.0 est une valeur valide (poteau de
    rive, par exemple) -- seul `None` signale "non renseigné". Le champ
    avec_degression ne rentre PAS en jeu ici : il contrôle seulement si
    la dégression est ACTIVÉE une fois la descente déclenchée (voir
    calculer_element()), pas si elle doit l'être.

    epaisseur_dalle n'est volontairement pas vérifiée ici : elle peut
    être absente si des CoucheCharge (Module 2) existent déjà sur
    l'élément -- calculer_element()/_couches_permanentes_pour_descente()
    gèrent cette bascule, pas cette fonction, qui ne s'occupe que de la
    trame (portées + niveaux).
    """
    portees = (element.portee_gauche, element.portee_droite, element.portee_avant, element.portee_arriere)
    if any(p is None for p in portees):
        return False
    return element.nb_niveaux_charges is not None


def _couches_permanentes_pour_descente(element: ElementStructurel) -> list | None:
    """
    Adapte les CoucheCharge (Module 2) liées à cet élément vers le
    format attendu par calculer_descente_charges_complete()
    (couches_permanentes) -- réutilise la propriété
    poids_surfacique_kn_m2 déjà calculée sur le modèle plutôt que de
    refaire epaisseur x poids volumique ici. None si aucune couche
    n'est liée : l'appelant retombe alors sur epaisseur_dalle (dalle
    béton seule).
    """
    couches = element.couches_charges.all()
    if not couches.exists():
        return None
    return [
        {"designation": couche.designation, "poids_surfacique_kn_m2": couche.poids_surfacique_kn_m2}
        for couche in couches
    ]


def calculer_element(element: ElementStructurel) -> dict:
    try:
        if element.type_element == ElementStructurel.TypeElement.POTEAU:
            if degression_renseignee(element):
                # Module 1 : trame connue -- descente de charges
                # complète (surface d'influence -> G -> Q -> ELU cumulé
                # sur nb_niveaux_charges, avec dégression NF P06-001 si
                # avec_degression=True) au lieu de la charge_calculee
                # brute historique.
                descente = calculer_descente_charges_complete(
                    portee_gauche=element.portee_gauche,
                    portee_droite=element.portee_droite,
                    portee_avant=element.portee_avant,
                    portee_arriere=element.portee_arriere,
                    epaisseur_dalle=element.epaisseur_dalle,
                    usage_batiment=element.projet.usage_batiment,
                    nb_niveaux=element.nb_niveaux_charges,
                    avec_degression=element.avec_degression,
                    usage_toiture=element.usage_toiture or None,
                    couches_permanentes=_couches_permanentes_pour_descente(element),
                )
                resultat = dimensionner_poteau(
                    charge_calculee=descente["charge_elu_cumulee_kn"],
                    hauteur_poteau=element.hauteur_poteau,
                )
                resultat["descente_charges"] = descente
                return resultat

            return dimensionner_poteau(
                charge_calculee=element.charge_calculee,
                hauteur_poteau=element.hauteur_poteau,
            )
        elif element.type_element in (
            ElementStructurel.TypeElement.POUTRE,
            ElementStructurel.TypeElement.LONGRINE,
        ):
            # Longrine = même physique qu'une poutre (flexion simple BAEL).
            # La charge linéaire ELU (kN/m) est celle de l'élément -- voir
            # calculer_charge_permanente_totale() pour la raison.
            pu = _charge_lineaire_requise(element)
            # γ = pu / pser connu si la trame l'a enregistré ; sinon le moteur
            # l'estime (1,45) et le signale par gamma_estime=True.
            pser = (element.resultat_calcul or {}).get("charge_els_kn_m")
            return dimensionner_poutre(
                portee=element.portee,
                charge_lineaire=pu,
                gamma_elu_els=(pu / pser) if pser else None,
            )
        elif element.type_element == ElementStructurel.TypeElement.SEMELLE:
            poteau_associe = getattr(element, "poteau_associe", None)
            cote_poteau = None
            if poteau_associe and poteau_associe.resultat_calcul:
                cote_poteau = poteau_associe.resultat_calcul.get("cote_cm")

            projet = element.projet
            methode = projet.methode_semelles
            if methode == "ELS" and not element.charge_service:
                raise EntreeInvalide(
                    f"{element.identifiant} : méthode ELS choisie mais effort de service (G + Q) inconnu -- "
                    f"régénérez la trame pour le calculer."
                )
            resultat = dimensionner_semelle(
                charge_poteau=element.charge_calculee,
                taux_travail_sol=element.taux_travail_sol,
                cote_poteau_cm=cote_poteau,
                charge_service=element.charge_service,
                methode=methode,
                inclure_poids_propre=projet.inclure_poids_propre_ossature,
            )
            resultat["trace"] = [{
                "etape": "Recalcul isolé", "formule": f"A = √(N / σsol) — méthode {methode}",
                "calcul": f"Nu = {element.charge_calculee} kN, Ns = {element.charge_service} kN (enregistrés à la génération)",
                "resultat": resultat["cote_cm"], "unite": "cm",
            }]
            return resultat
        elif element.type_element == getattr(ElementStructurel.TypeElement, "DALLE", "dalle"):
            # Module 7 : Import dynamique sécurisé si la formule Dev 1 n'est pas encore poussée
            try:
                from moteur_calcul.formules.dimensionnement_dalles import predimensionner_dalle
            except (ImportError, ModuleNotFoundError) as err:
                raise CalculNonDisponible("Module de calcul des dalles pas encore disponible.") from err

            # MODIFIÉ (Ange) : predimensionner_dalle() n'accepte que
            # (portee, portant_deux_sens) -- "charge_calculee" n'existe
            # pas dans sa signature, l'appel précédent levait un TypeError
            # à chaque tentative de calcul d'une dalle.
            # Comportement en nappe (BAEL 91, A.8.2) : alpha = Lx / Ly.
            # alpha >= 0,4 -> la dalle porte dans les deux sens. Ly n'est
            # connue que si longueur_m est renseignée ; sinon on reste sur
            # l'hypothèse "un sens", la plus défavorable (dalle plus
            # épaisse), et on le signale.
            ly = element.longueur_m
            deux_sens = bool(ly and element.portee and element.portee / ly >= 0.4)
            resultat = predimensionner_dalle(portee=element.portee, portant_deux_sens=deux_sens)
            resultat["alpha"] = round(element.portee / ly, 3) if ly else None
            if not ly:
                resultat["hypothese_sens_portee"] = (
                    "Grande portée Ly non renseignée : dalle supposée porter dans un seul sens "
                    "(épaisseur la plus défavorable)."
                )
            return resultat
        elif element.type_element == getattr(ElementStructurel.TypeElement, "SEMELLE_FILANTE", "semelle_filante"):
            # MODIFIÉ (Ange) : le module dimensionner_semelle_filante() vit dans
            # dimensionnement_semelles.py (pas un fichier séparé
            # dimensionnement_semelles_filantes.py qui n'existe pas) -- l'import
            # précédent échouait toujours, silencieusement transformé en
            # CalculNonDisponible, donc jamais détecté par les tests unitaires
            # du moteur (qui appellent la fonction directement, pas via l'API).
            try:
                from moteur_calcul.formules.dimensionnement_semelles import dimensionner_semelle_filante
            except (ImportError, ModuleNotFoundError) as err:
                raise CalculNonDisponible("Module de calcul des semelles filantes pas encore disponible.") from err

            # MODIFIÉ (Ange) : le paramètre réel s'appelle charge_lineaire_kn_m,
            # pas charge_lineaire -- l'appel précédent levait un TypeError.
            return dimensionner_semelle_filante(
                charge_lineaire_kn_m=_charge_lineaire_requise(element),
                taux_travail_sol=element.taux_travail_sol,
            )
        elif element.type_element == getattr(ElementStructurel.TypeElement, "CHAINAGE", "chainage"):
            # Phase C : chaînage promu en élément identifié (repère CH1) --
            # pas de calcul de résistance, section forfaitaire + ratio
            # acier (voir dimensionner_chainage(), même constantes
            # provisoires que le poste ratio global existant).
            return dimensionner_chainage(longueur_m=element.longueur_m)
        else:
            raise ValueError(f"Type d'élément inconnu : {element.type_element}")
    except (NotImplementedError, CalculNonDisponible) as exc:
        raise CalculNonDisponible(str(exc)) from exc
    except EntreeInvalide:
        raise


def recalculer_projet(projet):
    elements_a_calculer = projet.elements.exclude(
        statut=ElementStructurel.Statut.VALIDE
    )
    resultats = {}
    for element in elements_a_calculer:
        try:
            resultat = calculer_element(element)
            element.resultat_calcul = resultat
            element.save(update_fields=["resultat_calcul", "date_modification"])
            resultats[element.id] = {"ok": True, "resultat": resultat}
        except CalculNonDisponible as exc:
            resultats[element.id] = {"ok": False, "erreur": str(exc)}
        except EntreeInvalide as exc:
            resultats[element.id] = {"ok": False, "erreur": str(exc)}
    return resultats
