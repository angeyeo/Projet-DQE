"""
Contrôles de PLAUSIBILITÉ (distincts de la validation).

Validation   : une valeur physiquement impossible est REFUSÉE (validators.py).
Plausibilité : une valeur possible mais inhabituelle est SIGNALÉE
               (« ALERTE — valeur inhabituelle ») et JAMAIS modifiée.

Les plages ci-dessous sont des ordres de grandeur du bâtiment courant en
béton armé ; elles déclenchent une relecture, pas un refus. Elles sont
regroupées ici pour être relues et ajustées par le métier.
"""

PLAGES = {
    # cle: (min, max, unite, libelle)
    "portee": (2.0, 8.0, "m", "portée de trame"),
    "hauteur_etage": (2.5, 4.5, "m", "hauteur d'étage"),
    "g_plancher": (3.0, 10.0, "kN/m²", "charge permanente des planchers G"),
    "q": (1.0, 10.0, "kN/m²", "charge d'exploitation Q"),
    "contrainte_sol": (50.0, 600.0, "kN/m²", "contrainte admissible du sol"),
    "nb_niveaux": (1, 6, "", "nombre de niveaux (méthode simplifiée)"),
    "cote_poteau": (20, 60, "cm", "côté de poteau"),
    "cote_semelle": (40, 300, "cm", "côté de semelle isolée"),
    "epaisseur_dalle": (12, 25, "cm", "épaisseur de dalle"),
}


def _alerte(code, cle, valeur, contexte=None, detail=None):
    mini, maxi, unite, libelle = PLAGES[cle]
    u = f" {unite}" if unite else ""
    return {
        "code": code,
        "niveau": "ALERTE",
        "message": (
            f"ALERTE — valeur inhabituelle{f' ({contexte})' if contexte else ''} : {libelle} = {valeur:g}{u} "
            f"(plage courante {mini:g}–{maxi:g}{u})." + (f" {detail}" if detail else "")
        ),
        "message_groupe": f"ALERTE — valeur inhabituelle : {libelle} hors de la plage courante {mini:g}–{maxi:g}{u}.",
        "valeur": valeur,
        "plage": [mini, maxi],
        "unite": unite,
        "element": contexte,
    }


def _hors(cle, v):
    mini, maxi = PLAGES[cle][:2]
    return v is not None and (v < mini or v > maxi)


def controler_parametres(*, portee_x=None, portee_y=None, hauteur_etage=None, g=None, q=None,
                         contrainte_sol=None, nb_niveaux=None):
    alertes = []
    for nom, v in (("X", portee_x), ("Y", portee_y)):
        if _hors("portee", v):
            alertes.append(_alerte(f"PORTEE_{nom}_INHABITUELLE", "portee", v,
                                   detail="Au-delà de 8 m, prévoir une étude de flèche et de poutres précontraintes ou retombées."
                                   if v > 8 else None))
    if _hors("hauteur_etage", hauteur_etage):
        alertes.append(_alerte("HAUTEUR_ETAGE_INHABITUELLE", "hauteur_etage", hauteur_etage))
    if _hors("g_plancher", g):
        alertes.append(_alerte("G_INHABITUELLE", "g_plancher", g))
    if _hors("q", q):
        alertes.append(_alerte("Q_INHABITUELLE", "q", q))
    if _hors("contrainte_sol", contrainte_sol):
        alertes.append(_alerte("SOL_INHABITUEL", "contrainte_sol", contrainte_sol,
                               detail="Sol très faible : fondations superficielles à justifier par une étude géotechnique."
                               if contrainte_sol < 50 else None))
    if _hors("nb_niveaux", nb_niveaux):
        alertes.append(_alerte("NIVEAUX_INHABITUELS", "nb_niveaux", nb_niveaux,
                               detail="Contreventement et effets du second ordre non traités par le moteur."))
    return alertes


def controler_resultats(elements, portee_min=None):
    """elements : itérable de (identifiant, type_element, resultat dict)."""
    alertes = []
    for ident, type_el, res in elements:
        if not res:
            continue
        if type_el == "poteau":
            if _hors("cote_poteau", res.get("cote_cm")):
                alertes.append(_alerte("POTEAU_INHABITUEL", "cote_poteau", res["cote_cm"], ident))
            if res.get("frettage_necessaire"):
                alertes.append({"code": "POTEAU_ACIER_MAX", "niveau": "ALERTE", "element": ident,
                                "message": f"ALERTE — {ident} : section d'acier au-delà de 5 % du béton, revoir la section.",
                                "message_groupe": "ALERTE — poteaux dont l'acier dépasse 5 % du béton : revoir la section."})
        elif type_el == "semelle":
            cote = res.get("cote_cm")
            if _hors("cote_semelle", cote):
                alertes.append(_alerte("SEMELLE_INHABITUELLE", "cote_semelle", cote, ident,
                                       detail="Au-delà de 3 m, étudier semelles filantes ou radier."))
            if cote and portee_min and cote / 100 >= portee_min:
                alertes.append({"code": "SEMELLES_JOINTIVES", "niveau": "ALERTE", "element": ident,
                                "message": (f"ALERTE — {ident} : côté {cote:g} cm ≥ entraxe minimal "
                                            f"{portee_min:g} m : les semelles se touchent, étudier un radier."),
                                "message_groupe": "ALERTE — semelles plus larges que l'entraxe des poteaux : "
                                                  "elles se touchent, étudier un radier."})
        elif type_el == "dalle":
            if _hors("epaisseur_dalle", res.get("epaisseur_cm")):
                alertes.append(_alerte("DALLE_INHABITUELLE", "epaisseur_dalle", res["epaisseur_cm"], ident))
    return alertes


def controler_projet(projet):
    """Alertes de plausibilité d'un projet Django (paramètres + résultats)."""
    from .hypotheses import resoudre_charge_permanente

    try:
        g = resoudre_charge_permanente(projet.charge_permanente_kn_m2, projet.couches_permanentes or None)[0]
    except ValueError:
        g = None
    alertes = controler_parametres(
        portee_x=projet.portee_x, portee_y=projet.portee_y, hauteur_etage=projet.hauteur_etage,
        g=g, q=projet.charge_exploitation, contrainte_sol=projet.contrainte_sol_kn_m2,
        nb_niveaux=projet.nb_niveaux,
    )
    portees = [p for p in (projet.portee_x, projet.portee_y) if p]
    elements = ((e.identifiant, e.type_element, e.resultat_valide or e.resultat_calcul)
                for e in projet.elements.all())
    return alertes + controler_resultats(elements, portee_min=min(portees) if portees else None)
