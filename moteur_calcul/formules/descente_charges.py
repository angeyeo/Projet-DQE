"""
Descente de charges -- BAEL 91 mod.99 (référentiel par défaut).

Formules basées sur le document "reference_technique_BAEL_EC2_DQE"
(sections 2.2 à 2.4) fourni par le technicien BTP.
"""

from ..constantes import (
    CHARGES_EXPLOITATION,
    POIDS_VOLUMIQUE_BETON,
    COEFFICIENT_G_ELU,
    COEFFICIENT_Q_ELU,
    COEFFICIENTS_DEGRESSION,
    USAGES_AVEC_DEGRESSION,
    POIDS_COUCHES_COURANTES,
)
from ..validators import valider_surface, valider_usage_batiment


def calculer_surface_influence(portee_gauche, portee_droite, portee_avant, portee_arriere):
    """
    Surface d'influence (aire tributaire) d'un poteau, selon les portées
    des travées qui l'entourent de chaque côté.

    Formule (document technicien, section 2.4) :
        S = (portee_gauche/2 + portee_droite/2) x (portee_avant/2 + portee_arriere/2)

    Paramètres en mètres. Retour en m².
    """
    for p in (portee_gauche, portee_droite, portee_avant, portee_arriere):
        if p is None or p < 0:
            raise ValueError("Toutes les portées doivent être positives ou nulles.")
    largeur = (portee_gauche / 2) + (portee_droite / 2)
    profondeur = (portee_avant / 2) + (portee_arriere / 2)
    return largeur * profondeur


def calculer_charge_permanente(surface, epaisseur_dalle, poids_volumique_beton=None):
    """
    Charge permanente (poids propre) d'un niveau, ramenée à la surface
    d'influence d'un appui.

    G = surface x epaisseur_dalle x poids_volumique_beton

    Retour : charge permanente en kN.

    Note : ne compte que la dalle béton. Pour un plancher réel
    (étanchéité, forme de pente, chape, revêtement, enduit, cloisons),
    utiliser calculer_charge_permanente_composee().
    """
    valider_surface(surface)
    if epaisseur_dalle is None or epaisseur_dalle <= 0:
        raise ValueError("L'épaisseur de dalle doit être positive.")
    poids_volumique = poids_volumique_beton or POIDS_VOLUMIQUE_BETON
    return surface * epaisseur_dalle * poids_volumique


def calculer_charge_permanente_composee(surface, couches):
    """
    Charge permanente d'un plancher décrit par ses couches successives
    (Phase 2, module 2) -- remplace l'approximation "dalle béton seule"
    de calculer_charge_permanente() dès que la composition réelle du
    plancher est connue (étanchéité, forme de pente, chape, carrelage,
    enduit, cloisons...).

    Paramètres
    ----------
    surface : float
        Surface d'influence, en m².
    couches : list[dict]
        Une entrée par couche, dans l'ordre du haut vers le bas (l'ordre
        n'a pas d'incidence sur le total, il sert juste à relire le
        détail). Chaque couche accepte l'une des deux descriptions :

            {"designation": "chape",
             "epaisseur_m": 0.05,
             "poids_volumique_kn_m3": 20.0}

            {"designation": "étanchéité",
             "poids_surfacique_kn_m2": 0.12}

        Une couche peut aussi référencer le catalogue par sa clé :
            {"type": "chape_mortier", "epaisseur_m": 0.05}
        (voir constantes.POIDS_COUCHES_COURANTES)

    Retour
    ------
    dict : {
        "charge_totale_kn": float,
        "charge_surfacique_totale_kn_m2": float,
        "detail": [ {"designation", "poids_surfacique_kn_m2", "charge_kn"}, ... ],
    }
    """
    valider_surface(surface)
    if not couches:
        raise ValueError(
            "Au moins une couche est requise -- utiliser "
            "calculer_charge_permanente() pour le cas dalle béton seule."
        )

    detail = []
    charge_surfacique_totale = 0.0

    for index, couche in enumerate(couches):
        reference = POIDS_COUCHES_COURANTES.get(couche.get("type"), {})
        designation = couche.get("designation") or couche.get("type") or f"couche {index + 1}"

        poids_surfacique = couche.get(
            "poids_surfacique_kn_m2", reference.get("poids_surfacique_kn_m2")
        )

        if poids_surfacique is None:
            poids_volumique = couche.get(
                "poids_volumique_kn_m3", reference.get("poids_volumique_kn_m3")
            )
            epaisseur = couche.get("epaisseur_m")
            if poids_volumique is None or epaisseur is None:
                raise ValueError(
                    f"Couche '{designation}' incomplète : fournir soit "
                    f"'poids_surfacique_kn_m2', soit 'epaisseur_m' + "
                    f"'poids_volumique_kn_m3' (ou un 'type' du catalogue)."
                )
            if epaisseur <= 0 or poids_volumique <= 0:
                raise ValueError(f"Couche '{designation}' : épaisseur et poids doivent être positifs.")
            poids_surfacique = epaisseur * poids_volumique
        elif poids_surfacique <= 0:
            raise ValueError(f"Couche '{designation}' : le poids surfacique doit être positif.")

        charge_surfacique_totale += poids_surfacique
        detail.append({
            "designation": designation,
            "poids_surfacique_kn_m2": round(poids_surfacique, 3),
            "charge_kn": round(poids_surfacique * surface, 2),
        })

    return {
        "charge_totale_kn": round(charge_surfacique_totale * surface, 2),
        "charge_surfacique_totale_kn_m2": round(charge_surfacique_totale, 3),
        "detail": detail,
    }


def calculer_charge_exploitation(surface, usage_batiment):
    """
    Charge d'exploitation Q, ramenée à la surface d'influence.

    Q = surface x charge_unitaire(usage)
    """
    valider_surface(surface)
    valider_usage_batiment(usage_batiment)
    charge_unitaire = CHARGES_EXPLOITATION[usage_batiment]
    if charge_unitaire is None:
        raise NotImplementedError(
            f"CHARGES_EXPLOITATION['{usage_batiment}'] non fournie par le "
            f"technicien -- à demander avant de calculer cet usage."
        )
    return surface * charge_unitaire


def degression_applicable(usage_batiment):
    """
    Dit si la loi de dégression peut être appliquée pour cet usage.

    La dégression suppose que les niveaux ne sont pas chargés à fond en
    même temps (occupations indépendantes). Vrai en habitation et en
    bureaux, faux en commerce ou en industrie où tous les niveaux
    peuvent être pleins simultanément -- voir
    constantes.USAGES_AVEC_DEGRESSION.
    """
    return usage_batiment in USAGES_AVEC_DEGRESSION


def coefficient_degression(nb_etages_charges):
    """
    Coefficient de dégression appliqué à la SOMME des charges
    d'exploitation des étages situés au-dessus de l'appui considéré
    (toiture non comprise, elle n'est jamais dégressée).

    Loi NF P06-001 (voir constantes.COEFFICIENTS_DEGRESSION) :
        n <= 4 : valeur du tableau (1,00 / 0,95 / 0,90 / 0,85)
        n >= 5 : coef = (3 + n) / (2 x n)

    Paramètres
    ----------
    nb_etages_charges : int
        Nombre d'étages chargés au-dessus de l'appui (n).

    Retour : coefficient entre 0,5 et 1,0 (sans dimension).
    """
    if nb_etages_charges is None or nb_etages_charges < 0:
        raise ValueError("Le nombre d'étages chargés doit être positif ou nul.")
    if nb_etages_charges == 0:
        return 1.0
    if nb_etages_charges <= len(COEFFICIENTS_DEGRESSION):
        return COEFFICIENTS_DEGRESSION[nb_etages_charges - 1]
    return (3 + nb_etages_charges) / (2 * nb_etages_charges)


def cumuler_charges_exploitation_degressives(
    charge_toiture_kn, charges_etages_kn, usage_batiment=None
):
    """
    Cumule les charges d'exploitation en descendant, en appliquant la
    loi de dégression.

    Paramètres
    ----------
    charge_toiture_kn : float
        Charge d'exploitation du niveau le plus haut (toiture ou
        terrasse), en kN. Jamais dégressée.
    charges_etages_kn : list[float]
        Charges d'exploitation des étages courants, ordonnées du HAUT
        vers le BAS (index 0 = étage juste sous la toiture), en kN.
    usage_batiment : str, optionnel
        Si fourni et que l'usage n'autorise pas la dégression (voir
        degression_applicable), les charges sont simplement sommées
        sans réduction -- le cumul reste correct, juste non réduit.

    Retour
    ------
    dict : {
        "cumuls_kn": list[float],   # Q cumulé sous chaque niveau, du haut vers le bas
                                    # (index 0 = sous la toiture)
        "coefficients": list[float],
        "degression_appliquee": bool,
    }
    """
    if charge_toiture_kn is None or charge_toiture_kn < 0:
        raise ValueError("La charge d'exploitation de toiture doit être positive ou nulle.")
    if charges_etages_kn is None:
        raise ValueError("La liste des charges d'étage est requise (éventuellement vide).")
    if any(c is None or c < 0 for c in charges_etages_kn):
        raise ValueError("Toutes les charges d'étage doivent être positives ou nulles.")

    appliquer = usage_batiment is None or degression_applicable(usage_batiment)

    cumuls = [charge_toiture_kn]
    coefficients = [1.0]
    somme_etages = 0.0

    for index, charge_etage in enumerate(charges_etages_kn, start=1):
        somme_etages += charge_etage
        coef = coefficient_degression(index) if appliquer else 1.0
        coefficients.append(coef)
        cumuls.append(charge_toiture_kn + coef * somme_etages)

    return {
        "cumuls_kn": [round(c, 2) for c in cumuls],
        "coefficients": coefficients,
        "degression_appliquee": appliquer and len(charges_etages_kn) > 1,
    }


def calculer_charge_ponderee_elu(charge_permanente, charge_exploitation):
    """Combinaison ELU : Nu = 1,35 G + 1,5 Q"""
    if charge_permanente is None or charge_exploitation is None:
        raise ValueError("Charges permanente et exploitation requises.")
    return COEFFICIENT_G_ELU * charge_permanente + COEFFICIENT_Q_ELU * charge_exploitation


def calculer_charge_ponderee_els(charge_permanente, charge_exploitation):
    """Combinaison ELS : Ns = G + Q"""
    if charge_permanente is None or charge_exploitation is None:
        raise ValueError("Charges permanente et exploitation requises.")
    return charge_permanente + charge_exploitation


def calculer_charge_totale_niveau(charges_par_niveau_elu):
    """
    Cumule la charge ELU descendant sur un appui, niveau par niveau.

    Paramètres
    ----------
    charges_par_niveau_elu : list[float]
        Charges ELU (kN) de chaque niveau au-dessus de l'appui, déjà
        calculées via calculer_charge_ponderee_elu.

    Retour : charge ELU cumulée totale en kN.

    Note : somme directe, pas de dégression des charges d'exploitation
    pour les niveaux élevés -- à confirmer avec le technicien si le
    bâtiment dépasse quelques niveaux.
    """
    if not charges_par_niveau_elu:
        raise ValueError("La liste des charges par niveau ne peut pas être vide.")
    if any(c is None or c < 0 for c in charges_par_niveau_elu):
        raise ValueError("Toutes les charges par niveau doivent être positives.")
    return sum(charges_par_niveau_elu)


def calculer_descente_charges_complete(
    portee_gauche,
    portee_droite,
    portee_avant,
    portee_arriere,
    epaisseur_dalle,
    usage_batiment,
    nb_niveaux,
    avec_degression=True,
    usage_toiture=None,
    couches_permanentes=None,
):
    """
    Chaîne complète de descente de charges, du plan jusqu'à la charge
    ELU cumulée sur un poteau -- automatise ce que l'exercice de
    vérification faisait à la main (surface d'influence -> G -> Q ->
    ELU par niveau -> cumul sur nb_niveaux).

    Le niveau le plus haut est traité comme la toiture : sa charge
    d'exploitation n'est jamais dégressée, et son usage peut différer
    de celui des étages courants (paramètre usage_toiture).

    Hypothèse simplificatrice : tous les étages courants sont
    identiques (même trame, même épaisseur de dalle, même usage).

    Paramètres
    ----------
    portee_gauche, portee_droite, portee_avant, portee_arriere : float
        Portées des travées autour du poteau, en mètres.
    epaisseur_dalle : float
        Épaisseur de la dalle, en mètres (identique à chaque niveau).
        Ignoré si couches_permanentes est fourni.
    usage_batiment : str
        Usage des étages courants (voir constantes.CHARGES_EXPLOITATION).
    nb_niveaux : int
        Nombre de niveaux dont la charge descend sur ce poteau
        (toiture comprise).
    avec_degression : bool
        Applique la loi de dégression sur les charges d'exploitation
        des étages (voir cumuler_charges_exploitation_degressives).
        Sans effet si l'usage ne l'autorise pas, ou s'il n'y a qu'un
        seul étage sous la toiture.
    usage_toiture : str, optionnel
        Usage du niveau le plus haut, s'il diffère (typiquement
        "toiture_terrasse" ou "toiture_inaccessible"). Par défaut,
        même usage que les étages.
    couches_permanentes : list[dict], optionnel
        Composition du plancher courant, si elle est connue -- voir
        calculer_charge_permanente_composee(). Remplace le calcul
        "dalle béton seule" basé sur epaisseur_dalle.

    Retour
    ------
    dict : {
        "surface_influence_m2": float,
        "charge_permanente_par_niveau_kn": float,
        "charge_exploitation_par_niveau_kn": float,
        "charge_elu_par_niveau_kn": float,          # étage courant, non dégressé
        "charge_permanente_cumulee_kn": float,
        "charge_exploitation_cumulee_kn": float,    # après dégression
        "coefficient_degression": float,            # celui appliqué au pied
        "degression_appliquee": bool,
        "charge_elu_cumulee_kn": float,   # à passer à dimensionner_poteau/semelle
        "charge_els_cumulee_kn": float,
    }
    """
    if nb_niveaux is None or nb_niveaux <= 0:
        raise ValueError("Le nombre de niveaux doit être positif.")

    surface = calculer_surface_influence(
        portee_gauche, portee_droite, portee_avant, portee_arriere
    )

    if couches_permanentes:
        charge_g = calculer_charge_permanente_composee(surface, couches_permanentes)["charge_totale_kn"]
    else:
        charge_g = calculer_charge_permanente(surface, epaisseur_dalle)

    charge_q_etage = calculer_charge_exploitation(surface, usage_batiment)
    charge_q_toiture = (
        calculer_charge_exploitation(surface, usage_toiture)
        if usage_toiture
        else charge_q_etage
    )

    charge_elu_niveau = calculer_charge_ponderee_elu(charge_g, charge_q_etage)

    nb_etages = nb_niveaux - 1
    charges_etages = [charge_q_etage] * nb_etages

    if avec_degression:
        degression = cumuler_charges_exploitation_degressives(
            charge_q_toiture, charges_etages, usage_batiment
        )
        charge_q_cumulee = degression["cumuls_kn"][-1]
        coefficient = degression["coefficients"][-1]
        degression_appliquee = degression["degression_appliquee"]
    else:
        charge_q_cumulee = charge_q_toiture + sum(charges_etages)
        coefficient = 1.0
        degression_appliquee = False

    charge_g_cumulee = calculer_charge_totale_niveau([charge_g] * nb_niveaux)
    charge_cumulee = calculer_charge_ponderee_elu(charge_g_cumulee, charge_q_cumulee)

    return {
        "surface_influence_m2": round(surface, 2),
        "charge_permanente_par_niveau_kn": round(charge_g, 2),
        "charge_exploitation_par_niveau_kn": round(charge_q_etage, 2),
        "charge_elu_par_niveau_kn": round(charge_elu_niveau, 2),
        "charge_permanente_cumulee_kn": round(charge_g_cumulee, 2),
        "charge_exploitation_cumulee_kn": round(charge_q_cumulee, 2),
        "coefficient_degression": coefficient,
        "degression_appliquee": degression_appliquee,
        "charge_elu_cumulee_kn": round(charge_cumulee, 2),
        "charge_els_cumulee_kn": round(
            calculer_charge_ponderee_els(charge_g_cumulee, charge_q_cumulee), 2
        ),
    }