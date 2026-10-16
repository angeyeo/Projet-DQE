"""
Fiche d'approvisionnement : transforme les quantités du DQE en matériaux à
acheter (ciment, sable, gravier, acier, agglos), pertes comprises, puis en
coût d'achat si le cabinet a renseigné les prix des matériaux.

Sources des valeurs par défaut (« référence ») :
  - dosage du béton 350 kg de ciment, 0,45 m³ de sable, 0,85 m³ de gravier
    par m³ de béton : DQE de l'ingénieur BTP (R+1 NEW ERA) ;
  - pertes 3 % (tous matériaux) et 4 % (agglos) : ingénieur BTP, 10/10/2026 ;
  - 12 agglos par m² de mur : DQE de l'ingénieur.
Chaque valeur peut être remplacée par le cabinet ; la fiche dit toujours
d'où vient chaque valeur.

Règles (projet DQE) : aucune quantité ni aucun prix inventé.
  - un prix de matériau absent -> ligne sans montant + problème explicite,
    total HT « partiel » (jamais présenté comme complet) ;
  - un nombre de voyages n'est calculé que si la capacité du camion est
    saisie ;
  - ce qui ne peut pas être converti (coffrage, enduits sans dosage de
    mortier, postes saisis à la main) est listé, jamais ignoré en silence.
"""

import math
from decimal import ROUND_HALF_UP, Decimal

# Paramètres de référence : (valeur, libellé, unité, source)
PARAMETRES_REFERENCE = {
    "ciment_t_par_m3": (0.35, "Ciment par m³ de béton", "T/m³", "DQE de l'ingénieur BTP"),
    "sable_m3_par_m3": (0.45, "Sable par m³ de béton", "m³/m³", "DQE de l'ingénieur BTP"),
    "gravier_m3_par_m3": (0.85, "Gravier par m³ de béton", "m³/m³", "DQE de l'ingénieur BTP"),
    "pertes_pct": (3.0, "Pertes (ciment, sable, gravier, acier)", "%", "Ingénieur BTP, 10/10/2026"),
    "pertes_agglos_pct": (4.0, "Pertes sur les agglos", "%", "Ingénieur BTP, 10/10/2026"),
    "agglos_par_m2": (12.0, "Agglos par m² de mur", "u/m²", "DQE de l'ingénieur BTP"),
    "sac_ciment_kg": (50.0, "Poids d'un sac de ciment", "kg", "Conditionnement courant"),
    "capacite_camion_sable_m3": (None, "Capacité d'un camion de sable", "m³", None),
    "capacite_camion_gravier_m3": (None, "Capacité d'un camion de gravier", "m³", None),
}

# Bornes de validation des paramètres saisis par le cabinet.
BORNES_PARAMETRES = {
    "ciment_t_par_m3": (0.1, 0.6),
    "sable_m3_par_m3": (0.1, 1.0),
    "gravier_m3_par_m3": (0.1, 1.5),
    "pertes_pct": (0.0, 50.0),
    "pertes_agglos_pct": (0.0, 50.0),
    "agglos_par_m2": (5.0, 20.0),
    "sac_ciment_kg": (25.0, 100.0),
    "capacite_camion_sable_m3": (1.0, 60.0),
    "capacite_camion_gravier_m3": (1.0, 60.0),
}

# Prix des matériaux (dans le barème du cabinet, à côté des prix posés).
LIBELLES_PRIX_MATERIAUX = {
    "ciment_t": "Ciment (FCFA/T)",
    "sable_m3": "Sable (FCFA/m³)",
    "gravier_m3": "Gravier (FCFA/m³)",
    "acier_t": "Acier (FCFA/T)",
    "agglo_15_plein_u": "Agglo de 15 plein (FCFA/unité)",
    "agglo_15_creux_u": "Agglo de 15 creux (FCFA/unité)",
    "agglo_10_creux_u": "Agglo de 10 creux (FCFA/unité)",
}

# Prix relevés dans le DQE de l'ingénieur (2026) : PROPOSÉS au cabinet,
# jamais appliqués d'office. Sable et gravier y sont vendus au voyage de
# camion en tonnes : sans masse volumique, aucun prix au m³ n'en est déduit.
PRIX_MATERIAUX_REFERENCE = {
    "ciment_t": 100000,
    "acier_t": 450000,
    "agglo_15_creux_u": 400,
}

# Agglos : clé de prix du DQE (au m²) -> (clé de prix matériau, désignation)
AGGLOS = {
    "agglos_15_pleins_m2": ("agglo_15_plein_u", "Agglos de 15 pleins"),
    "agglos_15_creux_m2": ("agglo_15_creux_u", "Agglos de 15 creux"),
    "agglos_10_creux_m2": ("agglo_10_creux_u", "Agglos de 10 creux"),
}


def _d(v):
    return Decimal(str(v))


def _arr(v, n=3):
    return float(_d(v).quantize(Decimal(1).scaleb(-n), rounding=ROUND_HALF_UP))


def valider_parametres(params: dict) -> dict:
    """Paramètres du cabinet nettoyés ; lève ValueError avec un message clair."""
    if not isinstance(params, dict):
        raise ValueError("Les paramètres d'approvisionnement doivent être un objet {clé: valeur}.")
    propres = {}
    for cle, valeur in params.items():
        if cle not in PARAMETRES_REFERENCE:
            raise ValueError(f"Paramètre d'approvisionnement inconnu : « {cle} ».")
        if valeur in (None, ""):
            continue
        try:
            v = float(valeur)
        except (TypeError, ValueError):
            raise ValueError(f"« {PARAMETRES_REFERENCE[cle][1]} » : valeur invalide ({valeur!r}).") from None
        mini, maxi = BORNES_PARAMETRES[cle]
        if not mini <= v <= maxi:
            raise ValueError(
                f"« {PARAMETRES_REFERENCE[cle][1]} » doit être compris entre {mini:g} et {maxi:g} "
                f"{PARAMETRES_REFERENCE[cle][2]}."
            )
        propres[cle] = v
    return propres


def parametres_effectifs(params_cabinet: dict | None) -> dict:
    """{clé: {"valeur", "libelle", "unite", "source"}} : cabinet > référence."""
    params_cabinet = params_cabinet or {}
    res = {}
    for cle, (defaut, libelle, unite, source) in PARAMETRES_REFERENCE.items():
        v = params_cabinet.get(cle)
        if v not in (None, ""):
            res[cle] = {"valeur": float(v), "libelle": libelle, "unite": unite, "source": "Paramètre du cabinet"}
        else:
            res[cle] = {"valeur": defaut, "libelle": libelle, "unite": unite,
                        "source": source or "non renseigné"}
    return res


def _prix(prix: dict, cle: str, problemes: list):
    brut = (prix or {}).get(cle)
    if brut in (None, ""):
        problemes.append({
            "code": "PRIX_MATERIAU_MANQUANT", "cle_prix": cle,
            "message": f"Prix « {LIBELLES_PRIX_MATERIAUX[cle]} » non renseigné : montant de cette ligne non calculé.",
        })
        return None
    try:
        pu = _d(brut)
    except Exception:  # noqa: BLE001 -- valeur illisible signalée, jamais remplacée
        pu = None
    if pu is None or pu < 0:
        problemes.append({"code": "PRIX_MATERIAU_INVALIDE", "cle_prix": cle,
                          "message": f"Prix « {LIBELLES_PRIX_MATERIAUX[cle]} » invalide : {brut!r}."})
        return None
    return pu


def calculer_fiche_approvisionnement(dqe_data: dict, params_cabinet: dict | None, prix: dict | None,
                                     taux_tva_pct=None) -> dict:
    """Fiche d'approvisionnement à partir d'un DQE déjà calculé (calculer_projet_dqe)."""
    p = parametres_effectifs(params_cabinet)
    val = {k: v["valeur"] for k, v in p.items()}
    pertes = _d(val["pertes_pct"]) / 100
    pertes_agglos = _d(val["pertes_agglos_pct"]) / 100
    problemes = []

    # --- 1. Quantités de départ, ligne par ligne du DQE (traçabilité) ------
    beton, acier_kg, agglos_m2, non_convertis = [], _d(0), {}, []
    for l in dqe_data.get("lignes", []):
        cat, unite, q = l.get("categorie"), l.get("unite"), l.get("quantite")
        if q is None:
            continue
        origine = {"repere": l.get("repere"), "designation": l.get("designation"), "quantite": q}
        if cat == "BETON" and unite == "m³":
            beton.append(origine)
        elif cat == "ACIER" and unite == "kg":
            acier_kg += _d(q)
        elif l.get("cle_prix") in AGGLOS and unite == "m²":
            agglos_m2.setdefault(l["cle_prix"], []).append(origine)
        else:
            raison = {
                "COFFRAGE": "coffrage : bois et contreplaqué non chiffrés en matériaux",
                "ENDUIT": "enduit : dosage du mortier non renseigné",
            }.get(cat, "poste sans conversion en matériaux")
            non_convertis.append({**origine, "unite": unite, "raison": raison})

    volume_beton = sum((_d(b["quantite"]) for b in beton), _d(0))
    lignes = []

    def ligne(cle, materiau, unite, net, taux, formule, cle_prix=None, origines=None, conditionnement=None,
              voyages=None, entier=False):
        commande = net * (1 + taux)
        # Même règle que le DQE : montant = quantité affichée (au millième,
        # ou à l'unité pour les agglos) × prix unitaire -- le lecteur peut
        # refaire la multiplication.
        commande = _d(math.ceil(commande)) if entier else commande.quantize(Decimal("0.001"), rounding=ROUND_HALF_UP)
        pu = _prix(prix, cle_prix, problemes) if cle_prix else None
        montant = int((commande * pu).quantize(Decimal("1"), rounding=ROUND_HALF_UP)) if pu is not None else None
        lignes.append({
            "cle": cle, "materiau": materiau, "unite": unite,
            "quantite_nette": _arr(net), "pertes_pct": float(taux * 100),
            "quantite_commande": int(commande) if entier else _arr(commande),
            "conditionnement": conditionnement(commande) if conditionnement else None,
            "voyages": voyages(commande) if voyages else None,
            "cle_prix": cle_prix, "prix_unitaire": float(pu) if pu is not None else None, "montant": montant,
            "formule": formule, "origines": origines or [],
        })

    def voyages_par(capacite_cle, nom):
        cap = val[capacite_cle]
        if not cap:
            return lambda q: {"nombre": None, "message": f"Capacité du camion de {nom} non renseignée : voyages non calculés."}
        return lambda q: {"nombre": math.ceil(float(q) / cap), "capacite_m3": cap,
                          "message": f"{math.ceil(float(q) / cap)} voyage(s) de {cap:g} m³"}

    if volume_beton > 0:
        n = lambda v: f"{v:g}".replace(".", ",")  # noqa: E731
        vb = _arr(volume_beton)
        ligne("ciment", "Ciment", "T", volume_beton * _d(val["ciment_t_par_m3"]), pertes,
              f"{n(vb)} m³ × {n(val['ciment_t_par_m3'])} T/m³ × (1 + {n(val['pertes_pct'])} %)", "ciment_t", beton,
              conditionnement=lambda q: f"{math.ceil(q * 1000 / _d(val['sac_ciment_kg']))} sacs de {val['sac_ciment_kg']:g} kg")
        ligne("sable", "Sable", "m³", volume_beton * _d(val["sable_m3_par_m3"]), pertes,
              f"{n(vb)} m³ × {n(val['sable_m3_par_m3'])} m³/m³ × (1 + {n(val['pertes_pct'])} %)", "sable_m3", beton,
              voyages=voyages_par("capacite_camion_sable_m3", "sable"))
        ligne("gravier", "Gravier", "m³", volume_beton * _d(val["gravier_m3_par_m3"]), pertes,
              f"{n(vb)} m³ × {n(val['gravier_m3_par_m3'])} m³/m³ × (1 + {n(val['pertes_pct'])} %)", "gravier_m3", beton,
              voyages=voyages_par("capacite_camion_gravier_m3", "gravier"))
    if acier_kg > 0:
        ligne("acier", "Acier (armatures)", "T", acier_kg / 1000, pertes,
              f"{_arr(acier_kg, 1):g} kg ÷ 1000 × (1 + {val['pertes_pct']:g} %)".replace(".", ","), "acier_t")
    for cle_dqe, origines in agglos_m2.items():
        cle_prix, nom = AGGLOS[cle_dqe]
        surface = sum((_d(o["quantite"]) for o in origines), _d(0))
        ligne(cle_prix, nom, "u", surface * _d(val["agglos_par_m2"]), pertes_agglos,
              f"{_arr(surface, 2):g} m² × {val['agglos_par_m2']:g} u/m² × (1 + {val['pertes_agglos_pct']:g} %), arrondi à l'unité".replace(".", ","),
              cle_prix, origines, entier=True)

    # --- 2. Totaux : jamais un total présenté comme complet s'il manque un prix
    montants = [l["montant"] for l in lignes]
    complet = bool(lignes) and all(m is not None for m in montants)
    total_chiffre = sum(m for m in montants if m is not None)
    total_ht = total_chiffre if complet else None
    tva = ttc = None
    messages = []
    if not lignes:
        messages.append("Aucune quantité convertible en matériaux dans ce DQE.")
    elif not complet:
        messages.append(f"Total partiel : {sum(1 for m in montants if m is None)} ligne(s) sans prix de matériau. "
                        f"Total HT non calculé.")
    if total_ht is not None:
        if taux_tva_pct is None:
            messages.append("Taux de TVA du cabinet non renseigné : TTC non calculé.")
        else:
            tva = int((_d(total_ht) * _d(taux_tva_pct) / 100).quantize(Decimal("1"), rounding=ROUND_HALF_UP))
            ttc = total_ht + tva

    return {
        "projet": dqe_data.get("projet", {}),
        "parametres": p,
        "volume_beton_m3": _arr(volume_beton),
        "lignes": lignes,
        "non_convertis": non_convertis,
        "problemes": problemes,
        "total_chiffre": total_chiffre,
        "total_ht": total_ht,
        "taux_tva_pct": float(taux_tva_pct) if taux_tva_pct is not None else None,
        "montant_tva": tva,
        "total_ttc": ttc,
        "messages": messages,
        "hypotheses": [
            "Un seul dosage pour tous les bétons (béton de propreté compris), comme dans le DQE de l'ingénieur.",
            "Acier : poids du DQE (calculé par le moteur ou estimé par ratio, voir le DQE).",
        ],
    }
