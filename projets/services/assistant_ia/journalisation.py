import logging
from typing import Optional

from ...models import JournalAppelIA


logger = logging.getLogger(__name__)


def enregistrer_appel_ia(
    endpoint: str,
    source: str,
    utilisateur=None,
    duree_ms: Optional[int] = None,
    modele: Optional[str] = None,
    tokens_entree: Optional[int] = None,
    tokens_sortie: Optional[int] = None,
    tokens_reflexion: Optional[int] = None,
    tokens_total: Optional[int] = None,
) -> Optional[JournalAppelIA]:
    """
    Enregistre un appel IA dans le modèle JournalAppelIA.

    Cette fonction est défensive :
    toute erreur de journalisation est capturée et ne doit jamais
    empêcher le fonctionnement normal de l'appel IA.
    """

    try:
        try:
            from .client import pop_last_usage
            usage = pop_last_usage() or {}
        except Exception:
            usage = {}

        modele = modele if modele is not None else usage.get("modele")

        tokens_entree = (
            tokens_entree
            if tokens_entree is not None
            else usage.get("tokens_entree")
        )

        tokens_sortie = (
            tokens_sortie
            if tokens_sortie is not None
            else usage.get("tokens_sortie")
        )

        tokens_reflexion = (
            tokens_reflexion
            if tokens_reflexion is not None
            else usage.get("tokens_reflexion")
        )

        tokens_total = (
            tokens_total
            if tokens_total is not None
            else usage.get("tokens_total")
        )

        user_obj = None

        if utilisateur and getattr(utilisateur, "is_authenticated", False):
            user_obj = utilisateur

        valides_sources = set(JournalAppelIA.Source.values)

        if source not in valides_sources:
            logger.warning(
                "Source IA inconnue '%s' pour l'endpoint '%s', "
                "fallback vers FALLBACK_LOCAL",
                source,
                endpoint,
            )
            source = JournalAppelIA.Source.FALLBACK_LOCAL

        return JournalAppelIA.objects.create(
            utilisateur=user_obj,
            endpoint=endpoint,
            source=source,
            duree_ms=duree_ms,
            modele=modele,
            tokens_entree=tokens_entree,
            tokens_sortie=tokens_sortie,
            tokens_reflexion=tokens_reflexion,
            tokens_total=tokens_total,
        )

    except Exception as exc:
        logger.exception(
            "Erreur lors de la journalisation de l'appel IA: %s",
            exc,
        )
        return None