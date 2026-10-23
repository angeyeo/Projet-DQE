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
    G_TOITURE_CHARPENTE_KN_M2,
    TYPES_TOITURE,
    COEFFICIENT_G_ELU,
    COEFFICIENT_Q_ELS,
    COEFFICIENT_Q_ELU,
    CONTRAINTE_SOL_DEFAUT,
    POIDS_MURS_MAX_KN_M2,
    POURCENTAGE_BAIES_MAX,
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
    # Toiture du dernier niveau : "dalle" (G = G planchers, comportement
    # historique) ou "charpente" (G = g_toiture_kn_m2, aucun plancher au
    # dernier niveau).
    type_toiture: str = "dalle"
    g_toiture_kn_m2: float | None = None
    contrainte_sol_kn_m2: float | None = None
    # Murs en maçonnerie posés sur les poutres (façades, refends). None =
    # poids non renseigné : charge NON comptée et ALERTE affichée. Les
    # cloisons légères restent comprises dans G des planchers.
    poids_murs_kn_m2: float | None = None
    origine_poids_murs: str | None = None
    # Un mur n'est compté que LÀ OÙ IL EXISTE (ingénieur BTP, 12/10/2026) :
    # tronçons de poutre désignés sur le plan des murs (clés de
    # trame.cle_segment). RDC : murs sur les longrines ; étages : murs sur
    # les poutres du plancher situé dessous (même plan à chaque étage).
    murs_rdc: frozenset = frozenset()
    murs_etages: frozenset = frozenset()
    # Issue #81 : plans propres aux étages R+2 et plus, ((2, frozenset), ...).
    # Un étage absent reprend murs_etages (plan du R+1).
    murs_etages_specifiques: tuple = ()
    # Part des baies (portes, fenêtres) déduite de la surface des murs, en %.
    # 0 = aucune baie déduite (prudent).
    pourcentage_baies_murs: float = 0.0
    # Murs du RDC posés sur les longrines, qui reportent leur charge sur
    # les semelles (validé par l'ingénieur BTP, 12/10/2026).
    murs_rdc_sur_semelles: bool = True
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
        if self.type_toiture not in TYPES_TOITURE:
            raise ValueError(f"Type de toiture inconnu : {self.type_toiture!r} (dalle ou charpente).")
        if self.type_toiture == "charpente" and (self.g_toiture_kn_m2 is None or self.g_toiture_kn_m2 <= 0):
            raise ValueError("Toiture en charpente : la charge permanente de toiture doit être strictement positive (kN/m²).")
        if self.poids_murs_kn_m2 is not None and not (0 < self.poids_murs_kn_m2 <= POIDS_MURS_MAX_KN_M2):
            raise ValueError(
                f"Le poids des murs doit être compris entre 0 et {POIDS_MURS_MAX_KN_M2:g} kN/m² de mur "
                f"(valeur reçue : {self.poids_murs_kn_m2})."
            )
        if not (0 <= self.pourcentage_baies_murs <= POURCENTAGE_BAIES_MAX):
            raise ValueError(f"La part des baies doit être comprise entre 0 et {POURCENTAGE_BAIES_MAX:g} %.")
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
    def g_toiture_effective(self):
        """G du dernier niveau (kN/m²) : celle des planchers pour une dalle."""
        return self.g_toiture_kn_m2 if self.type_toiture == "charpente" else self.g_plancher_kn_m2

    @property
    def murs_comptes(self):
        return self.poids_murs_kn_m2 is not None and bool(self.murs_rdc or self.tous_murs_etages)

    def murs_etage(self, k):
        """Tronçons portant un mur à l'étage R+k (k ≥ 1)."""
        return dict(self.murs_etages_specifiques).get(k, self.murs_etages)

    @property
    def tous_murs_etages(self):
        """Tronçons portant un mur à AU MOINS un étage."""
        return self.murs_etages.union(*(m for _, m in self.murs_etages_specifiques))

    def mur_sur(self, cle, niveau):
        """True si un mur est placé sur ce tronçon et compté. niveau : "rdc",
        "etages" (à au moins un étage) ou k (entier, étage R+k)."""
        if self.poids_murs_kn_m2 is None or cle is None:
            return False
        if niveau == "rdc":
            return cle in self.murs_rdc
        if niveau == "etages":
            return cle in self.tous_murs_etages
        return cle in self.murs_etage(niveau)

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
        if self.type_toiture == "charpente":
            m.append(f"Toiture en charpente : G = {n(self.g_toiture_kn_m2)} kN/m² (charpente + couverture, "
                     f"valeur donnée par l'ingénieur BTP) ; pas de plancher au dernier niveau.")
        else:
            m.append("Toiture-terrasse en dalle : même G que les planchers.")
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
        places = len(self.murs_rdc) + len(self.tous_murs_etages)
        if self.poids_murs_kn_m2 is None:
            m.append(
                "ALERTE : poids des murs non renseigné -- la charge des murs en maçonnerie n'est PAS comptée : "
                "efforts des poteaux, poutres et semelles sous-estimés. Renseignez le poids des murs "
                "(kN/m² de mur, enduits compris)"
                + (f" ; {places} tronçon(s) de mur placé(s) en attente." if places else
                   ", puis placez les murs sur le plan des murs.")
            )
        elif not places:
            m.append(
                "ALERTE : aucun mur placé sur le plan des murs -- la charge des murs n'est PAS comptée. Placez les "
                "murs de façade et de séparation qui figurent au plan architectural."
            )
        else:
            m.append(
                f"Murs en maçonnerie : {n(self.poids_murs_kn_m2)} kN/m² de mur (enduits compris), comptés "
                f"seulement là où ils existent : {len(self.murs_etages)} tronçon(s) aux étages"
                + (" (plan du R+1 ; plans propres : " + ", ".join(
                    f"R+{k} {len(t)} tronçon(s)" for k, t in self.murs_etages_specifiques) + ")"
                   if self.murs_etages_specifiques else "")
                + f", {len(self.murs_rdc)} au rez-de-chaussée (plan des murs). Hauteur du mur = hauteur d'étage − "
                f"hauteur de la poutre. Les cloisons légères restent comprises dans G des planchers."
            )
            m.append(
                f"Baies déduites : {n(self.pourcentage_baies_murs)} % de la surface des murs."
                if self.pourcentage_baies_murs else
                "Aucune baie déduite de la surface des murs (prudent) : renseignez la part des baies si elle est connue."
            )
            if self.murs_rdc:
                m.append(
                    "Murs du rez-de-chaussée posés sur les longrines, qui reportent leur charge sur les semelles "
                    "(validé par l'ingénieur BTP le 12/10/2026)."
                    if self.murs_rdc_sur_semelles else
                    "Murs du rez-de-chaussée sur leur propre fondation : leur charge n'est pas ajoutée aux semelles."
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
        # Le plan des murs n'est pas recopié dans chaque élément : seul le
        # nombre de tronçons l'est (le détail vit sur le projet).
        d["murs_rdc"] = len(self.murs_rdc)
        d["murs_etages"] = len(self.murs_etages)
        d["murs_etages_specifiques"] = {str(k): len(m) for k, m in self.murs_etages_specifiques}
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
