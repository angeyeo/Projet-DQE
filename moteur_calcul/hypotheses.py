"""
Hypothèses de calcul d'un projet : UNE source, explicite et traçable.

Toute grandeur qui n'est pas une donnée saisie par l'utilisateur (G
forfaitaire, contrainte de sol par défaut, méthode des semelles...) est
portée ici, avec son ORIGINE, et recopiée dans le résultat de chaque
élément ("hypotheses_calcul") : l'écran « Voir le calcul » et les exports
peuvent ainsi toujours dire d'où vient un chiffre.

Origines possibles d'une valeur :
    "saisie"      valeur entrée par l'utilisateur pour ce projet
    "couches"     calculée à partir de la composition du plancher saisie
    "usage"       valeur normative déduite de l'usage (constantes.py)
    "forfait"     valeur par défaut du moteur (G = 5 kN/m², contenu validé
                  par le technicien BTP) -- à remplacer par la composition
                  réelle du plancher si elle diffère
    "defaut"      valeur par défaut du moteur (contrainte du sol)
    "valide_technicien"  valeur par défaut validée par le technicien BTP
                  (Q de toiture)

Décisions métier validées par le technicien BTP le 07/10/2026 :
    1. semelles dimensionnées à l'ELU (A² ≥ Nu / σsol) ;
    2. poids propre des poutres et poteaux AJOUTÉ à G par défaut ;
    3. G = 5 kN/m² pour un plancher courant (hourdis 16+4, chape,
       carrelage, enduit sous-face, cloisons) ;
    6. Q de toiture = 1,5 kN/m².
"""

from dataclasses import asdict, dataclass, field

from .constantes import (
    CHARGE_EXPLOITATION_TOITURE_KN_M2,
    COEFFICIENT_G_ELS,
    COEFFICIENT_G_ELU,
    COEFFICIENT_Q_ELS,
    COEFFICIENT_Q_ELU,
    CONTRAINTE_SOL_DEFAUT,
    POIDS_VOLUMIQUE_BETON,
)
from .formules.descente_charges import calculer_charge_permanente_composee

# Charge permanente des planchers retenue quand ni G ni la composition du
# plancher ne sont saisis. VALEUR VALIDÉE PAR LE TECHNICIEN BTP
# (07/10/2026) pour un plancher courant : dalle à hourdis 16+4 avec
# chape, carrelage, enduit sous-face et cloisons. Toujours signalée
# dans les hypothèses du projet, jamais silencieuse.
# Interprétation retenue : les 5 kN/m² sont le TOTAL du plancher (corps
# 16+4 compris) -- cohérent avec l'ordre de grandeur usuel (~2,8 kN/m²
# pour le 16+4 + ~2,2 kN/m² de finitions et cloisons). À reconfirmer.
G_PLANCHER_FORFAITAIRE_KN_M2 = 5.0
CONTENU_G_FORFAITAIRE = "plancher à hourdis 16+4, chape, carrelage, enduit sous-face et cloisons"

METHODES_SEMELLES = ("ELU", "ELS")
# Défauts d'un NOUVEAU projet (validés par le technicien BTP).
METHODE_SEMELLES_PAR_DEFAUT = "ELU"
POIDS_PROPRE_OSSATURE_PAR_DEFAUT = True


@dataclass(frozen=True)
class HypothesesCalcul:
    g_plancher_kn_m2: float
    origine_g: str
    q_kn_m2: float
    origine_q: str
    inclure_poids_propre_ossature: bool = False
    methode_semelles: str = "ELU"
    # Q de la toiture (dernier niveau). None = même valeur que les étages
    # (comportement historique des appels directs au moteur) ; les projets
    # passent la valeur validée (1,5 kN/m²) via parametres_projet.
    q_toiture_kn_m2: float | None = None
    origine_q_toiture: str | None = None
    contrainte_sol_kn_m2: float | None = None
    detail_g: tuple = field(default_factory=tuple)
    gamma_g_elu: float = COEFFICIENT_G_ELU
    gamma_q_elu: float = COEFFICIENT_Q_ELU
    gamma_g_els: float = COEFFICIENT_G_ELS
    gamma_q_els: float = COEFFICIENT_Q_ELS
    poids_volumique_beton_kn_m3: float = POIDS_VOLUMIQUE_BETON

    def __post_init__(self):
        if self.g_plancher_kn_m2 is None or self.g_plancher_kn_m2 <= 0:
            raise ValueError("La charge permanente des planchers G doit être strictement positive (kN/m²).")
        if self.q_kn_m2 is None or self.q_kn_m2 <= 0:
            raise ValueError(
                "Charge d'exploitation non définie : renseignez-la ou choisissez un "
                "usage du bâtiment pour lequel une valeur normative existe."
            )
        if self.q_toiture_kn_m2 is not None and self.q_toiture_kn_m2 <= 0:
            raise ValueError("La charge d'exploitation de toiture doit être strictement positive (kN/m²).")
        if self.methode_semelles not in METHODES_SEMELLES:
            raise ValueError(f"Méthode de dimensionnement des semelles inconnue : {self.methode_semelles!r}.")

    # -- combinaisons --------------------------------------------------
    def elu(self, g, q):
        """Combinaison fondamentale ELU (BAEL 91 A.3.3,21) : 1,35 G + 1,5 Q."""
        return self.gamma_g_elu * g + self.gamma_q_elu * q

    def els(self, g, q):
        """Combinaison caractéristique ELS : G + Q."""
        return self.gamma_g_els * g + self.gamma_q_els * q

    @property
    def q_toiture_effective(self):
        return self.q_toiture_kn_m2 if self.q_toiture_kn_m2 is not None else self.q_kn_m2

    @property
    def contrainte_sol_effective(self):
        return self.contrainte_sol_kn_m2 if self.contrainte_sol_kn_m2 is not None else CONTRAINTE_SOL_DEFAUT

    # -- restitution ---------------------------------------------------
    def messages(self):
        """Hypothèses lisibles, à afficher à l'ingénieur et dans le DQE
        (texte destiné aussi au client : pas de symbole grec, décimales à virgule)."""
        def n(v):
            return f"{v:g}".replace(".", ",")
        m = []
        if self.origine_g == "forfait":
            m.append(
                f"HYPOTHÈSE : charge permanente des planchers G = {n(self.g_plancher_kn_m2)} kN/m² "
                f"(valeur par défaut validée : {CONTENU_G_FORFAITAIRE}). "
                f"Saisir la composition réelle du plancher si elle diffère."
            )
        elif self.origine_g == "couches":
            m.append(f"G = {n(self.g_plancher_kn_m2)} kN/m² calculée à partir de la composition du plancher saisie.")
        else:
            m.append(f"G = {n(self.g_plancher_kn_m2)} kN/m² saisie pour le projet.")
        if self.origine_q.startswith("usage"):
            m.append(f"Q = {n(self.q_kn_m2)} kN/m² : valeur normative de l'usage ({self.origine_q.split(':', 1)[-1]}).")
        if self.q_toiture_kn_m2 is None:
            m.append("Q de toiture prise égale à Q d'étage (usage de toiture non distingué).")
        else:
            m.append(f"Q de toiture = {n(self.q_toiture_kn_m2)} kN/m²"
                     + (" (valeur validée par le technicien BTP)." if self.origine_q_toiture == "valide_technicien"
                        else "."))
        m.append(
            "Poids propre des poutres et poteaux "
            + ("AJOUTÉ à G (b × h × 25 kN/m³)." if self.inclure_poids_propre_ossature
               else "NON ajouté : G doit déjà l'inclure.")
        )
        if self.origine_g == "forfait" and not self.inclure_poids_propre_ossature:
            m.append(
                "ALERTE : le forfait G des planchers ne couvre PAS le poids propre des poutres et poteaux "
                "(règle validée par le technicien BTP) -- activez son ajout, sinon les efforts sont sous-estimés."
            )
        m.append(
            "Semelles dimensionnées à l'"
            + ("ELU : surface ≥ effort ultime Nu / contrainte admissible du sol (méthode validée par le technicien BTP)."
               if self.methode_semelles == "ELU"
               else "ELS : surface ≥ effort de service Ns / contrainte admissible du sol (usage courant).")
        )
        if self.contrainte_sol_kn_m2 is None:
            m.append(
                f"HYPOTHÈSE : contrainte admissible du sol {CONTRAINTE_SOL_DEFAUT:.0f} kN/m² "
                f"(non renseignée -- à remplacer par l'étude géotechnique)."
            )
        return m

    def vers_dict(self):
        d = asdict(self)
        d["detail_g"] = list(self.detail_g)
        d["contrainte_sol_effective_kn_m2"] = self.contrainte_sol_effective
        return d


def resoudre_charge_permanente(g_saisie=None, couches=None):
    """(g_kn_m2, origine, detail). Priorité : couches > saisie > forfait."""
    if couches:
        res = calculer_charge_permanente_composee(1.0, couches)
        return res["charge_surfacique_totale_kn_m2"], "couches", tuple(res["detail"])
    if g_saisie is not None:
        if g_saisie <= 0:
            raise ValueError("La charge permanente saisie doit être strictement positive (kN/m²).")
        return float(g_saisie), "saisie", ()
    return G_PLANCHER_FORFAITAIRE_KN_M2, "forfait", ()


def hypotheses_par_defaut(charge_exploitation, taux_travail_sol=None):
    """Hypothèses historiques du moteur (G forfaitaire, pas de poids propre,
    semelles à l'ELU) -- utilisées quand l'appelant n'en fournit pas.
    Restent tracées comme telles dans chaque résultat."""
    return HypothesesCalcul(
        g_plancher_kn_m2=G_PLANCHER_FORFAITAIRE_KN_M2, origine_g="forfait",
        q_kn_m2=charge_exploitation, origine_q="saisie",
        contrainte_sol_kn_m2=taux_travail_sol,
    )
