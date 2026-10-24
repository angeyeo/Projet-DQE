"""Version du moteur de calcul, imprimée sur la note de calcul (issue #96).

À INCRÉMENTER à chaque changement d'une formule, d'une constante ou d'une
règle de calcul (date du changement + lettre si plusieurs le même jour),
pour qu'une note imprimée dise avec quelles règles elle a été produite.

Historique :
  2026.10.23 -- note de calcul ; ratios d'acier B4, charpente B14 et
                dégression B9 validés (21/10/2026).
"""

import os

VERSION_MOTEUR = "2026.10.23"
NORME = "BAEL 91 modifié 99"


def identifiant_version():
    """« 2026.10.23 », complété du commit déployé quand la variable GIT_COMMIT
    est fournie. Rien n'est inventé si elle est absente."""
    commit = (os.getenv("GIT_COMMIT") or "").strip()
    return f"{VERSION_MOTEUR} ({commit[:7]})" if commit else VERSION_MOTEUR
