"""
Constantes normatives utilisées par le moteur de calcul.

IMPORTANT : les valeurs à None doivent être remplies avec les formules/valeurs
fournies par le technicien BTP. Ne jamais deviner une valeur normative --
laisser None tant que la vraie valeur n'est pas confirmée, pour éviter
qu'un test passe silencieusement avec une valeur inventée.

Norme retenue pour ce projet : ______ (BAEL 91 rév.99 / Eurocode 2 -- à trancher
avec le technicien BTP et à noter ici une fois décidé).
"""

# Charges d'exploitation par usage du bâtiment, en kN/m²
# Source : à compléter (ex. NF EN 1991-1-1 / BAEL, tableau des charges d'exploitation)
CHARGES_EXPLOITATION = {
    "habitation": None,
    "commerce": None,
    "bureau": None,
    "industriel": None,
}

# Poids volumique du béton armé, en kN/m³
POIDS_VOLUMIQUE_BETON = None

# Résistance caractéristique du béton par défaut, en MPa (ex. fc28)
RESISTANCE_BETON_DEFAUT = None

# Limite d'élasticité de l'acier, en MPa (ex. fe pour BAEL, fyk pour Eurocode)
LIMITE_ELASTIQUE_ACIER = None

# Coefficient de sécurité global (à préciser : ELU, ELS, ou les deux séparément)
COEFFICIENT_SECURITE = None

# Bornes réalistes pour la validation des entrées (à confirmer avec le technicien)
PORTEE_MIN_M = 1.0
PORTEE_MAX_M = 15.0
NB_NIVEAUX_MAX = 20

USAGES_VALIDES = list(CHARGES_EXPLOITATION.keys())