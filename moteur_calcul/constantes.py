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

# Ratios de pré-dimensionnement rapide (poutres, dalles) -- section 3.2/3.3
RATIO_HAUTEUR_POUTRE_CONTINUE = (10, 12)     # portée / 10 à 12
RATIO_HAUTEUR_POUTRE_ISOSTATIQUE = (8, 10)   # portée / 8 à 10
RATIO_EPAISSEUR_DALLE_1_SENS = (25, 30)       # portée / 25 à 30
RATIO_EPAISSEUR_DALLE_2_SENS = (35, 40)       # portée / 35 à 40
EPAISSEUR_DALLE_MIN_CM = 12
EPAISSEUR_DALLE_MAX_COURANTE_CM = 16

# Contrainte admissible du sol par défaut, en kN/m² -- HYPOTHÈSE PAR
# DÉFAUT, à remplacer impérativement par une étude géotechnique réelle.
CONTRAINTE_SOL_DEFAUT_MIN = 150.0
CONTRAINTE_SOL_DEFAUT_MAX = 200.0
CONTRAINTE_SOL_DEFAUT = 180.0  # valeur milieu utilisée si non renseignée

# Ratios d'acier par volume de béton (kg/m³), estimation simplifiée
# pour le MVP avant calcul détaillé du ferraillage -- section 5.2
RATIO_ACIER_SEMELLES_KG_M3 = (40, 60)
RATIO_ACIER_POTEAUX_KG_M3 = (100, 150)
RATIO_ACIER_POUTRES_KG_M3 = (120, 180)
RATIO_ACIER_DALLES_KG_M3 = (70, 100)

# Bornes réalistes pour la validation des entrées
PORTEE_MIN_M = 1.0
PORTEE_MAX_M = 15.0
NB_NIVEAUX_MAX = 20

USAGES_VALIDES = list(CHARGES_EXPLOITATION.keys())