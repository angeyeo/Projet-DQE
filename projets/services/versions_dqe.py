"""
Historique et comparaison des versions d'un DQE (issue #82).

Une version est enregistrée quand le DQE généré DIFFÈRE de la dernière
version du projet (empreinte). Son contenu est figé (modèle VersionDQE).

COMPARAISON poste par poste
---------------------------
Clé d'un poste : (lot, désignation, unité). Si plusieurs lignes ont la même
clé dans une version (deux postes saisis identiques), elles sont regroupées :
quantités et montants additionnés, prix unitaire = montant / quantité.

Pour chaque poste présent dans les deux versions, l'écart de montant est
décomposé en effets (méthode des écarts, exacte au FCFA près) :

    ΔM = M2 − M1
    effet quantité = (q2 − q1) × pu1
    effet prix     = q2 × (pu2 − pu1)
    arrondi        = ΔM − effet quantité − effet prix

(q × pu n'est égal au montant qu'à l'arrondi au FCFA près ; le reliquat
d'arrondi est affiché à part, jamais réparti en silence.)

Un poste absent d'une version est « ajouté » ou « supprimé » : son montant
entier est l'écart.
"""

import hashlib
import json
from decimal import ROUND_HALF_UP, Decimal

from django.db import transaction

from moteur_calcul.version import identifiant_version

from ..models import Projet, VersionDQE

# Ce qui définit le CONTENU d'un DQE (dates d'édition et auteur exclus).
CLES_EMPREINTE = ("lignes", "total_general", "finances", "hypotheses", "hypotheses_projet")


def empreinte(dqe_data):
    contenu = {k: dqe_data.get(k) for k in CLES_EMPREINTE}
    brut = json.dumps(contenu, sort_keys=True, ensure_ascii=False, default=str)
    return hashlib.sha256(brut.encode("utf-8")).hexdigest()


def _nom(utilisateur):
    if utilisateur is None or not getattr(utilisateur, "is_authenticated", False):
        return ""
    return (utilisateur.get_full_name() or utilisateur.get_username() or "")[:150]


def enregistrer_version(projet, dqe_data, utilisateur=None):
    """Renvoie (version, creee). Une nouvelle version n'est créée que si le
    contenu diffère de la dernière ; sinon la dernière est renvoyée."""
    signature = empreinte(dqe_data)
    with transaction.atomic():
        # Verrou sur le projet : deux générations simultanées ne prennent
        # jamais le même numéro.
        Projet.objects.select_for_update().filter(pk=projet.pk).first()
        derniere = VersionDQE.objects.filter(projet=projet).order_by("-numero").first()
        if derniere is not None and derniere.empreinte == signature:
            return derniere, False
        version = VersionDQE.objects.create(
            projet=projet,
            numero=(derniere.numero + 1) if derniere else 1,
            auteur=utilisateur if getattr(utilisateur, "is_authenticated", False) else None,
            auteur_nom=_nom(utilisateur),
            total_general=dqe_data["total_general"],
            nb_lignes=len(dqe_data.get("lignes", [])),
            version_moteur=identifiant_version()[:40],
            empreinte=signature,
            donnees=dqe_data,
        )
    return version, True


def resume_version(v):
    return {"numero": v.numero, "date": v.date.isoformat(), "auteur": v.auteur_nom or None,
            "total_general": v.total_general, "nb_lignes": v.nb_lignes, "version_moteur": v.version_moteur}


# ---------------------------------------------------------------------------
# Comparaison
# ---------------------------------------------------------------------------

def _d(v):
    return Decimal(str(v or 0))


def _entier(v: Decimal) -> int:
    return int(v.quantize(Decimal("1"), rounding=ROUND_HALF_UP))


def _postes(dqe_data):
    """{clé: poste regroupé} dans l'ordre d'apparition."""
    postes = {}
    for l in dqe_data.get("lignes", []):
        cle = (l.get("lot") or "", (l.get("designation") or "").strip(), l.get("unite") or "")
        p = postes.get(cle)
        if p is None:
            p = postes[cle] = {"lot": cle[0], "designation": cle[1], "unite": cle[2], "quantite": Decimal("0"),
                               "montant": 0, "nb_lignes": 0}
        p["quantite"] += _d(l.get("quantite"))
        p["montant"] += int(l.get("montant") or 0)
        p["nb_lignes"] += 1
    for p in postes.values():
        p["prix_unitaire"] = (Decimal(p["montant"]) / p["quantite"]) if p["quantite"] else None
    return postes


def _num(v, places=3):
    if v is None:
        return None
    return float(v.quantize(Decimal(1).scaleb(-places), rounding=ROUND_HALF_UP))


def comparer(donnees_avant, donnees_apres):
    """Comparaison poste par poste de deux contenus de DQE (avant → après)."""
    a, b = _postes(donnees_avant), _postes(donnees_apres)
    libelles = {}
    for d in (donnees_avant, donnees_apres):
        for lot in d.get("lots", []):
            libelles[lot["lot"]] = lot.get("libelle") or lot["lot"]

    postes = []
    for cle in list(a) + [c for c in b if c not in a]:
        pa, pb = a.get(cle), b.get(cle)
        m1, m2 = (pa["montant"] if pa else 0), (pb["montant"] if pb else 0)
        ligne = {
            "lot": cle[0], "lot_libelle": libelles.get(cle[0], cle[0]), "designation": cle[1], "unite": cle[2],
            "quantite_avant": _num(pa["quantite"]) if pa else None,
            "quantite_apres": _num(pb["quantite"]) if pb else None,
            "prix_unitaire_avant": _num(pa["prix_unitaire"], 2) if pa and pa["prix_unitaire"] is not None else None,
            "prix_unitaire_apres": _num(pb["prix_unitaire"], 2) if pb and pb["prix_unitaire"] is not None else None,
            "montant_avant": m1 if pa else None, "montant_apres": m2 if pb else None,
            "ecart": m2 - m1,
            "ecart_pct": round((m2 - m1) / m1 * 100, 1) if pa and pb and m1 else None,
            "effet_quantite": None, "effet_prix": None, "arrondi": None,
        }
        if pa and pb:
            q1, q2 = pa["quantite"], pb["quantite"]
            pu1, pu2 = pa["prix_unitaire"], pb["prix_unitaire"]
            if pu1 is not None and pu2 is not None:
                eq = _entier((q2 - q1) * pu1)
                ep = _entier(q2 * (pu2 - pu1))
                ligne.update(effet_quantite=eq, effet_prix=ep, arrondi=(m2 - m1) - eq - ep)
            ligne["statut"] = "identique" if (m1 == m2 and q1 == q2) else "modifie"
        else:
            ligne["statut"] = "ajoute" if pb else "supprime"
        postes.append(ligne)

    lots = {}
    for p in postes:
        t = lots.setdefault(p["lot"], {"lot": p["lot"], "libelle": p["lot_libelle"], "avant": 0, "apres": 0})
        t["avant"] += p["montant_avant"] or 0
        t["apres"] += p["montant_apres"] or 0
    for t in lots.values():
        t["ecart"] = t["apres"] - t["avant"]

    total_avant, total_apres = donnees_avant.get("total_general", 0), donnees_apres.get("total_general", 0)
    compte = {s: sum(1 for p in postes if p["statut"] == s) for s in ("ajoute", "supprime", "modifie", "identique")}
    return {
        "total_avant": total_avant, "total_apres": total_apres, "ecart": total_apres - total_avant,
        "ecart_pct": round((total_apres - total_avant) / total_avant * 100, 1) if total_avant else None,
        "effet_quantite": sum(p["effet_quantite"] or 0 for p in postes),
        "effet_prix": sum(p["effet_prix"] or 0 for p in postes),
        "ecart_postes_ajoutes": sum(p["ecart"] for p in postes if p["statut"] == "ajoute"),
        "ecart_postes_supprimes": sum(p["ecart"] for p in postes if p["statut"] == "supprime"),
        "arrondi": sum(p["arrondi"] or 0 for p in postes),
        "compte": compte,
        "lots": list(lots.values()),
        "postes": postes,
    }
