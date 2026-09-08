"""
Contrôle de cohérence déterministe V1 — résultats structurels.

Ce module analyse les résultats de calcul d'un élément structurel
et retourne des signaux de cohérence SANS appel LLM.

Règles métier implémentées (validées avec Ange) :
  1. PRESSION_SOL_DEPASSEE     — semelle / semelle_filante
  2. FRETTAGE_ACIER_DEPASSE    — poteau
  3. HYPOTHESE_SOL_NON_CONFIRMEE — semelle / semelle_filante
  4. MINIMUM_NON_FRAGILITE_APPLIQUE — poutre / longrine

Fraîcheur des résultats :
  - VALIDE + resultat_valide  → analyse autorisée
  - MODIFIE                   → CALCUL_A_REFAIRE (pas d'analyse)
  - PROPOSE + resultat_calcul → CALCUL_A_VALIDER (pas d'analyse V1)
  - PROPOSE sans résultat     → CALCUL_NON_DISPONIBLE
  - Autre / sans résultat     → CALCUL_NON_DISPONIBLE

INTERDIT :
  - element.save() ou toute écriture DB
  - appel au moteur de calcul
  - appel LLM (get_ai_client, appeler_llm, etc.)
  - invention de seuils ou formules
"""

import logging

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Priorité des catégories (ordre décroissant)
# ---------------------------------------------------------------------------
_PRIORITE_CATEGORIES = {"CRITIQUE": 3, "ATTENTION": 2, "INFORMATION": 1}


def _est_bool_strict(value):
    """Retourne True ssi value est un bool Python natif (pas int, pas str)."""
    return isinstance(value, bool)


def _est_numerique_strict(value):
    """Retourne True ssi value est int ou float, mais pas bool."""
    return isinstance(value, (int, float)) and not isinstance(value, bool)


def _valeur_numerique_ou_none(resultat, cle):
    """Extrait une valeur numérique stricte depuis le résultat, ou None."""
    value = resultat.get(cle)
    if value is not None and _est_numerique_strict(value):
        return value
    return None


# ---------------------------------------------------------------------------
# Sélection du résultat selon la fraîcheur
# ---------------------------------------------------------------------------
def _selectionner_resultat(element):
    """
    Détermine le résultat exploitable et le statut d'analyse associé.

    Returns:
        tuple (resultat_dict | None, source_resultat | None, statut_analyse | None, message_local | None)
        - Si statut_analyse n'est pas None, l'analyse métier est bloquée.
    """
    statut = getattr(element, "statut", None)

    # CAS 1 — VALIDE + resultat_valide
    if statut == "valide":
        resultat_valide = getattr(element, "resultat_valide", None)
        if resultat_valide and isinstance(resultat_valide, dict):
            return resultat_valide, "resultat_valide", None, None
        # VALIDE mais pas de resultat_valide → pas exploitable
        return None, None, "CALCUL_NON_DISPONIBLE", (
            "Aucun résultat de calcul exploitable n'est disponible "
            "pour cet élément."
        )

    # CAS 2 — MODIFIE
    if statut == "modifie":
        return None, None, "CALCUL_A_REFAIRE", (
            "L'élément a été modifié depuis sa validation. "
            "Relancez le calcul et validez l'élément avant "
            "l'analyse de cohérence."
        )

    # CAS 3 — PROPOSE
    if statut == "propose":
        resultat_calcul = getattr(element, "resultat_calcul", None)
        if resultat_calcul and isinstance(resultat_calcul, dict):
            return None, None, "CALCUL_A_VALIDER", (
                "Le résultat n'a pas encore été validé. "
                "Relancez le calcul si les paramètres ont été modifiés, "
                "puis validez l'élément avant l'analyse de cohérence."
            )
        return None, None, "CALCUL_NON_DISPONIBLE", (
            "Aucun résultat de calcul exploitable n'est disponible "
            "pour cet élément."
        )

    # AUTRES CAS — statut inconnu ou absent
    return None, None, "CALCUL_NON_DISPONIBLE", (
        "Aucun résultat de calcul exploitable n'est disponible "
        "pour cet élément."
    )


# ---------------------------------------------------------------------------
# Règles métier
# ---------------------------------------------------------------------------

def _verifier_pression_sol_semelle(resultat):
    """
    Règle 1 — PRESSION_SOL_DEPASSEE (semelle / semelle_filante).

    Condition : resultat["condition_respectee"] is False
    """
    signaux = []

    condition = resultat.get("condition_respectee")
    if not _est_bool_strict(condition):
        # Champ absent ou type inattendu → pas de signal
        return signaux

    if condition is False:
        # Déterminer les valeurs numériques selon le type de semelle
        # Semelle affinée : pression_reelle_mpa
        # Semelle filante : pression_reelle_kn_m2
        valeur_mesuree = None
        valeur_limite = None
        unite = None

        pression_mpa = _valeur_numerique_ou_none(resultat, "pression_reelle_mpa")
        if pression_mpa is not None:
            valeur_mesuree = pression_mpa
            # contrainte_sol_mpa n'est pas dans le dict retourné par le moteur
            unite = "MPa"
        else:
            pression_kn = _valeur_numerique_ou_none(
                resultat, "pression_reelle_kn_m2"
            )
            if pression_kn is not None:
                valeur_mesuree = pression_kn
                # contrainte_sol n'est pas dans le dict retourné par le moteur
                unite = "kN/m²"

        signaux.append({
            "code": "PRESSION_SOL_DEPASSEE",
            "categorie": "CRITIQUE",
            "champ_analyse": "condition_respectee",
            "valeur_mesuree": valeur_mesuree,
            "valeur_limite": valeur_limite,
            "unite": unite,
            "source_regle": "MOTEUR_DETERMINISTE",
            "origine_regle": "dimensionnement_semelles",
            "message_local": (
                "La condition de pression du sol n'est pas satisfaite. "
                "Une vérification / correction du dimensionnement "
                "est requise."
            ),
        })

    return signaux


def _verifier_hypothese_sol(resultat):
    """
    Règle 3 — HYPOTHESE_SOL_NON_CONFIRMEE (semelle / semelle_filante).

    Condition : resultat["hypothese_sol"] is True
    """
    signaux = []

    hypothese = resultat.get("hypothese_sol")
    if not _est_bool_strict(hypothese):
        return signaux

    if hypothese is True:
        signaux.append({
            "code": "HYPOTHESE_SOL_NON_CONFIRMEE",
            "categorie": "ATTENTION",
            "champ_analyse": "hypothese_sol",
            "valeur_mesuree": None,
            "valeur_limite": None,
            "unite": None,
            "source_regle": "HYPOTHESE_PROJET",
            "origine_regle": "dimensionnement_semelles",
            "message_local": (
                "La contrainte du sol utilisée repose sur une hypothèse "
                "par défaut. Une vérification à partir des données "
                "géotechniques du projet est requise."
            ),
        })

    return signaux


def _verifier_frettage_poteau(resultat):
    """
    Règle 2 — FRETTAGE_ACIER_DEPASSE (poteau).

    Condition : resultat["frettage_necessaire"] is True
    """
    signaux = []

    frettage = resultat.get("frettage_necessaire")
    if not _est_bool_strict(frettage):
        return signaux

    if frettage is True:
        valeur_mesuree = _valeur_numerique_ou_none(
            resultat, "section_acier_retenue_cm2"
        )
        valeur_limite = _valeur_numerique_ou_none(
            resultat, "section_acier_max_cm2"
        )
        unite = "cm²" if (valeur_mesuree is not None or valeur_limite is not None) else None

        signaux.append({
            "code": "FRETTAGE_ACIER_DEPASSE",
            "categorie": "CRITIQUE",
            "champ_analyse": "frettage_necessaire",
            "valeur_mesuree": valeur_mesuree,
            "valeur_limite": valeur_limite,
            "unite": unite,
            "source_regle": "MOTEUR_DETERMINISTE",
            "origine_regle": "dimensionnement_poteaux",
            "message_local": (
                "La section d'acier retenue dépasse la limite calculée "
                "par le moteur. Une vérification / correction du "
                "dimensionnement est requise."
            ),
        })

    return signaux


def _verifier_non_fragilite(resultat):
    """
    Règle 4 — MINIMUM_NON_FRAGILITE_APPLIQUE (poutre / longrine).

    Condition : resultat["non_fragilite_respectee"] is False
    """
    signaux = []

    non_frag = resultat.get("non_fragilite_respectee")
    if not _est_bool_strict(non_frag):
        return signaux

    if non_frag is False:
        valeur_mesuree = _valeur_numerique_ou_none(
            resultat, "section_acier_theorique_cm2"
        )
        valeur_limite = _valeur_numerique_ou_none(
            resultat, "section_acier_min_cm2"
        )
        unite = "cm²" if (valeur_mesuree is not None or valeur_limite is not None) else None

        signaux.append({
            "code": "MINIMUM_NON_FRAGILITE_APPLIQUE",
            "categorie": "INFORMATION",
            "champ_analyse": "non_fragilite_respectee",
            "valeur_mesuree": valeur_mesuree,
            "valeur_limite": valeur_limite,
            "unite": unite,
            "source_regle": "MOTEUR_DETERMINISTE",
            "origine_regle": "dimensionnement_poutres",
            "message_local": (
                "Le minimum de non-fragilité gouverne le ferraillage "
                "retenu par le moteur."
            ),
        })

    return signaux


# ---------------------------------------------------------------------------
# Dispatch des règles par type d'élément
# ---------------------------------------------------------------------------
_REGLES_PAR_TYPE = {
    "semelle": [_verifier_hypothese_sol],
    "semelle_filante": [_verifier_pression_sol_semelle, _verifier_hypothese_sol],
    "poteau": [_verifier_frettage_poteau],
    "poutre": [_verifier_non_fragilite],
    "longrine": [_verifier_non_fragilite],
}


def _determiner_statut_global(signaux):
    """Retourne la catégorie la plus élevée parmi les signaux."""
    if not signaux:
        return "AUCUN_SIGNAL"
    meilleur = max(
        signaux,
        key=lambda s: _PRIORITE_CATEGORIES.get(s.get("categorie", ""), 0),
    )
    return meilleur["categorie"]


# ---------------------------------------------------------------------------
# Fonction publique principale
# ---------------------------------------------------------------------------

def analyser_element_coherence(element):
    """
    Analyse la cohérence des résultats d'un élément structurel.

    READ ONLY — aucune mutation de l'élément ni de la base de données.

    Args:
        element: instance de ElementStructurel (Django model)

    Returns:
        dict avec la structure stable documentée dans la conception V1.
    """
    element_id = getattr(element, "id", None) or getattr(element, "pk", None)
    identifiant = getattr(element, "identifiant", None)
    type_element = getattr(element, "type_element", None)
    statut_element = getattr(element, "statut", None)

    # --- Sélection du résultat selon la fraîcheur ---
    resultat, source_resultat, statut_bloque, message_bloque = (
        _selectionner_resultat(element)
    )

    if statut_bloque is not None:
        # Fraîcheur insuffisante → pas d'analyse métier
        return {
            "element_id": element_id,
            "identifiant": identifiant,
            "type_element": type_element,
            "statut_element": statut_element,
            "source_resultat": source_resultat,
            "statut_analyse": statut_bloque,
            "nombre_signaux": 0,
            "signaux": [],
            "explication_ia": None,
            "source_explication": "LOCAL",
            "message_local": message_bloque,
            "validation_humaine_requise": True,
        }

    # --- Analyse métier ---
    regles = _REGLES_PAR_TYPE.get(type_element, [])
    signaux = []

    for regle in regles:
        try:
            signaux.extend(regle(resultat))
        except Exception:
            logger.exception(
                "Erreur inattendue dans la règle %s pour l'élément %s",
                getattr(regle, "__name__", "?"),
                identifiant,
            )
            # Ne pas crasher — continuer avec les autres règles

    statut_analyse = _determiner_statut_global(signaux)

    # Message local selon le statut
    if statut_analyse == "AUCUN_SIGNAL":
        message_local = (
            "Aucun signal de cohérence n'a été identifié parmi les "
            "contrôles disponibles dans cette version."
        )
    elif statut_analyse == "CRITIQUE":
        message_local = (
            "Un ou plusieurs contrôles critiques ont été détectés. "
            "Une vérification est requise avant de poursuivre."
        )
    elif statut_analyse == "ATTENTION":
        message_local = (
            "Un ou plusieurs points d'attention ont été relevés. "
            "Une vérification est recommandée."
        )
    else:
        message_local = (
            "Des informations techniques complémentaires sont "
            "disponibles pour cet élément."
        )

    return {
        "element_id": element_id,
        "identifiant": identifiant,
        "type_element": type_element,
        "statut_element": statut_element,
        "source_resultat": source_resultat,
        "statut_analyse": statut_analyse,
        "nombre_signaux": len(signaux),
        "signaux": signaux,
        "explication_ia": None,
        "source_explication": "LOCAL",
        "message_local": message_local,
        "validation_humaine_requise": True,
    }


def analyser_projet_coherence(projet) -> dict:
    """
    Exécute l'analyse de cohérence déterministe sur tous les éléments d'un projet.

    Règles :
    - Strictement déterministe et locale (aucun appel LLM).
    - Lecture seule (aucune écriture DB, aucun recalcul moteur).
    - Agrégation par statut_analyse des éléments (compte des éléments par statut).
    - Ordre des éléments garanti par `.order_by("id")`.
    """
    if projet is None:
        raise ValueError("Le projet ne peut pas être None.")

    projet_id = getattr(projet, "id", None) or getattr(projet, "pk", None)
    nom_projet = getattr(projet, "nom", "")

    # Extraction des éléments dans un ordre strictement déterministe
    elements_qs = projet.elements.all().order_by("id")

    elements_analyses = []
    critiques = 0
    attentions = 0
    informations = 0
    aucun_signal = 0
    calculs_a_valider = 0
    calculs_a_refaire = 0
    calculs_non_disponibles = 0

    for element in elements_qs:
        res_elem = analyser_element_coherence(element)
        elements_analyses.append(res_elem)

        statut = res_elem.get("statut_analyse")
        if statut == "CRITIQUE":
            critiques += 1
        elif statut == "ATTENTION":
            attentions += 1
        elif statut == "INFORMATION":
            informations += 1
        elif statut == "AUCUN_SIGNAL":
            aucun_signal += 1
        elif statut == "CALCUL_A_VALIDER":
            calculs_a_valider += 1
        elif statut == "CALCUL_A_REFAIRE":
            calculs_a_refaire += 1
        elif statut == "CALCUL_NON_DISPONIBLE":
            calculs_non_disponibles += 1

    return {
        "projet_id": projet_id,
        "nom_projet": nom_projet,
        "resume": {
            "total_elements": len(elements_analyses),
            "critiques": critiques,
            "attentions": attentions,
            "informations": informations,
            "aucun_signal": aucun_signal,
            "calculs_a_valider": calculs_a_valider,
            "calculs_a_refaire": calculs_a_refaire,
            "calculs_non_disponibles": calculs_non_disponibles,
        },
        "elements": elements_analyses,
    }
