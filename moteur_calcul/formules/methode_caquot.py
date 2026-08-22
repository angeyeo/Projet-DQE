"""
Méthode de Caquot -- calcul des moments fléchissants d'une poutre
CONTINUE (plusieurs travées), BAEL 91 mod.99 §B.6.2.

dimensionner_poutre() (dimensionnement_poutres.py) ne traite qu'une
poutre ISOSTATIQUE (une seule travée, moment simple ql²/8) : dès qu'une
poutre repose sur plus de deux appuis, les moments sur appuis
(continuité) réduisent le moment en travée mais font apparaître des
moments négatifs (fibre supérieure tendue) qu'il faut aussi ferrailler
-- d'où ce module séparé, appelé ensuite par
dimensionnement_poutres.dimensionner_poutre_continue().

Hypothèses de ce module (à valider par le technicien BTP au cas par
cas, comme le reste du moteur) :
- Charges uniformément réparties sur chaque travée (pas de charges
  ponctuelles).
- Appuis de rive considérés simples (moment nul aux deux extrémités) --
  cas courant en bâtiment (poutre qui ne se prolonge pas au-delà du
  premier/dernier poteau).
- Toutes les travées ont la même largeur/hauteur de section (poutre à
  inertie constante) -- hypothèse implicite de la formule à 8,5.
"""

from ..constantes import COEFFICIENT_CAQUOT, COEFFICIENT_REDUCTION_CAQUOT_MINORE
from ..validators import valider_portee, EntreeInvalide


def valider_donnees_caquot(portees, charges_lineaires):
    """
    Vérifie que les deux listes décrivent bien une poutre continue
    exploitable par la méthode de Caquot : au moins 2 travées, même
    longueur des deux listes, portées et charges valides/positives.
    """
    if portees is None or charges_lineaires is None:
        raise EntreeInvalide("Les portées et les charges linéaires sont obligatoires.")
    if len(portees) != len(charges_lineaires):
        raise EntreeInvalide(
            f"Le nombre de portées ({len(portees)}) doit être égal au nombre de "
            f"charges linéaires ({len(charges_lineaires)})."
        )
    if len(portees) < 2:
        raise EntreeInvalide(
            "La méthode de Caquot suppose au moins 2 travées continues -- "
            "pour une poutre isolée sur 2 appuis, utiliser dimensionner_poutre()."
        )
    for portee in portees:
        valider_portee(portee)
    for charge in charges_lineaires:
        if charge is None or charge <= 0:
            raise EntreeInvalide("Chaque charge linéaire doit être un nombre positif.")
    return True


def portees_reduites_caquot(portees, minore=True):
    """
    "Portées fictives" l' utilisées dans la formule des moments sur
    appuis : la travée réelle pour les deux travées de RIVE (première
    et dernière), 0,8 x la travée réelle pour les travées
    INTERMÉDIAIRES si minore=True (voir COEFFICIENT_REDUCTION_CAQUOT_MINORE
    -- condition Q <= 2G, à vérifier par l'appelant), sinon la travée
    réelle partout (méthode non minorée, plus défavorable).
    """
    n = len(portees)
    return [
        portee if (i == 0 or i == n - 1 or not minore)
        else portee * COEFFICIENT_REDUCTION_CAQUOT_MINORE
        for i, portee in enumerate(portees)
    ]


def calculer_moment_appui_caquot(charge_gauche, portee_gauche_reduite, charge_droite, portee_droite_reduite):
    """
    Moment sur un appui intermédiaire (formule de Caquot, BAEL B.6.2,2) :

        M = -(q_w x l'_w³ + q_e x l'_e³) / (8,5 x (l'_w + l'_e))

    q_w/q_e : charges linéaires ELU des travées gauche/droite adjacentes
    (kN/m). l'_w/l'_e : leurs portées réduites (m, voir
    portees_reduites_caquot()). Retour toujours négatif ou nul (fibre
    supérieure tendue), en kN.m.
    """
    denominateur = COEFFICIENT_CAQUOT * (portee_gauche_reduite + portee_droite_reduite)
    return -(
        charge_gauche * portee_gauche_reduite ** 3 + charge_droite * portee_droite_reduite ** 3
    ) / denominateur


def calculer_moment_travee_caquot(portee, charge_lineaire, moment_appui_gauche, moment_appui_droit):
    """
    Moment maximal en travée d'une poutre continue, compte tenu des
    moments (négatifs ou nuls) repris par les deux appuis qui
    l'encadrent :

        M(x) = M0(x) + Mw x (1 - x/l) + Me x (x/l)

    où M0(x) = q.x.(l-x)/2 est le moment "isostatique" (poutre
    simplement appuyée) et Mw, Me les moments d'appui gauche/droit
    (négatifs). Le maximum est cherché par dérivation (M'(x)=0), puis
    la position est bornée à [0, l] -- une poutre à travées très
    inégales peut mathématiquement sortir de cet intervalle, ce qui
    n'a pas de sens physique.

    Retour : (moment_max_knm, position_x_m).
    """
    if charge_lineaire is None or charge_lineaire <= 0:
        raise EntreeInvalide("La charge linéaire doit être positive.")
    valider_portee(portee)

    x = portee / 2 + (moment_appui_droit - moment_appui_gauche) / (charge_lineaire * portee)
    x = min(max(x, 0.0), portee)

    moment_isostatique = charge_lineaire * x * (portee - x) / 2
    moment_continuite = moment_appui_gauche * (1 - x / portee) + moment_appui_droit * (x / portee)
    return moment_isostatique + moment_continuite, x


def calculer_moments_caquot(portees, charges_lineaires, minore=True):
    """
    Calcule tous les moments (appuis + travées) d'une poutre continue
    à N travées par la méthode de Caquot.

    Paramètres
    ----------
    portees : list[float]
        Portée de chaque travée, en mètres, dans l'ordre (au moins 2).
    charges_lineaires : list[float]
        Charge linéaire ELU de chaque travée, en kN/m (même longueur
        que `portees`).
    minore : bool
        True (défaut) = méthode minorée, portées intermédiaires
        réduites à 0,8L -- valable seulement si Q <= 2G sur l'ensemble
        de la poutre (cas courant en bâtiment d'habitation/bureau).
        False = méthode non minorée (portées réelles partout),
        obligatoire si les charges d'exploitation sont plus lourdes
        (halls, commerces...) -- résultat plus défavorable, donc plus
        sûr dans le doute.

    Retour
    ------
    dict : {
        "portees_reduites_m": [...],           # N valeurs
        "moments_appuis_knm": [...],           # N+1 valeurs (0 aux 2 extrémités)
        "moments_travees_knm": [...],          # N valeurs (max positif attendu)
        "positions_moment_max_m": [...],       # N valeurs, position du max dans chaque travée
    }
    """
    valider_donnees_caquot(portees, charges_lineaires)
    n = len(portees)
    portees_reduites = portees_reduites_caquot(portees, minore=minore)

    moments_appuis = [0.0] * (n + 1)
    for i in range(1, n):
        moments_appuis[i] = calculer_moment_appui_caquot(
            charge_gauche=charges_lineaires[i - 1],
            portee_gauche_reduite=portees_reduites[i - 1],
            charge_droite=charges_lineaires[i],
            portee_droite_reduite=portees_reduites[i],
        )

    moments_travees = []
    positions = []
    for i in range(n):
        moment, position = calculer_moment_travee_caquot(
            portee=portees[i],
            charge_lineaire=charges_lineaires[i],
            moment_appui_gauche=moments_appuis[i],
            moment_appui_droit=moments_appuis[i + 1],
        )
        moments_travees.append(moment)
        positions.append(position)

    return {
        "portees_reduites_m": [round(p, 3) for p in portees_reduites],
        "moments_appuis_knm": [round(m, 2) for m in moments_appuis],
        "moments_travees_knm": [round(m, 2) for m in moments_travees],
        "positions_moment_max_m": [round(p, 2) for p in positions],
    }