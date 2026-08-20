from decimal import Decimal, ROUND_HALF_UP
from collections import defaultdict

from projets.models import Projet, ElementStructurel, PosteComplementaire

from moteur_calcul.constantes import (
    RATIO_ACIER_POTEAUX_KG_M3,
    RATIO_ACIER_POUTRES_KG_M3,
    RATIO_ACIER_SEMELLES_KG_M3,
    RATIO_ACIER_DALLES_KG_M3,
)
from moteur_calcul.formules.postes_ratio import calculer_poste_ratio, TYPES_POSTES

# Prix unitaires par défaut en FCFA
PRIX_UNITAIRES_DEFAUT = {
    "beton_m3": Decimal("100000"),
    "acier_kg": Decimal("800"),
    "coffrage_m2": Decimal("12000"),
    # AJOUTÉ (Ange, Jour 2 §2.1) : nécessaires pour valoriser les lignes
    # produites par calculer_poste_ratio() (maçonnerie, enduit), qui ne
    # sont ni du béton, ni de l'acier, ni du coffrage au sens des 3 clés
    # ci-dessus. Ordre de grandeur du DQE CIMBAT reçu -- à ajuster selon
    # le marché réel comme les 3 autres.
    "agglos_pleins_m3": Decimal("9000"),
    "agglos_15_creux_m2": Decimal("8000"),
    "agglos_10_creux_m2": Decimal("6000"),
    "enduit_m2": Decimal("3500"),
}

# Ratios d'acier utilisés en solution de secours (poids moteur non disponible).
# Alignés sur moteur_calcul.constantes (document technicien BTP) : on prend
# le milieu de chaque fourchette plutôt qu'une valeur inventée localement.
RATIOS_ACIER_KG_M3 = {
    "POTEAU": Decimal(str(sum(RATIO_ACIER_POTEAUX_KG_M3) / 2)),    # (100+150)/2 = 125
    "POUTRE": Decimal(str(sum(RATIO_ACIER_POUTRES_KG_M3) / 2)),    # (120+180)/2 = 150
    "SEMELLE": Decimal(str(sum(RATIO_ACIER_SEMELLES_KG_M3) / 2)),  # (40+60)/2 = 50
    "DALLE": Decimal(str(sum(RATIO_ACIER_DALLES_KG_M3) / 2)),      # (70+100)/2 = 85
}


def cm_vers_m(valeur_cm) -> float:
    """Convertit une dimension en centimètres vers des mètres."""
    if valeur_cm is None:
        return 0.0
    return float(valeur_cm) / 100.0


def calculer_element_dqe(element: ElementStructurel, prix_unitaires: dict) -> list:
    """
    Calcule les quantités et montants (Béton, Coffrage, Acier) pour un élément
    structurel validé.

    Retourne une liste de lignes de devis structurées.
    """
    res = element.resultat_valide
    if not res:
        return []

    lignes = []

    # 1. Poteau
    #
    # MODIFIÉ (Ange) : dimensionner_poteau() retourne "cote_cm" (poteau
    # carré), jamais "largeur_cm"/"profondeur_cm" -- ces clés n'existent
    # pas dans le résultat réel du moteur. L'ancienne version cherchait
    # les mauvaises clés, ce qui faisait échouer silencieusement la
    # condition `all(...)` et retournait [] pour TOUT poteau réel
    # (aucune ligne béton/coffrage/acier générée, sans erreur visible).
    if element.type_element == ElementStructurel.TypeElement.POTEAU:
        cote_cm = res.get("cote_cm")
        hauteur_poteau = element.hauteur_poteau  # en mètres sur le modèle

        if not all(v is not None for v in [cote_cm, hauteur_poteau]):
            return []

        cote_m = cm_vers_m(cote_cm)

        # Béton (m3) = côté * côté * hauteur (poteau carré)
        volume_beton = Decimal(str(cote_m * cote_m * hauteur_poteau))
        # Coffrage (m2) = 4 côtés * hauteur (poteau carré, pas 2*(l+p))
        surf_coffrage = Decimal(str(4 * cote_m * hauteur_poteau))

        # Acier (kg)
        # Priorité 1 : poids total fourni par le moteur (si présent)
        poids_moteur = res.get("poids_acier_total_kg")
        if poids_moteur is not None:
            poids_acier = Decimal(str(poids_moteur))
        else:
            # Priorité 2 : ratio par défaut (milieu de la fourchette du
            # document technicien, voir RATIOS_ACIER_KG_M3 ci-dessus)
            poids_acier = volume_beton * RATIOS_ACIER_KG_M3["POTEAU"]

    # 2. Poutre
    elif element.type_element == ElementStructurel.TypeElement.POUTRE:
        largeur_cm = res.get("largeur_cm")
        hauteur_cm = res.get("hauteur_cm")
        portee = element.portee  # en mètres sur le modèle

        if not all(v is not None for v in [largeur_cm, hauteur_cm, portee]):
            return []

        largeur_m = cm_vers_m(largeur_cm)
        hauteur_m = cm_vers_m(hauteur_cm)

        # Béton (m3) = l * h * L
        volume_beton = Decimal(str(largeur_m * hauteur_m * portee))
        # Coffrage (m2) = (l + 2*h) * L (face supérieure non coffrée)
        surf_coffrage = Decimal(str((largeur_m + 2 * hauteur_m) * portee))

        # Acier (kg)
        poids_moteur = res.get("poids_acier_total_kg")
        if poids_moteur is not None:
            poids_acier = Decimal(str(poids_moteur))
        else:
            poids_acier = volume_beton * RATIOS_ACIER_KG_M3["POUTRE"]

    # 3. Semelle
    elif element.type_element == ElementStructurel.TypeElement.SEMELLE:
        cote_cm = res.get("cote_cm")
        hauteur_cm = res.get("hauteur_cm")

        if not all(v is not None for v in [cote_cm, hauteur_cm]):
            return []

        cote_m = cm_vers_m(cote_cm)
        hauteur_m = cm_vers_m(hauteur_cm)

        # Béton (m3) = côté * côté * hauteur
        volume_beton = Decimal(str(cote_m * cote_m * hauteur_m))
        # Coffrage latéral (m2) = 4 * côté * hauteur
        surf_coffrage = Decimal(str(4 * cote_m * hauteur_m))

        # Acier (kg)
        poids_moteur = res.get("poids_acier_total_kg")
        if poids_moteur is not None:
            poids_acier = Decimal(str(poids_moteur))
        else:
            # MODIFIÉ (Ange) : 50 kg/m³ (milieu 40-60 du document
            # technicien) au lieu de 80 kg/m³ dans la version précédente,
            # qui dépassait la fourchette fournie sans justification connue.
            poids_acier = volume_beton * RATIOS_ACIER_KG_M3["SEMELLE"]

    # 4. Dalle (Module 7)
    #
    # AJOUTÉ (Ange) : jusqu'ici absente de calculer_element_dqe() -- une
    # dalle validée était silencieusement ignorée du DQE (même classe de
    # bug que le poteau il y a quelques semaines). Le moteur ne renvoie
    # qu'une épaisseur (predimensionner_dalle ne calcule pas le
    # ferraillage détaillé), donc l'acier reste toujours au ratio, jamais
    # au poids moteur.
    elif element.type_element == ElementStructurel.TypeElement.DALLE:
        epaisseur_cm = res.get("epaisseur_cm")
        surface = element.surface_m2  # m², champ ajouté sur le modèle

        if not all(v is not None for v in [epaisseur_cm, surface]):
            return []

        epaisseur_m = cm_vers_m(epaisseur_cm)

        # Béton (m3) = surface * épaisseur
        volume_beton = Decimal(str(surface * epaisseur_m))
        # Coffrage (m2) = sous-face de la dalle uniquement (dalle coulée
        # sur coffrage horizontal, pas de coffrage latéral à ce niveau
        # de détail -- cohérent avec le document technicien, section 3.1)
        surf_coffrage = Decimal(str(surface))

        poids_acier = volume_beton * RATIOS_ACIER_KG_M3["DALLE"]

    # 5. Semelle filante (Module 4)
    #
    # AJOUTÉ (Ange) : les résultats de dimensionner_semelle_filante() sont
    # exprimés PAR MÈTRE LINÉAIRE (largeur_cm, hauteur_cm,
    # acier_transversal_cm2_ml) -- il faut les multiplier par la longueur
    # totale du mur porté (element.longueur_m, champ ajouté sur le
    # modèle) pour obtenir des quantités totales comparables aux autres
    # lignes du DQE.
    elif element.type_element == ElementStructurel.TypeElement.SEMELLE_FILANTE:
        largeur_cm = res.get("largeur_cm")
        hauteur_cm = res.get("hauteur_cm")
        longueur = element.longueur_m  # m, champ ajouté sur le modèle

        if not all(v is not None for v in [largeur_cm, hauteur_cm, longueur]):
            return []

        largeur_m = cm_vers_m(largeur_cm)
        hauteur_m = cm_vers_m(hauteur_cm)

        # Béton (m3) = largeur * hauteur * longueur totale
        volume_beton = Decimal(str(largeur_m * hauteur_m * longueur))
        # Coffrage (m2) = 2 faces latérales * hauteur * longueur
        # (dessous contre le sol, dessus non coffré -- semelle filante
        # coulée en tranchée)
        surf_coffrage = Decimal(str(2 * hauteur_m * longueur))

        # Acier : le moteur donne un poids réel par mètre linéaire
        # (barres transversales + répartition), contrairement aux autres
        # types -- priorité au calcul réel plutôt qu'au ratio, dès qu'il
        # est disponible.
        acier_transversal_cm2_ml = res.get("acier_transversal_cm2_ml")
        acier_repartition_cm2_ml = res.get("acier_repartition_cm2_ml")
        if acier_transversal_cm2_ml is not None:
            # Poids = section totale (cm² -> m²) x longueur x densité acier
            section_totale_cm2_ml = acier_transversal_cm2_ml + (acier_repartition_cm2_ml or 0)
            section_totale_m2 = section_totale_cm2_ml / 10_000
            from moteur_calcul.constantes import DENSITE_ACIER_KG_M3
            poids_acier = Decimal(str(section_totale_m2 * longueur * DENSITE_ACIER_KG_M3))
        else:
            poids_acier = volume_beton * RATIOS_ACIER_KG_M3["SEMELLE"]

    else:
        return []

    # Sécurité anti-valeurs négatives ou nulles
    if volume_beton <= 0 or surf_coffrage <= 0 or poids_acier <= 0:
        return []

    # Construction des lignes de devis
    # Béton
    pu_beton = Decimal(str(prix_unitaires.get("beton_m3", PRIX_UNITAIRES_DEFAUT["beton_m3"])))
    lignes.append({
        "element_id": element.id,
        "repere": element.identifiant,
        "type_element": element.type_element.upper(),
        "designation": f"Béton armé — {element.get_type_element_display()} {element.identifiant}",
        "categorie": "BETON",
        "unite": "m³",
        "quantite": float(volume_beton.quantize(Decimal("0.0001"), rounding=ROUND_HALF_UP)),
        "prix_unitaire": int(pu_beton),
        "montant": int((volume_beton * pu_beton).quantize(Decimal("1"), rounding=ROUND_HALF_UP)),
    })

    # Coffrage
    pu_coffrage = Decimal(str(prix_unitaires.get("coffrage_m2", PRIX_UNITAIRES_DEFAUT["coffrage_m2"])))
    lignes.append({
        "element_id": element.id,
        "repere": element.identifiant,
        "type_element": element.type_element.upper(),
        "designation": f"Coffrage — {element.get_type_element_display()} {element.identifiant}",
        "categorie": "COFFRAGE",
        "unite": "m²",
        "quantite": float(surf_coffrage.quantize(Decimal("0.0001"), rounding=ROUND_HALF_UP)),
        "prix_unitaire": int(pu_coffrage),
        "montant": int((surf_coffrage * pu_coffrage).quantize(Decimal("1"), rounding=ROUND_HALF_UP)),
    })

    # Acier
    pu_acier = Decimal(str(prix_unitaires.get("acier_kg", PRIX_UNITAIRES_DEFAUT["acier_kg"])))
    lignes.append({
        "element_id": element.id,
        "repere": element.identifiant,
        "type_element": element.type_element.upper(),
        "designation": f"Armatures acier — {element.get_type_element_display()} {element.identifiant}",
        "categorie": "ACIER",
        "unite": "kg",
        "quantite": float(poids_acier.quantize(Decimal("0.0001"), rounding=ROUND_HALF_UP)),
        "prix_unitaire": int(pu_acier),
        "montant": int((poids_acier * pu_acier).quantize(Decimal("1"), rounding=ROUND_HALF_UP)),
    })

    return lignes


def calculer_postes_ratio_projet(geometrie: dict, prix_unitaires: dict, types_postes=TYPES_POSTES) -> list:
    """
    AJOUTÉ (Ange, Jour 2 §2.1) : branche calculer_poste_ratio() (postes
    maçonnerie/enduit/chaînage/raidisseur/acrotère, sans dimensionnement
    structurel dédié) sur le DQE -- jusqu'ici la fonction moteur existait
    mais rien ne la valorisait ni ne l'agrégeait au devis.

    Contrairement à calculer_element_dqe(), il n'y a pas d'ElementStructurel
    associé (ce sont des quantités déduites de la géométrie générale du
    bâtiment, pas d'un élément individuel) -- element_id reste None.

    Un poste dont la geometrie ne fournit pas les données nécessaires est
    silencieusement omis (calculer_poste_ratio() renvoie [] dans ce cas,
    ex. maçonnerie sans hauteur de soubassement) plutôt que de lever une
    erreur qui bloquerait tout le DQE pour un seul poste incomplet.
    """
    lignes = []
    for type_poste in types_postes:
        for ligne_brute in calculer_poste_ratio(type_poste, geometrie):
            cle_prix = _cle_prix_unitaire(ligne_brute["designation"], ligne_brute["unite"])
            pu = Decimal(str(prix_unitaires.get(cle_prix, PRIX_UNITAIRES_DEFAUT.get(cle_prix, 0))))
            quantite = Decimal(str(ligne_brute["quantite"]))
            if quantite <= 0:
                continue
            lignes.append({
                "element_id": None,
                "repere": type_poste.upper(),
                "type_element": "RATIO_" + type_poste.upper(),
                "designation": ligne_brute["designation"],
                "categorie": _categorie_depuis_unite(ligne_brute["unite"], ligne_brute["designation"]),
                "unite": ligne_brute["unite"],
                "quantite": float(quantite.quantize(Decimal("0.0001"), rounding=ROUND_HALF_UP)),
                "prix_unitaire": int(pu),
                "montant": int((quantite * pu).quantize(Decimal("1"), rounding=ROUND_HALF_UP)),
            })
    return lignes


def _cle_prix_unitaire(designation: str, unite: str) -> str:
    """Associe une ligne de postes_ratio à sa clé dans PRIX_UNITAIRES_DEFAUT."""
    d = designation.lower()
    if "agglos 15 pleins" in d:
        return "agglos_pleins_m3"
    if "agglos 15 creux" in d:
        return "agglos_15_creux_m2"
    if "agglos 10 creux" in d:
        return "agglos_10_creux_m2"
    if "enduit" in d:
        return "enduit_m2"
    if "béton" in d:
        return "beton_m3"
    if "acier" in d:
        return "acier_kg"
    if "coffrage" in d:
        return "coffrage_m2"
    raise ValueError(f"Pas de prix unitaire connu pour la ligne : {designation!r}")


def _categorie_depuis_unite(unite: str, designation: str) -> str:
    d = designation.lower()
    if "béton" in d or "agglos" in d:
        return "BETON"
    if "acier" in d:
        return "ACIER"
    if "coffrage" in d:
        return "COFFRAGE"
    if "enduit" in d:
        return "ENDUIT"
    return "AUTRE"


# --- Montant en toutes lettres (Jour 4) ----------------------------------
#
# Convention d'écriture financière (utilisée par CIMBAT sur le DQE de
# référence : "...soixante et un mille sept cent", pas "sept cents") :
# "cent" et "vingt" ne prennent JAMAIS la marque du pluriel dans un
# montant écrit en toutes lettres, contrairement à la règle grammaticale
# standard -- convention usuelle sur les chèques et devis pour éviter
# toute altération frauduleuse du montant.

_UNITES = ["", "un", "deux", "trois", "quatre", "cinq", "six", "sept", "huit", "neuf"]
_DIX_DIX_NEUF = [
    "dix", "onze", "douze", "treize", "quatorze", "quinze", "seize",
    "dix-sept", "dix-huit", "dix-neuf",
]
_DIZAINES = {20: "vingt", 30: "trente", 40: "quarante", 50: "cinquante", 60: "soixante"}


def _deux_chiffres_en_lettres(n: int) -> str:
    if n < 10:
        return _UNITES[n]
    if n < 20:
        return _DIX_DIX_NEUF[n - 10]
    if n < 70:
        dizaine, unite = divmod(n, 10)
        mot = _DIZAINES[dizaine * 10]
        if unite == 0:
            return mot
        if unite == 1:
            return f"{mot} et un"
        return f"{mot}-{_UNITES[unite]}"
    if n < 80:
        # 70-79 : soixante + 10..19 (soixante-dix, soixante et onze, soixante-douze...)
        reste = n - 60
        if reste == 11:
            return "soixante et onze"
        return f"soixante-{_DIX_DIX_NEUF[reste - 10]}"
    # 80-99 : quatre-vingt + 0..19 (pas de "s", convention financière)
    reste = n - 80
    if reste == 0:
        return "quatre-vingt"
    if reste < 10:
        return f"quatre-vingt-{_UNITES[reste]}"
    return f"quatre-vingt-{_DIX_DIX_NEUF[reste - 10]}"


def _trois_chiffres_en_lettres(n: int) -> str:
    centaines, reste = divmod(n, 100)
    mots = []
    if centaines > 0:
        prefixe = "cent" if centaines == 1 else f"{_UNITES[centaines]} cent"
        mots.append(prefixe)  # jamais de "s" (convention financière)
    if reste > 0:
        mots.append(_deux_chiffres_en_lettres(reste))
    return " ".join(mots) if mots else "zéro"


def nombre_en_lettres(n: int) -> str:
    """Convertit un entier positif en toutes lettres (français, convention financière)."""
    if n == 0:
        return "zéro"
    if n < 0:
        return "moins " + nombre_en_lettres(-n)

    milliards, reste = divmod(n, 10**9)
    millions, reste = divmod(reste, 10**6)
    milliers, unites = divmod(reste, 1000)

    parts = []
    if milliards:
        mot = _trois_chiffres_en_lettres(milliards)
        parts.append(f"{mot} milliard" + ("s" if milliards > 1 else ""))
    if millions:
        mot = _trois_chiffres_en_lettres(millions)
        parts.append(f"{mot} million" + ("s" if millions > 1 else ""))
    if milliers:
        parts.append("mille" if milliers == 1 else f"{_trois_chiffres_en_lettres(milliers)} mille")
    if unites:
        parts.append(_trois_chiffres_en_lettres(unites))
    return " ".join(parts)


def montant_en_toutes_lettres(montant_fcfa) -> str:
    """Ex. 45 961 700 -> 'quarante-cinq millions neuf cent soixante et un mille sept cent'."""
    return nombre_en_lettres(int(montant_fcfa))
def calculer_projet_dqe(projet: Projet, prix_unitaires: dict = None, geometrie: dict = None) -> dict:
    """
    Parcourt tous les éléments validés d'un projet, calcule leurs métrés,
    y associe les postes ratio (maçonnerie/enduit/chaînage/raidisseur/
    acrotère, si `geometrie` est fournie) et les postes de main d'œuvre
    saisis manuellement, et regroupe le tout par LOT façon CIMBAT.

    MODIFIÉ (Ange, Jour 2 §2.2) : restructuration par lot/sous-lot.
    - Chaque ligne porte désormais un champ "lot" (les éléments
      structurels et les postes ratio vont systématiquement dans
      LOT 02 — GROS OEUVRE, comme dans le DQE CIMBAT de référence ; les
      postes de main d'œuvre utilisent le lot choisi par l'ingénieur).
    - "sous_totaux_par_lot" (clé "lots" ci-dessous) remplace la clé
      plate "main_doeuvre" de l'ancien "sous_totaux" (qui mélangeait
      main d'œuvre et éléments structurels dans un seul total sans
      distinction de lot) -- retirée comme demandé dans la feuille de
      route.
    - Un seul passage sur toutes les lignes (pas de boucle imbriquée) :
      reste performant même quand poteaux/semelles viennent d'une grille
      de plusieurs dizaines d'éléments (trame).
    """
    if prix_unitaires is None:
        prix_unitaires = PRIX_UNITAIRES_DEFAUT

    LOT_GROS_OEUVRE_INFRA = PosteComplementaire.Lot.GROS_OEUVRE_INFRA.value
    LOT_GROS_OEUVRE_SUPER = PosteComplementaire.Lot.GROS_OEUVRE_SUPER.value
    # Lot par défaut (postes ratio, éléments sans position renseignée) :
    # la superstructure reste le cas le plus courant (maçonnerie, chaînages...).
    LOT_STRUCTUREL = LOT_GROS_OEUVRE_SUPER

    # Uniquement les éléments au statut VALIDE
    elements_valides = projet.elements.filter(statut=ElementStructurel.Statut.VALIDE)

    toutes_lignes = []

    # 1. Calcul pour les éléments structurels (LOT 02 — GROS OEUVRE)
    #    Semelles/fondations -> Infrastructure, reste (poteaux, poutres,
    #    dalles...) -> Superstructure, selon le champ `position` de
    #    l'élément (fallback Superstructure si non renseigné).
    for element in elements_valides:
        lot_element = (
            LOT_GROS_OEUVRE_INFRA
            if element.position == ElementStructurel.Position.INFRASTRUCTURE
            else LOT_GROS_OEUVRE_SUPER
        )
        for ligne in calculer_element_dqe(element, prix_unitaires):
            ligne["lot"] = lot_element
            toutes_lignes.append(ligne)

    # 2. Postes ratio (maçonnerie, enduit, chaînage, raidisseur, acrotère)
    #    -- uniquement si la géométrie générale du bâtiment est fournie ;
    #    silencieusement absents sinon (pas d'erreur bloquante : un
    #    projet peut être calculé sans ces informations si elles ne sont
    #    pas encore connues).
    if geometrie:
        for ligne in calculer_postes_ratio_projet(geometrie, prix_unitaires):
            ligne["lot"] = LOT_STRUCTUREL
            toutes_lignes.append(ligne)

    # 3. Postes de main d'œuvre manuels -- chacun dans SON lot
    for poste in projet.postes_complementaires.all():
        q_dec = Decimal(str(poste.quantite))
        pu_dec = Decimal(str(poste.prix_unitaire))
        montant_dec = (q_dec * pu_dec).quantize(Decimal("1"), rounding=ROUND_HALF_UP)

        toutes_lignes.append({
            "element_id": None,
            "repere": "MO",
            "type_element": "MAIN_DOEUVRE",
            "designation": poste.designation,
            "categorie": "MAIN_DOEUVRE",
            "unite": poste.unite,
            "quantite": float(q_dec.quantize(Decimal("0.0001"), rounding=ROUND_HALF_UP)),
            "prix_unitaire": int(pu_dec),
            "montant": int(montant_dec),
            "lot": poste.lot,
        })

    # 4. Regroupement par lot + sous-totaux par catégorie -- un seul passage
    sous_totaux_categorie = defaultdict(Decimal)
    lots = defaultdict(lambda: {"lignes": [], "sous_total": Decimal("0")})

    for ligne in toutes_lignes:
        montant = Decimal(str(ligne["montant"]))
        lots[ligne["lot"]]["lignes"].append(ligne)
        lots[ligne["lot"]]["sous_total"] += montant
        if ligne["categorie"] != "MAIN_DOEUVRE":
            sous_totaux_categorie[ligne["categorie"].lower()] += montant

    total_general = sum(l["sous_total"] for l in lots.values())

    # Ordre d'affichage stable, façon CIMBAT (LOT 00 en premier, etc.)
    ordre_lots = [choix.value for choix in PosteComplementaire.Lot]
    lots_ordonnes = sorted(
        lots.keys(), key=lambda lot: ordre_lots.index(lot) if lot in ordre_lots else len(ordre_lots)
    )

    return {
        "projet": {
            "id": projet.id,
            "nom": projet.nom,
        },
        "lignes": toutes_lignes,
        "lots": [
            {
                "lot": lot,
                "lignes": lots[lot]["lignes"],
                "sous_total": int(lots[lot]["sous_total"]),
            }
            for lot in lots_ordonnes
        ],
        "sous_totaux": {
            categorie: int(montant) for categorie, montant in sous_totaux_categorie.items()
        },
        "total_general": int(total_general),
        "montant_lettres": montant_en_toutes_lettres(total_general),
        "devise": "FCFA",
    }