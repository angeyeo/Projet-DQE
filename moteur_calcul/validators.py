"""
Validation des entrées utilisateur avant tout calcul.
Objectif : rejeter tôt les valeurs incohérentes plutôt que de laisser
une formule produire un résultat absurde silencieusement.
"""

from .constantes import (
    USAGES_VALIDES,
    PORTEE_MIN_M,
    PORTEE_MAX_M,
    NB_NIVEAUX_MAX,
)


class EntreeInvalide(ValueError):
    """Levée quand une entrée utilisateur est hors des bornes attendues."""


def valider_portee(portee):
    if portee is None or portee <= 0:
        raise EntreeInvalide("La portée doit être un nombre positif.")
    if not (PORTEE_MIN_M <= portee <= PORTEE_MAX_M):
        raise EntreeInvalide(
            f"La portée doit être comprise entre {PORTEE_MIN_M} m et {PORTEE_MAX_M} m."
        )
    return portee


def valider_usage_batiment(usage):
    if usage not in USAGES_VALIDES:
        raise EntreeInvalide(
            f"Usage inconnu : '{usage}'. Valeurs acceptées : {USAGES_VALIDES}."
        )
    return usage


def valider_nb_niveaux(nb_niveaux):
    if nb_niveaux is None or nb_niveaux <= 0:
        raise EntreeInvalide("Le nombre de niveaux doit être un entier positif.")
    if nb_niveaux > NB_NIVEAUX_MAX:
        raise EntreeInvalide(f"Le nombre de niveaux dépasse la limite gérée ({NB_NIVEAUX_MAX}).")
    return nb_niveaux


def valider_surface(surface):
    if surface is None or surface <= 0:
        raise EntreeInvalide("La surface doit être un nombre positif.")
    return surface

# Plage plausible d'une contrainte admissible de sol, en kN/m² : de
# ~0,25 bar (sol très médiocre) à 20 bar (rocher sain). Sert surtout à
# détecter une ERREUR D'UNITÉ (0.2 saisi en MPa au lieu de 200 kN/m²,
# soit un facteur 1000 sur la surface de la semelle).
CONTRAINTE_SOL_MIN_KN_M2 = 25.0
CONTRAINTE_SOL_MAX_KN_M2 = 2000.0


def valider_contrainte_sol_kn_m2(valeur):
    """None autorisé (= hypothèse par défaut du moteur, signalée)."""
    if valeur is None:
        return None
    if valeur <= 0:
        raise EntreeInvalide("La contrainte admissible du sol doit être positive (kN/m²).")
    if valeur < CONTRAINTE_SOL_MIN_KN_M2:
        raise EntreeInvalide(
            f"Contrainte du sol = {valeur} kN/m² : valeur trop faible, probablement "
            f"saisie en MPa ou en bar. Le moteur attend des kN/m² "
            f"(0,2 MPa = 2 bar = 200 kN/m²)."
        )
    if valeur > CONTRAINTE_SOL_MAX_KN_M2:
        raise EntreeInvalide(
            f"Contrainte du sol = {valeur} kN/m² : valeur hors plage plausible "
            f"(max {CONTRAINTE_SOL_MAX_KN_M2:.0f} kN/m²). Vérifiez l'unité."
        )
    return valeur
