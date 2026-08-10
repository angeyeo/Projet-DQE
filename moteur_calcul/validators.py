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