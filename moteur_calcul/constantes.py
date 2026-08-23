"""
Constantes normatives utilisées par le moteur de calcul.

Source : document "reference_technique_BAEL_EC2_DQE" fourni par le
technicien BTP (référentiel BAEL 91 rév.99 par défaut, Eurocode 2 en
option -- voir MaterialStandard, à introduire si besoin de bascule
explicite entre les deux normes).

IMPORTANT : ces valeurs sont des valeurs par défaut / indicatives selon
le document reçu. Le taux de travail du sol reste une hypothèse par
défaut tant qu'aucune étude géotechnique réelle n'est fournie -- à
signaler clairement à l'ingénieur dans l'interface.
"""

# Norme de référence par défaut pour ce projet
NORME_PAR_DEFAUT = "BAEL91_MOD99"  # alternative : "EUROCODE2"

# Charges d'exploitation par usage du bâtiment, en kN/m²
# Source : document technicien BTP, section 2.2
CHARGES_EXPLOITATION = {
    "habitation": 1.5,
    "commerce": 5.0,
    "bureau": 2.5,
    "industriel": None,  # non fourni par le technicien -- à demander
    "balcon": 3.5,
    "circulation": 3.0,       # milieu de la fourchette 2.5-4.0 -- à confirmer
    "toiture_terrasse": 1.5,
    "toiture_inaccessible": 1.0,
}

# Poids volumique du béton armé, en kN/m³
POIDS_VOLUMIQUE_BETON = 25.0

# --- Charges permanentes composées (Phase 2, module 2) ---
#
# Un plancher réel n'est pas "une dalle béton" : il empile plusieurs
# couches (forme de pente, isolation, étanchéité, chape, revêtement,
# enduit sous face, cloisons...). Ce catalogue sert de valeurs par
# défaut pour l'interface de saisie et pour les tests.
#
# Deux façons de décrire une couche :
#   - "poids_volumique_kn_m3" : le poids dépend de l'épaisseur saisie
#   - "poids_surfacique_kn_m2" : poids déjà ramené au m² (épaisseur fixe
#     ou élément non homogène : étanchéité, faux plafond, cloisons)
#
# ATTENTION -- VALEURS COURANTES DE LA PRATIQUE, PAS ENCORE VALIDÉES
# par le technicien BTP (le document reçu ne donne que le béton armé).
# À faire confirmer avant utilisation en production.
POIDS_COUCHES_COURANTES = {
    "dalle_beton_arme":     {"poids_volumique_kn_m3": 25.0},
    "beton_maigre":         {"poids_volumique_kn_m3": 22.0},
    "forme_de_pente":       {"poids_volumique_kn_m3": 22.0},
    "chape_mortier":        {"poids_volumique_kn_m3": 20.0},
    "carrelage_colle":      {"poids_surfacique_kn_m2": 0.50},
    "etancheite_multicouche": {"poids_surfacique_kn_m2": 0.12},
    "isolation_polystyrene": {"poids_surfacique_kn_m2": 0.05},
    "enduit_sous_face":     {"poids_surfacique_kn_m2": 0.30},
    "faux_plafond":         {"poids_surfacique_kn_m2": 0.20},
    "cloisons_legeres":     {"poids_surfacique_kn_m2": 1.00},
}

# Résistance caractéristique du béton par défaut, en MPa (fc28 usage courant)
RESISTANCE_BETON_DEFAUT = 25.0

# Limite d'élasticité de l'acier, en MPa (Fe500 -- courant en Côte d'Ivoire)
LIMITE_ELASTIQUE_ACIER = 500.0

# Coefficients de sécurité BAEL (ELU)
GAMMA_BETON = 1.5   # gamma_b
GAMMA_ACIER = 1.15  # gamma_s

# Coefficients de combinaison d'actions (identiques BAEL / EC2 en cas courant)
COEFFICIENT_G_ELU = 1.35
COEFFICIENT_Q_ELU = 1.5
COEFFICIENT_G_ELS = 1.0
COEFFICIENT_Q_ELS = 1.0

# Moment réduit limite (frontière pivot A / pivot B), pour acier Fe500
# Source : document technicien BTP, section 3.2 -- ATTENTION, valeur
# différente d'un exemple précédent (0.372) qui était erroné/à ignorer.
MU_LIMITE_PIVOT_AB = 0.186

# Coefficient alpha simplifié pour pré-dimensionnement rapide des poteaux
# (élancement faible) -- section 3.1 du document
ALPHA_POTEAU_ELANCEMENT_FAIBLE = 0.85

# Coefficient de sécurité additionnel pour le pré-dimensionnement rapide
# des poteaux (fourchette 1.2 à 1.5 selon le document -- milieu par défaut)
COEFFICIENT_SECURITE_POTEAU_RAPIDE = 1.3

# Longueur de flambement (lf) rapportée à la hauteur libre (l0).
# Hypothèse par défaut : lf = l0 (poteau considéré articulé aux deux
# extrémités) -- la plus prudente sans information sur le degré
# d'encastrement réel. Si le technicien confirme un encastrement
# efficace par les planchers (cas courant en bâtiment courant
# multi-niveaux), 0.7 est une valeur usuelle à utiliser à la place.
LF_SUR_L0_DEFAUT = 1.0

# Élancement au-delà duquel ce pré-dimensionnement simplifié ne
# s'applique plus (BAEL : méthode forfaitaire valable jusqu'à lambda=70)
ELANCEMENT_MAX_METHODE_SIMPLIFIEE = 70

# Hypothèse sur le délai d'application de la majorité des charges,
# pour le coefficient de réduction alpha2 (méthode forfaitaire BAEL).
# Le document technicien (fichier Excel "Mon Métreur") prévoit 3 cas
# selon ce délai (>90j, 28-90j, <28j) -- on suppose ici le cas le plus
# courant en bâtiment (>90 jours, structure achevée avant mise en
# charge complète), donc alpha2 = alpha1 (pas de division supplémentaire).
# À ajuster si le technicien précise un cas différent pour un projet donné.
DELAI_APPLICATION_CHARGES_SUPPOSE = "superieur_90_jours"

# --- Dégression des charges d'exploitation (Phase 2, module 1) ---
#
# Loi de dégression NF P06-001 : sur un bâtiment à plusieurs niveaux,
# tous les étages ne sont pas à pleine charge d'exploitation en même
# temps ; la charge cumulée qui descend sur un appui est donc réduite
# au fur et à mesure qu'on descend.
#
#   Sous le niveau n (n = nombre d'étages chargés au-dessus, toiture
#   exclue) :   Q_cumulé = Q_toiture + coef(n) x (Q1 + ... + Qn)
#
#   coef(n) = valeur du tableau ci-dessous pour n <= 4
#   coef(n) = (3 + n) / (2 x n) pour n >= 5   (les deux se rejoignent
#             à n=5 : (3+5)/10 = 0,80)
#
# ATTENTION -- HYPOTHÈSE À CONFIRMER : ce sont les coefficients de la
# règle française. La feuille de route évoque une suite légèrement
# différente (1 / 0,9 / 0,8 / 0,7) pour la Côte d'Ivoire. Tant que le
# technicien BTP n'a pas tranché, on applique la règle française
# (documentée et plus prudente que 0,9/0,8/0,7). Pour basculer, il
# suffit de remplacer cette liste et la formule dans
# descente_charges.coefficient_degression().
COEFFICIENTS_DEGRESSION = [1.00, 0.95, 0.90, 0.85]  # n = 1, 2, 3, 4

# La dégression suppose des occupations indépendantes d'un niveau à
# l'autre. Elle ne s'applique PAS aux usages où tous les niveaux
# peuvent être chargés à fond simultanément (commerce, industrie), ni
# aux charges de toiture (jamais dégressées).
USAGES_AVEC_DEGRESSION = ("habitation", "bureau")

# Ratios de pré-dimensionnement rapide (poutres, dalles) -- section 3.2/3.3
RATIO_HAUTEUR_POUTRE_CONTINUE = (10, 12)     # portée / 10 à 12
RATIO_HAUTEUR_POUTRE_ISOSTATIQUE = (8, 10)   # portée / 8 à 10

# --- Méthode de Caquot (poutres continues, BAEL 91 mod.99 B.6.2) ---
#
# Coefficient du dénominateur de la formule des moments sur appuis
# intermédiaires (8,5 pour une poutre à section constante -- 8 x le
# coefficient 15/16 usuellement retenu en pratique bâtiment courant).
COEFFICIENT_CAQUOT = 8.5

# Coefficient de réduction des portées ("portées fictives") appliqué
# aux travées intermédiaires dans la méthode de Caquot MINORÉE -- ne
# s'applique QUE si la charge d'exploitation reste modérée par rapport
# à la charge permanente (Q <= 2G ou Q <= 5 kN/m², BAEL B.6.2,1). Les
# travées de rive gardent leur portée réelle dans tous les cas.
# Si cette condition n'est pas vérifiée, il faut appeler la méthode en
# minore=False (portées réelles partout -- plus défavorable, plus sûr).
COEFFICIENT_REDUCTION_CAQUOT_MINORE = 0.8
RATIO_EPAISSEUR_DALLE_1_SENS = (25, 30)       # portée / 25 à 30
RATIO_EPAISSEUR_DALLE_2_SENS = (35, 40)       # portée / 35 à 40
EPAISSEUR_DALLE_MIN_CM = 12
EPAISSEUR_DALLE_MAX_COURANTE_CM = 16

# Contrainte admissible du sol par défaut, en kN/m² -- HYPOTHÈSE PAR
# DÉFAUT, à remplacer impérativement par une étude géotechnique réelle.
CONTRAINTE_SOL_DEFAUT_MIN = 150.0
CONTRAINTE_SOL_DEFAUT_MAX = 200.0
CONTRAINTE_SOL_DEFAUT = 180.0  # valeur milieu utilisée si non renseignée

# Minima constructifs des semelles (pratique courante, pas une exigence
# de calcul : une semelle plus étroite/plate que ça n'est pas réalisable
# proprement sur chantier).
LARGEUR_MIN_SEMELLE_FILANTE_CM = 40
HAUTEUR_MIN_SEMELLE_CM = 20
ENROBAGE_SEMELLE_CM = 5  # aciers coulés contre le sol / béton de propreté

# Largeur au-delà de laquelle une semelle filante n'a plus de sens
# constructif : à ce stade les semelles se rejoignent et c'est un
# radier général qu'il faut étudier, pas une semelle continue.
LARGEUR_MAX_SEMELLE_FILANTE_CM = 300

# Ratios d'acier par volume de béton (kg/m³), estimation simplifiée
# pour le MVP avant calcul détaillé du ferraillage -- section 5.2
RATIO_ACIER_SEMELLES_KG_M3 = (40, 60)
RATIO_ACIER_POTEAUX_KG_M3 = (100, 150)
RATIO_ACIER_POUTRES_KG_M3 = (120, 180)
RATIO_ACIER_DALLES_KG_M3 = (70, 100)

# Densité de l'acier (pour convertir une section théorique en poids réel)
DENSITE_ACIER_KG_M3 = 7850.0

# Coefficient gamma (Mu/Mser) supposé quand le moment de service n'est
# pas fourni séparément (notre moteur ne prend actuellement qu'une
# charge linéaire déjà pondérée ELU, pas G et Q séparés). 1,45 est une
# valeur médiane raisonnable entre 1,35 (G seul) et 1,5 (Q dominant) --
# à remplacer par un vrai calcul si G et Q sont un jour fournis
# séparément à dimensionner_poutre().
GAMMA_ELU_ELS_SUPPOSE = 1.45

# Bornes réalistes pour la validation des entrées
PORTEE_MIN_M = 1.0
PORTEE_MAX_M = 15.0
NB_NIVEAUX_MAX = 20

USAGES_VALIDES = list(CHARGES_EXPLOITATION.keys())

# --- Ratios "postes sans formule dédiée" (Phase 2/3, feuille de route
# "Ma partie — Backend", Jour 1, §1.1) -----------------------------------
#
# Ces postes du DQE type CIMBAT (maçonnerie, enduit, chaînage, raidisseur,
# acrotère) n'ont pas de dimensionnement structurel dédié dans le moteur
# -- ce sont des quantités déduites de la géométrie générale du bâtiment
# (périmètre, hauteurs, nombre de niveaux), pas d'un calcul de résistance.
#
# ATTENTION -- POINT CRITIQUE (à valider avec le technicien BTP avant
# utilisation en production, cf. feuille de route) : ces valeurs sont
# pour l'instant DÉDUITES DU SEUL EXEMPLE DISPONIBLE (DQE CIMBAT, Villa
# basse 4 pièces, devis n°0017-2026), pas d'un référentiel validé. Elles
# sont cohérentes à ±10% entre les différents postes "linéaires légers"
# du même devis (chaînages, bêches, renforts, linteaux, acrotère : tous
# à 90 kg/m³ d'acier et ~10 m²/m³ de coffrage), ce qui est un bon signe,
# mais UN SEUL exemple ne suffit pas à les figer.

# Épaisseur standard d'un mur en agglomérés de 15 (parpaing 15 cm), en m.
EPAISSEUR_AGGLOS_15_M = 0.15
EPAISSEUR_AGGLOS_10_M = 0.10

# Coefficient de plein (1 - proportion d'ouvertures : portes, fenêtres) à
# appliquer à la surface brute de mur pour la maçonnerie d'élévation.
# 0.80 = hypothèse courante en habitation (à ajuster selon le plan réel).
COEFFICIENT_PLEIN_MACONNERIE_ELEVATION = 0.80

# Ratios acier / béton (kg/m³), déduits du DQE CIMBAT -- voir avertissement
# ci-dessus. Les éléments "linéaires légers" (chaînages, linteaux, bêches,
# renforts de dallage, acrotère) sont tous à 90 kg/m³ dans l'exemple ; les
# éléments "verticaux/compression" (amorces de poteaux, raidisseurs) à
# 150 kg/m³, cohérent avec RATIO_ACIER_POTEAUX_KG_M3 déjà utilisé ailleurs.
RATIO_ACIER_ELEMENT_LINEAIRE_LEGER_KG_M3 = 90.0
RATIO_ACIER_RAIDISSEUR_AMORCE_KG_M3 = 150.0

# Ratios coffrage / béton (m²/m³), même source.
RATIO_COFFRAGE_ELEMENT_LINEAIRE_LEGER_M2_M3 = 10.0
RATIO_COFFRAGE_ACROTERE_M2_M3 = 15.0

# Sections forfaitaires (m²) des éléments linéaires légers, pratique
# courante en petit bâtiment (à confirmer avec le technicien) : ex.
# chaînage 15x20 cm = 0.03 m².
SECTION_CHAINAGE_M2 = 0.03
SECTION_ACROTERE_M2 = 0.05  # acrotère un peu plus large (15x33 environ)

# AJOUTÉ (Phase C) : dimensions par défaut du chaînage (15x20 cm),
# cohérentes avec SECTION_CHAINAGE_M2 ci-dessus (0.15 x 0.20 = 0.03 m²)
# -- utilisées par dimensionner_chainage() (postes_ratio.py) pour un
# chaînage identifié individuellement (repère CH1), par opposition au
# poste ratio global (calculer_poste_ratio("chainage", ...)) qui ne
# manipule que la section totale sans la décomposer.
LARGEUR_CHAINAGE_CM_DEFAUT = 15.0
HAUTEUR_CHAINAGE_CM_DEFAUT = 20.0

# Ratio d'enduit : un raidisseur ou une amorce de poteau par façade/angle
# structurel, en l'absence d'un vrai plan de ferraillage -- hypothèse
# grossière tant que le plan réel n'est pas disponible.
ENDUIT_EPAISSEUR_FORFAITAIRE = "dosé à 350 kg/m³"  # libellé DQE, pas un ratio numérique

# --- Compléments du plan de coffrage (Phase C -- voir
# Feuille_de_route_Import_Plan_Automatique.md, §"3. Feuille de route par
# développeur / Genius / Phase C") : dallage et joints de dilatation,
# calculés géométriquement depuis l'emprise des semelles/poteaux. Voir
# moteur_calcul/formules/complements_plan_coffrage.py.

# Distance maximale entre joints de dilatation pour une structure en
# béton armé courante, SANS disposition particulière (armatures de
# retrait, joints de rupture partiels, etc.) -- pratique usuelle
# France/Afrique de l'Ouest (cf. DTU 20.1 pour la maçonnerie chaînée et
# usage courant BTP pour le béton armé, ~25 m). Valeur PAR DÉFAUT et
# conservatrice pour un pré-dimensionnement automatique ; une étude
# structurelle réelle peut justifier de s'en écarter (joints de rupture
# structurelle, dilatation thermique différente selon climat/exposition).
DISTANCE_MAX_JOINT_DILATATION_M = 25.0

# Débord du dallage (dalle sur terre-plein / hérisson) au-delà de
# l'emprise extérieure des semelles -- pratique constructive courante
# pour couvrir la totalité du bâtiment y compris les débords de
# soubassement, avant application d'un enduit/plinthe. Valeur forfaitaire
# à ajuster selon le plan réel si le débord architectural diffère.
MARGE_DALLAGE_M = 0.20