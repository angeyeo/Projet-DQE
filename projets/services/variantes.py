"""
Variantes de projet : « et si ? » recalculé PAR LE MOTEUR, sans rien
enregistrer.

Méthode : dans une transaction annulée (rollback systématique), on applique
les modifications au projet, on régénère la trame avec le même service que
l'endpoint generer_trame, on retient les résultats du moteur comme
résultats validés, puis on calcule le DQE avec le barème du cabinet.
Aucune estimation locale : chaque variante passe par le chemin de calcul
complet. Les éléments hors trame (dalles, postes) sont repris tels quels.

Limite assumée : variantes disponibles pour les trames régulières
uniquement (un plan IFC importé n'a pas de paramètres de grille à faire
varier).
"""

from django.db import transaction

from moteur_calcul.validators import EntreeInvalide

from ..models import ElementStructurel, Projet
from .dqe_calculator import DQEIncomplet, calculer_projet_dqe
from .parametres_projet import ParametresIncomplets, parametres_structure
from .trame_service import creer_elements_trame

# Paramètres qu'une variante peut modifier, avec leur validation minimale.
CHAMPS_VARIABLES = {
    "charge_permanente_kn_m2": float,
    "charge_exploitation": float,
    "contrainte_sol_kn_m2": float,
    "portee_x": float,
    "portee_y": float,
    "nb_travees_x": int,
    "nb_travees_y": int,
    "nb_niveaux": int,
    "hauteur_etage": float,
    "methode_semelles": str,
    "inclure_poids_propre_ossature": bool,
}
MAX_VARIANTES = 5


class VarianteInvalide(ValueError):
    pass


class _Annuler(Exception):
    pass


def _nettoyer(modifications):
    if not isinstance(modifications, dict):
        raise VarianteInvalide("« modifications » doit être un objet {champ: valeur}.")
    propres = {}
    for champ, valeur in modifications.items():
        if champ not in CHAMPS_VARIABLES:
            raise VarianteInvalide(f"Champ non modifiable dans une variante : « {champ} ».")
        typ = CHAMPS_VARIABLES[champ]
        if valeur is None:
            propres[champ] = None
            continue
        try:
            v = typ(valeur) if typ is not bool else bool(valeur)
        except (TypeError, ValueError):
            raise VarianteInvalide(f"Valeur invalide pour « {champ} » : {valeur!r}.") from None
        if typ in (int, float) and v <= 0:
            raise VarianteInvalide(f"« {champ} » doit être strictement positif.")
        if champ == "methode_semelles" and v not in Projet.MethodeSemelles.values:
            raise VarianteInvalide(f"Méthode de semelles inconnue : {v!r}.")
        propres[champ] = v
    return propres


def _synthese(projet):
    """Résumé chiffré d'un état du projet (dans la transaction en cours)."""
    semelles = list(projet.elements.filter(type_element=ElementStructurel.TypeElement.SEMELLE))
    poteaux = list(projet.elements.filter(type_element=ElementStructurel.TypeElement.POTEAU))
    res = {
        "semelle_cote_max_cm": max((s.resultat_calcul or {}).get("cote_cm", 0) for s in semelles) if semelles else None,
        "poteau_cote_max_cm": max((p.resultat_calcul or {}).get("cote_cm", 0) for p in poteaux) if poteaux else None,
        "effort_max_kn": round(max((p.charge_calculee or 0) for p in poteaux), 2) if poteaux else None,
        "dqe": None,
        "problemes": [],
    }
    try:
        dqe = calculer_projet_dqe(projet, prix_unitaires=projet.entreprise.get_prix_unitaires()
                                  if projet.entreprise_id else None)
    except DQEIncomplet as exc:
        res["problemes"] = exc.problemes
    else:
        res["dqe"] = {"total_general": dqe["total_general"], "synthese": dqe["synthese"],
                      "sous_totaux": dqe["sous_totaux"], "finances": dqe["finances"]}
    return res


def _evaluer(projet_id, modifications):
    """Calcule une variante dans une transaction TOUJOURS annulée."""
    resultat = {}
    try:
        with transaction.atomic():
            projet = Projet.objects.select_for_update().get(pk=projet_id)
            for champ, v in modifications.items():
                setattr(projet, champ, v)
            projet.save()
            prm = parametres_structure(projet, avec_grille=True)
            _, hypotheses = creer_elements_trame(projet, prm)
            # Résultat du moteur retenu tel quel (aucune saisie manuelle).
            for e in projet.elements.all():
                if e.resultat_calcul:
                    e.resultat_valide = e.resultat_calcul
                    e.statut = ElementStructurel.Statut.VALIDE
                    e.save(update_fields=["resultat_valide", "statut"])
            resultat = _synthese(projet)
            resultat["hypotheses"] = sorted(set(hypotheses))
            raise _Annuler
    except _Annuler:
        pass
    return resultat


def calculer_variantes(projet, variantes):
    if not projet.nb_travees_x or not projet.nb_travees_y:
        raise VarianteInvalide("Variantes disponibles pour les trames régulières uniquement "
                               "(renseignez les travées et portées du projet).")
    if not isinstance(variantes, list) or not variantes:
        raise VarianteInvalide("Fournissez au moins une variante.")
    if len(variantes) > MAX_VARIANTES:
        raise VarianteInvalide(f"Au plus {MAX_VARIANTES} variantes par calcul.")
    preparees = []
    for i, v in enumerate(variantes, start=1):
        if not isinstance(v, dict):
            raise VarianteInvalide(f"Variante {i} invalide.")
        preparees.append(((v.get("nom") or f"Variante {i}")[:80], _nettoyer(v.get("modifications") or {})))

    sorties = []
    for nom, modifs in [("Projet actuel (recalculé)", {})] + preparees:
        try:
            r = _evaluer(projet.pk, modifs)
            r.update({"nom": nom, "modifications": modifs, "erreur": None})
        except ParametresIncomplets as exc:
            r = {"nom": nom, "modifications": modifs, "erreur": str(exc)}
        except (ValueError, EntreeInvalide, NotImplementedError) as exc:
            r = {"nom": nom, "modifications": modifs, "erreur": f"Le moteur a refusé cette variante : {exc}"}
        sorties.append(r)

    base = sorties[0].get("dqe") and sorties[0]["dqe"]["total_general"]
    for r in sorties[1:]:
        total = r.get("dqe") and r["dqe"]["total_general"]
        r["ecart_total"] = (total - base) if (total is not None and base) else None
        r["ecart_pct"] = round((total - base) / base * 100, 2) if (total is not None and base) else None
    return sorties
