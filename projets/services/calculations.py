from moteur_calcul.formules.dimensionnement_poteaux import dimensionner_poteau
from moteur_calcul.formules.dimensionnement_poutres import dimensionner_poutre
from moteur_calcul.formules.dimensionnement_semelles import dimensionner_semelle
from moteur_calcul.validators import EntreeInvalide

from ..models import ElementStructurel


class CalculNonDisponible(Exception):
    """Levée quand le moteur de calcul n'est pas encore prêt (formules en attente)."""


def calculer_charge_permanente_totale(element: ElementStructurel) -> float:
    """Module 2 : Calcule la charge permanente G en sommant les couches complexes."""
    couches = element.couches_charges.all()
    if couches.exists():
        return sum(couche.poids_surfacique_kn_m2 for couche in couches)
    return getattr(element, "charge_lineaire", 0.0) or 0.0


def calculer_element(element: ElementStructurel) -> dict:
    try:
        if element.type_element == ElementStructurel.TypeElement.POTEAU:
            return dimensionner_poteau(
                charge_calculee=element.charge_calculee,
                hauteur_poteau=element.hauteur_poteau,
            )
        elif element.type_element == ElementStructurel.TypeElement.POUTRE:
            charge_g = calculer_charge_permanente_totale(element) or element.charge_lineaire
            return dimensionner_poutre(
                portee=element.portee,
                charge_lineaire=charge_g,
            )
        elif element.type_element == ElementStructurel.TypeElement.SEMELLE:
            poteau_associe = getattr(element, "poteau_associe", None)
            cote_poteau = None
            if poteau_associe and poteau_associe.resultat_calcul:
                cote_poteau = poteau_associe.resultat_calcul.get("cote_cm")

            return dimensionner_semelle(
                charge_poteau=element.charge_calculee,
                taux_travail_sol=element.taux_travail_sol,
            )
        elif element.type_element == getattr(ElementStructurel.TypeElement, "DALLE", "dalle"):
            # Module 7 : Import dynamique sécurisé si la formule Dev 1 n'est pas encore poussée
            try:
                from moteur_calcul.formules.dimensionnement_dalles import predimensionner_dalle
            except (ImportError, ModuleNotFoundError) as err:
                raise CalculNonDisponible("Module de calcul des dalles pas encore disponible.") from err

            return predimensionner_dalle(
                portee=element.portee,
                charge_calculee=element.charge_calculee,
            )
        elif element.type_element == getattr(ElementStructurel.TypeElement, "SEMELLE_FILANTE", "semelle_filante"):
            # Module 4 : Import dynamique sécurisé si la formule Dev 1 n'est pas encore poussée
            try:
                from moteur_calcul.formules.dimensionnement_semelles_filantes import dimensionner_semelle_filante
            except (ImportError, ModuleNotFoundError) as err:
                raise CalculNonDisponible("Module de calcul des semelles filantes pas encore disponible.") from err

            return dimensionner_semelle_filante(
                charge_lineaire=element.charge_lineaire,
                taux_travail_sol=element.taux_travail_sol,
            )
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