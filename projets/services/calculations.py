from moteur_calcul.formules.dimensionnement_poteaux import dimensionner_poteau
from moteur_calcul.formules.dimensionnement_poutres import dimensionner_poutre
from moteur_calcul.formules.dimensionnement_semelles import dimensionner_semelle
from moteur_calcul.validators import EntreeInvalide

from ..models import ElementStructurel


class CalculNonDisponible(Exception):
    """Levée quand le moteur de calcul n'est pas encore prêt (formules en attente)."""


def calculer_element(element: ElementStructurel) -> dict:
    """
    Appelle la bonne fonction du moteur de calcul selon le type d'élément,
    et retourne le résultat sous forme de dict prêt à stocker dans
    `resultat_calcul`.

    Lève CalculNonDisponible si le moteur de calcul n'a pas encore les
    formules réelles (NotImplementedError propagée depuis moteur_calcul).
    Lève EntreeInvalide si les données de l'élément sont incohérentes.
    """
    try:
        if element.type_element == ElementStructurel.TypeElement.POTEAU:
            return dimensionner_poteau(
                charge_calculee=element.charge_calculee,
                hauteur_poteau=element.hauteur_poteau,
            )
        elif element.type_element == ElementStructurel.TypeElement.POUTRE:
            return dimensionner_poutre(
                portee=element.portee,
                charge_lineaire=element.charge_lineaire,
            )
        elif element.type_element == ElementStructurel.TypeElement.SEMELLE:
            # Prise en compte de la cote du poteau associé si disponible (Module 6)
            cote_poteau = None
            poteau_associe = getattr(element, "poteau_associe", None)
            if poteau_associe:
                res_poteau = poteau_associe.resultat_calcul or {}
                cote_poteau = res_poteau.get("cote_cm")

            return dimensionner_semelle(
                charge_poteau=element.charge_calculee,
                taux_travail_sol=element.taux_travail_sol,
            )
        else:
            raise ValueError(f"Type d'élément inconnu : {element.type_element}")
    except NotImplementedError as exc:
        raise CalculNonDisponible(str(exc)) from exc
    except EntreeInvalide:
        raise  # laissée telle quelle, la vue la traduit en 400


def recalculer_projet(projet):
    """
    Relance le calcul pour tous les éléments d'un projet dont le statut
    est 'propose' ou 'modifie' (jamais pour les éléments déjà 'valide').
    """
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