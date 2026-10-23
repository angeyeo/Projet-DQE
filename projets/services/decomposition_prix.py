"""
Décomposition d'un prix unitaire en part MATÉRIAUX et part MAIN-D'ŒUVRE
(issue #92, première étape de #85).

Règles :
  - les deux parts viennent des prix du cabinet (bibliothèque, barème,
    poste saisi) : AUCUN pourcentage par défaut, aucune répartition
    inventée ;
  - un prix sans décomposition reste valable : sa ligne de DQE est
    « non décomposé » ;
  - si les deux parts sont données, prix unitaire = matériaux + main-d'œuvre
    (contrôlé ici, côté serveur) ; une seule part donnée est refusée.
"""

from decimal import ROUND_HALF_UP, Decimal

TOLERANCE_FCFA = 0.01  # écart admis entre le total et la somme des parts (arrondis de saisie)
DECOMPOSE, NON_DECOMPOSE = "decompose", "non_decompose"


def verifier_decomposition(prix_unitaire, materiaux, main_oeuvre, libelle="ce prix"):
    """Renvoie (prix_unitaire, materiaux, main_oeuvre) cohérents, ou lève
    ValueError avec un message pour l'utilisateur.
    - aucune part : prix inchangé, parts None (« non décomposé ») ;
    - deux parts sans total : total = matériaux + main-d'œuvre ;
    - deux parts et un total : le total doit être leur somme."""
    if materiaux is None and main_oeuvre is None:
        return prix_unitaire, None, None
    if materiaux is None or main_oeuvre is None:
        raise ValueError(f"{libelle} : renseignez les DEUX parts (matériaux et main-d'œuvre), ou aucune.")
    try:
        mat, mo = float(materiaux), float(main_oeuvre)
    except (TypeError, ValueError):
        raise ValueError(f"{libelle} : parts matériaux / main-d'œuvre non numériques.") from None
    if mat < 0 or mo < 0:
        raise ValueError(f"{libelle} : les parts matériaux et main-d'œuvre doivent être positives ou nulles.")
    total = mat + mo
    if prix_unitaire not in (None, "") and abs(float(prix_unitaire) - total) > TOLERANCE_FCFA:
        raise ValueError(
            f"{libelle} : le prix unitaire ({float(prix_unitaire):g} FCFA) n'est pas égal à matériaux + "
            f"main-d'œuvre ({mat:g} + {mo:g} = {total:g} FCFA).")
    return total, mat, mo


def decorer_ligne(ligne, materiaux, main_oeuvre):
    """Ajoute à une ligne de DQE ses parts matériaux / main-d'œuvre.

    montant_materiaux = quantité × prix matériaux, arrondi au FCFA ;
    montant_main_oeuvre = montant − montant_materiaux, pour que les deux
    parts fassent EXACTEMENT le montant de la ligne (écart d'arrondi ≤ 1 FCFA
    porté par la main-d'œuvre, jamais de FCFA créé ou perdu).
    Sans décomposition (ou décomposition incohérente avec le prix de la
    ligne), la ligne est « non décomposé » et ses parts restent vides."""
    vide = {"decomposition": NON_DECOMPOSE, "prix_materiaux": None, "prix_main_oeuvre": None,
            "montant_materiaux": None, "montant_main_oeuvre": None}
    if materiaux is None or main_oeuvre is None:
        ligne.update(vide)
        return ligne
    mat, mo = Decimal(str(materiaux)), Decimal(str(main_oeuvre))
    if abs((mat + mo) - Decimal(str(ligne["prix_unitaire"]))) > Decimal(str(TOLERANCE_FCFA)):
        ligne.update(vide)
        ligne["decomposition_incoherente"] = True
        return ligne
    m_mat = int((Decimal(str(ligne["quantite"])) * mat).quantize(Decimal("1"), rounding=ROUND_HALF_UP))
    ligne.update({
        "decomposition": DECOMPOSE,
        "prix_materiaux": float(mat) if mat != mat.to_integral_value() else int(mat),
        "prix_main_oeuvre": float(mo) if mo != mo.to_integral_value() else int(mo),
        "montant_materiaux": m_mat,
        "montant_main_oeuvre": ligne["montant"] - m_mat,
    })
    return ligne


def totaux(lignes):
    """Sous-totaux matériaux / main-d'œuvre / non décomposé d'un ensemble de lignes."""
    mat = sum(l["montant_materiaux"] for l in lignes if l.get("decomposition") == DECOMPOSE)
    mo = sum(l["montant_main_oeuvre"] for l in lignes if l.get("decomposition") == DECOMPOSE)
    nd = sum(l["montant"] for l in lignes if l.get("decomposition") != DECOMPOSE)
    return {"materiaux": mat, "main_oeuvre": mo, "non_decompose": nd}
