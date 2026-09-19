import logging
from typing import Optional
from ...models import JournalAppelIA

logger = logging.getLogger(__name__)


def enregistrer_appel_ia(
    endpoint: str,
    source: str,
    utilisateur=None,
    duree_ms: Optional[int] = None,
) -> Optional[JournalAppelIA]:
    """
    Enregistre un appel IA dans le modèle JournalAppelIA.

    Exigence de sécurité :
    Cette fonction est strictement défensive. Tout échec (erreur DB, utilisateur invalide,
    champ manquant) est capturé et logué sans jamais lever d'exception ni perturber
    l'exécution de la requête IA.

    Args:
        endpoint: Le chemin canonique de l'endpoint (ex: '/api/assistant/structurer-projet/')
        source: La source réelle de la réponse ('GEMINI', 'MOCK', 'FALLBACK_LOCAL')
        utilisateur: L'utilisateur Django (request.user) ou None
        duree_ms: La durée de l'exécution en millisecondes (optionnel)

    Returns:
        L'instance de JournalAppelIA créée ou None en cas d'erreur.
    """
    try:
        user_obj = None
        if utilisateur and getattr(utilisateur, "is_authenticated", False):
            user_obj = utilisateur

        valides_sources = set(JournalAppelIA.Source.values)
        if source not in valides_sources:
            logger.warning(
                "Source IA inconnue '%s' pour l'endpoint '%s', fallback vers FALLBACK_LOCAL",
                source,
                endpoint,
            )
            source = JournalAppelIA.Source.FALLBACK_LOCAL

        return JournalAppelIA.objects.create(
            utilisateur=user_obj,
            endpoint=endpoint,
            source=source,
            duree_ms=duree_ms,
        )
    except Exception as exc:
        logger.exception("Erreur lors de la journalisation de l'appel IA: %s", exc)
        return None
