"""
Conversion DWG -> DXF côté serveur (issue #95), par l'outil en ligne de
commande `dwg2dxf` de GNU LibreDWG.

Choix de l'outil (étude du 22/10/2026, détail dans l'issue #95) :
  - GNU LibreDWG : licence GPL v3, lit les DWG de R13 à 2018 (le format
    2018 est celui des versions récentes d'AutoCAD). Appelé comme
    PROGRAMME SÉPARÉ (sous-processus), il n'est ni lié ni distribué avec
    le logiciel DQE.
  - ODA File Converter : gratuit, mais réservé aux usages NON
    commerciaux pour les non-membres de l'Open Design Alliance : écarté.

Le convertisseur est OPTIONNEL : s'il n'est pas installé sur le serveur,
le DWG est refusé avec un message qui explique comment exporter en DXF.
Aucune conversion approximative n'est tentée à sa place.

Sécurité : un DWG reçu est une donnée non fiable et LibreDWG est une
bibliothèque C (plusieurs failles corrigées ces dernières années). La
conversion tourne donc dans un processus séparé, sans shell, dans un
dossier temporaire, avec un délai et une mémoire limités.
"""

import os
import shutil
import subprocess
import tempfile

from django.conf import settings

DELAI_CONVERSION_S = 60
MEMOIRE_MAX_OCTETS = 1024 * 1024 * 1024  # 1 Gio


class ConversionDWGImpossible(Exception):
    """Conversion refusée ou échouée : le message est destiné à l'utilisateur."""


def chemin_convertisseur():
    """Chemin de dwg2dxf, ou None s'il n'est pas installé.
    Réglage DWG2DXF_PATH (variable d'environnement) prioritaire."""
    configure = getattr(settings, "DWG2DXF_PATH", "") or ""
    if configure:
        return configure if os.path.isfile(configure) and os.access(configure, os.X_OK) else None
    return shutil.which("dwg2dxf")


def convertisseur_disponible():
    return chemin_convertisseur() is not None


def _limiter_ressources():  # pragma: no cover - exécuté dans le processus enfant
    import resource

    resource.setrlimit(resource.RLIMIT_AS, (MEMOIRE_MAX_OCTETS, MEMOIRE_MAX_OCTETS))
    resource.setrlimit(resource.RLIMIT_CPU, (DELAI_CONVERSION_S, DELAI_CONVERSION_S + 5))


def convertir_dwg_en_dxf(contenu_dwg):
    """Convertit le contenu binaire d'un DWG ; renvoie le contenu du DXF.

    Lève ConversionDWGImpossible (convertisseur absent, fichier illisible,
    délai dépassé). Le DXF obtenu est ensuite lu par le lecteur DXF
    existant, qui applique ses propres contrôles (unités, poteaux...).
    """
    executable = chemin_convertisseur()
    if executable is None:
        raise ConversionDWGImpossible(MESSAGE_DWG_NON_DISPONIBLE)
    with tempfile.TemporaryDirectory(prefix="dqe-dwg-") as dossier:
        source = os.path.join(dossier, "plan.dwg")
        cible = os.path.join(dossier, "plan.dxf")
        with open(source, "wb") as f:
            f.write(contenu_dwg)
        try:
            resultat = subprocess.run(
                [executable, "-y", "-o", cible, source],
                cwd=dossier, capture_output=True, timeout=DELAI_CONVERSION_S,
                preexec_fn=_limiter_ressources if os.name == "posix" else None,
                env={"PATH": "/usr/bin:/bin", "LANG": "C"},
            )
        except subprocess.TimeoutExpired:
            raise ConversionDWGImpossible(
                f"La conversion du DWG a dépassé {DELAI_CONVERSION_S} s. Enregistrez le plan au format DXF "
                "depuis AutoCAD et déposez le DXF.") from None
        except OSError as exc:
            raise ConversionDWGImpossible(f"Le convertisseur DWG n'a pas pu être lancé ({exc}).") from None
        if not os.path.isfile(cible) or os.path.getsize(cible) == 0:
            # dwg2dxf renvoie parfois un code non nul sur des avertissements
            # tout en produisant un DXF complet : seul un fichier absent ou
            # vide est un échec.
            raise ConversionDWGImpossible(
                "Ce fichier DWG n'a pas pu être converti (fichier endommagé, protégé ou version non prise en "
                "charge). Enregistrez le plan au format DXF depuis AutoCAD et déposez le DXF. "
                f"(code {resultat.returncode})")
        with open(cible, "rb") as f:
            return f.read()


MESSAGE_DWG_NON_DISPONIBLE = (
    "Les fichiers DWG ne sont pas lus sur ce serveur. Dans AutoCAD : Fichier > Enregistrer sous, "
    "type « AutoCAD 2018 DXF (*.dxf) », puis déposez le DXF."
)
