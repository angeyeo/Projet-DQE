"""
Rendu PDF du DQE : PRÉSENTATION UNIQUEMENT.

Ce module ne calcule rien : quantités, prix, montants, TVA et totaux
viennent tels quels de `dqe_data` (calculer_projet_dqe). Les seules
opérations faites ici sont du formatage (séparateurs de milliers,
regroupement visuel déjà fourni par le calculateur) et une part en %
du récapitulatif par lot, dérivée des montants reçus.

Structure (une fonction par bloc, testables séparément) :
    entete()            -- page 1 : cabinet (logo réel ou typographie) + références
    titre()             -- titre du document, projet, lots
    infos_projet()      -- cartouche d'informations (champs disponibles seulement)
    tableau_lot()       -- cœur du document : lignes numérotées par sous-lot
    recap_lots()        -- récapitulatif par lot
    bloc_financier()    -- HT / (déboursé, marge) / TVA / TTC
    montant_lettres()   -- « Arrêté le présent devis… »
    infos_techniques()  -- hypothèses RÉELLEMENT utilisées (sinon rien)
    cartouche()         -- cartouche de validation (établi / vérifié / visa)
    PiedDePage          -- en-tête courant (pages 2+) et pied de page, « Page x / n »
"""

import os
from io import BytesIO
from xml.sax.saxutils import escape

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_RIGHT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import mm
from reportlab.lib.utils import ImageReader
from reportlab.pdfgen import canvas as pdfcanvas
from reportlab.platypus import (
    CondPageBreak, Image, KeepTogether, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle,
)

# ---------------------------------------------------------------------------
# Charte graphique (source unique des couleurs et tailles)
# ---------------------------------------------------------------------------


class Couleurs:
    NUIT = colors.HexColor("#14233C")        # bleu nuit : titres, en-têtes de tableau, total TTC
    BLEU = colors.HexColor("#2B4C7E")        # bleu technique : filets, numéros
    TEXTE = colors.HexColor("#1F2933")
    GRIS = colors.HexColor("#5B6573")        # texte secondaire
    GRIS_MOYEN = colors.HexColor("#9AA4B2")
    FILET = colors.HexColor("#D9DEE5")       # séparateurs très légers
    FOND = colors.HexColor("#F3F5F8")        # fonds de blocs
    FOND_LEGER = colors.HexColor("#FAFBFC")  # alternance des lignes
    ACCENT = colors.HexColor("#C1511F")      # accent de la marque, avec parcimonie
    BLANC = colors.white


class Tailles:
    TITRE = 24
    SOUS_TITRE = 14
    SECTION = 10
    CORPS = 8.6
    PETIT = 7.4
    PIED = 7


MARGE_X = 18 * mm
MARGE_HAUT = 16 * mm
MARGE_BAS = 22 * mm
LARGEUR_PAGE, HAUTEUR_PAGE = A4
LARGEUR_UTILE = LARGEUR_PAGE - 2 * MARGE_X

# Police EMBARQUÉE dans le PDF (Bitstream Vera, livrée avec reportlab) :
# les polices standard non embarquées (Helvetica) laissaient certains
# lecteurs afficher « m » au lieu de « m³ » / « m² ».
def _enregistrer_polices():
    import os

    import reportlab
    from reportlab.pdfbase import pdfmetrics
    from reportlab.pdfbase.ttfonts import TTFont

    dossier = os.path.join(os.path.dirname(reportlab.__file__), "fonts")
    for nom, fichier in (("DQE", "Vera.ttf"), ("DQE-Bold", "VeraBd.ttf"), ("DQE-Oblique", "VeraIt.ttf")):
        if nom not in pdfmetrics.getRegisteredFontNames():
            pdfmetrics.registerFont(TTFont(nom, os.path.join(dossier, fichier)))


_enregistrer_polices()
POLICE, POLICE_GRAS, POLICE_ITALIQUE = "DQE", "DQE-Bold", "DQE-Oblique"


def _style(nom, **kw):
    base = dict(fontName=POLICE, fontSize=Tailles.CORPS, leading=Tailles.CORPS * 1.35, textColor=Couleurs.TEXTE)
    base.update(kw)
    return ParagraphStyle(nom, **base)


S = {
    "titre": _style("titre", fontName=POLICE_GRAS, fontSize=Tailles.TITRE, leading=Tailles.TITRE * 1.15,
                    textColor=Couleurs.NUIT),
    "sous_titre": _style("sous_titre", fontName=POLICE_GRAS, fontSize=Tailles.SOUS_TITRE,
                         leading=Tailles.SOUS_TITRE * 1.3, textColor=Couleurs.NUIT),
    "surtitre": _style("surtitre", fontName=POLICE_GRAS, fontSize=Tailles.PETIT, textColor=Couleurs.ACCENT,
                       leading=Tailles.PETIT * 1.5),
    "section": _style("section", fontName=POLICE_GRAS, fontSize=Tailles.SECTION, textColor=Couleurs.NUIT,
                      leading=Tailles.SECTION * 1.4),
    "corps": _style("corps"),
    "corps_gras": _style("corps_gras", fontName=POLICE_GRAS),
    "droite": _style("droite", alignment=TA_RIGHT),
    "droite_gras": _style("droite_gras", fontName=POLICE_GRAS, alignment=TA_RIGHT),
    "centre": _style("centre", alignment=TA_CENTER),
    "petit": _style("petit", fontSize=Tailles.PETIT, leading=Tailles.PETIT * 1.4, textColor=Couleurs.GRIS),
    "petit_droite": _style("petit_droite", fontSize=Tailles.PETIT, leading=Tailles.PETIT * 1.4,
                           textColor=Couleurs.GRIS, alignment=TA_RIGHT),
    "etiquette": _style("etiquette", fontSize=Tailles.PETIT, textColor=Couleurs.GRIS, leading=Tailles.PETIT * 1.5),
    "entete_tab": _style("entete_tab", fontName=POLICE_GRAS, fontSize=Tailles.PETIT, textColor=Couleurs.BLANC,
                         leading=Tailles.PETIT * 1.3),
    "entete_tab_d": _style("entete_tab_d", fontName=POLICE_GRAS, fontSize=Tailles.PETIT, textColor=Couleurs.BLANC,
                           leading=Tailles.PETIT * 1.3, alignment=TA_RIGHT),
    "entete_tab_c": _style("entete_tab_c", fontName=POLICE_GRAS, fontSize=Tailles.PETIT, textColor=Couleurs.BLANC,
                           leading=Tailles.PETIT * 1.3, alignment=TA_CENTER),
    "ttc_libelle": _style("ttc_libelle", fontName=POLICE_GRAS, fontSize=11, textColor=Couleurs.BLANC, leading=14),
    "ttc_valeur": _style("ttc_valeur", fontName=POLICE_GRAS, fontSize=14, textColor=Couleurs.BLANC, leading=17,
                         alignment=TA_RIGHT),
    "lettres": _style("lettres", fontName=POLICE_GRAS, fontSize=9.2, leading=13, textColor=Couleurs.NUIT),
}


def nombre(valeur):
    """Formatage d'affichage : 6 404 232 ; 0,098 (aucun arrondi supplémentaire)."""
    from .dqe_exporters import formater_nombre

    return formater_nombre(valeur)


def fcfa(valeur):
    return f"{nombre(valeur)} FCFA"


def _txt(v):
    return escape(str(v)) if v is not None else ""


def _date_fr(iso):
    from .dqe_exporters import formater_date

    return formater_date(iso) if iso else ""


REF_NON_ATTRIBUEE = ("", "non attribué", "non attribuée")

LIBELLES_USAGE = {
    "habitation": "Habitation", "commerce": "Commerce", "bureau": "Bureaux", "industriel": "Industriel",
    "balcon": "Balcon", "circulation": "Circulation", "toiture_terrasse": "Toiture-terrasse",
    "toiture_inaccessible": "Toiture inaccessible",
}


def reference_devis(projet):
    ref = (projet.get("numero_devis") or "").strip()
    return None if ref.lower() in REF_NON_ATTRIBUEE else ref


# ---------------------------------------------------------------------------
# Logo
# ---------------------------------------------------------------------------

def get_logo(entreprise, hauteur_max=16 * mm, largeur_max=48 * mm):
    """Image du VRAI logo du cabinet, proportions conservées, ou None."""
    chemin = (entreprise or {}).get("logo_path")
    if not chemin or not os.path.exists(chemin):
        return None
    try:
        largeur, hauteur = ImageReader(chemin).getSize()
    except Exception:
        return None
    if not largeur or not hauteur:
        return None
    echelle = min(hauteur_max / hauteur, largeur_max / largeur)
    img = Image(chemin, width=largeur * echelle, height=hauteur * echelle)
    img.hAlign = "LEFT"
    return img


def coordonnees_cabinet(entreprise):
    e = entreprise or {}
    contact = [x.strip() for x in (e.get("email"), e.get("telephone"), e.get("siege_social")) if x and x.strip()]
    legal = [f"{lib} {e[c].strip()}" for c, lib in (("rccm", "RCCM"), ("cc", "CC"), ("cb", "CB"))
             if e.get(c) and e[c].strip()]
    return contact, legal


# ---------------------------------------------------------------------------
# Blocs
# ---------------------------------------------------------------------------

def entete(dqe_data, entreprise):
    projet = dqe_data.get("projet", {})
    e = entreprise or {}
    contact, legal = coordonnees_cabinet(e)
    gauche = []
    logo = get_logo(e)
    if logo:
        gauche += [logo, Spacer(1, 3)]
    if e.get("nom"):
        gauche.append(Paragraph(_txt(e["nom"]), _style("cab", fontName=POLICE_GRAS, fontSize=11,
                                                       leading=14, textColor=Couleurs.NUIT)))
    if contact:
        gauche.append(Paragraph(" • ".join(_txt(c) for c in contact), S["petit"]))
    if legal:
        gauche.append(Paragraph(" • ".join(_txt(c) for c in legal), S["petit"]))

    ref = reference_devis(projet)
    lignes_droite = [
        ("Devis n°", ref if ref else "non attribué"),
        ("Date", _date_fr(projet.get("date_edition"))),
    ]
    droite = Table(
        [[Paragraph(lib.upper(), S["etiquette"]),
          Paragraph(_txt(val), S["droite_gras"] if val and val != "non attribué" else S["petit_droite"])]
         for lib, val in lignes_droite if val],
        colWidths=[22 * mm, 40 * mm],
    )
    droite.setStyle(TableStyle([
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("LINEBELOW", (0, 0), (-1, -2), 0.4, Couleurs.FILET),
        ("TOPPADDING", (0, 0), (-1, -1), 3), ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
        ("LEFTPADDING", (0, 0), (-1, -1), 0), ("RIGHTPADDING", (0, 0), (-1, -1), 0),
    ]))
    t = Table([[gauche or "", droite]], colWidths=[LARGEUR_UTILE - 64 * mm, 64 * mm])
    t.setStyle(TableStyle([
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LEFTPADDING", (0, 0), (-1, -1), 0), ("RIGHTPADDING", (0, 0), (-1, -1), 0),
        ("LINEBELOW", (0, 0), (-1, 0), 1.2, Couleurs.NUIT),
        ("BOTTOMPADDING", (0, 0), (-1, 0), 8),
    ]))
    return [t, Spacer(1, 6 * mm)]


def titre(dqe_data, lots):
    projet = dqe_data.get("projet", {})
    elements = []
    if projet.get("date_edition"):
        elements.append(Paragraph(f"DOCUMENT D'ESTIMATION — ÉDITION DU {_date_fr(projet['date_edition'])}", S["surtitre"]))
    elements.append(Paragraph("DEVIS QUANTITATIF ET ESTIMATIF", S["titre"]))
    elements.append(Spacer(1, 2))
    elements.append(Paragraph(f"Projet : {_txt(projet.get('nom'))}", S["sous_titre"]))
    if lots:
        elements.append(Paragraph(
            ("Lot : " if len(lots) == 1 else "Lots : ") + " · ".join(f"{l['numero']} — {l['nom'].capitalize()}" for l in lots),
            _style("lots", fontSize=10, leading=14, textColor=Couleurs.GRIS)))
    elements.append(Spacer(1, 4 * mm))
    return elements


def infos_projet(dqe_data, lots, entreprise):
    """Cartouche d'informations : seuls les champs réellement disponibles."""
    projet = dqe_data.get("projet", {})
    f = dqe_data.get("finances") or {}
    champs = [
        ("Projet", projet.get("nom")),
        ("Usage", LIBELLES_USAGE.get(projet.get("usage_batiment"), projet.get("usage_batiment"))),
        ("Niveaux", projet.get("nb_niveaux")),
        ("Référence devis", reference_devis(projet)),
        ("Cabinet", (entreprise or {}).get("nom")),
        ("Établi par", projet.get("auteur")),
        ("Date d'édition", _date_fr(projet.get("date_edition"))),
    ]
    champs = [(k, v) for k, v in champs if v not in (None, "")]
    gauche = Table([[Paragraph(k, S["etiquette"]), Paragraph(_txt(v), S["corps_gras"])] for k, v in champs],
                   colWidths=[30 * mm, 70 * mm])
    gauche.setStyle(TableStyle([
        ("LINEBELOW", (0, 0), (-1, -2), 0.4, Couleurs.FILET),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("TOPPADDING", (0, 0), (-1, -1), 2.6), ("BOTTOMPADDING", (0, 0), (-1, -1), 2.6),
        ("LEFTPADDING", (0, 0), (-1, -1), 0),
    ]))

    # Synthèse : montant principal (TTC si calculé, sinon HT, sinon total des lignes).
    if f.get("total_ttc") is not None:
        lib, val = "Montant estimé TTC", f["total_ttc"]
    elif f.get("total_ht") is not None:
        lib, val = "Montant estimé HT", f["total_ht"]
    else:
        lib, val = "Total des ouvrages", dqe_data["total_general"]
    nb_lignes = len(dqe_data.get("lignes", []))
    synthese = Table([
        [Paragraph("SYNTHÈSE", _style("ss", fontName=POLICE_GRAS, fontSize=Tailles.PETIT,
                                      textColor=colors.HexColor("#F0A477")))],
        [Paragraph(lib, _style("sl", fontSize=Tailles.PETIT, textColor=Couleurs.GRIS_MOYEN))],
        [Paragraph(fcfa(val), _style("sv", fontName=POLICE_GRAS, fontSize=15, leading=19, textColor=Couleurs.BLANC))],
        [Paragraph(f"{len(lots)} lot{'s' if len(lots) > 1 else ''} · {nb_lignes} ligne{'s' if nb_lignes > 1 else ''} de prix",
                   _style("sn", fontSize=Tailles.PETIT, textColor=Couleurs.GRIS_MOYEN))],
    ], colWidths=[62 * mm])
    synthese.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), Couleurs.NUIT),
        ("LEFTPADDING", (0, 0), (-1, -1), 10), ("RIGHTPADDING", (0, 0), (-1, -1), 10),
        ("TOPPADDING", (0, 0), (-1, 0), 9), ("BOTTOMPADDING", (0, -1), (-1, -1), 10),
        ("TOPPADDING", (0, 1), (-1, -1), 1), ("BOTTOMPADDING", (0, 0), (-1, -2), 1),
    ]))
    bloc = Table([[[Paragraph("INFORMATIONS DU PROJET", S["surtitre"]), Spacer(1, 2), gauche], synthese]],
                 colWidths=[LARGEUR_UTILE - 66 * mm, 66 * mm])
    bloc.setStyle(TableStyle([
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LEFTPADDING", (0, 0), (-1, -1), 0), ("RIGHTPADDING", (0, 0), (-1, -1), 0),
        ("ALIGN", (1, 0), (1, 0), "RIGHT"),
    ]))
    return [bloc, Spacer(1, 6 * mm)]


COLS = [16 * mm, None, 12 * mm, 20 * mm, 24 * mm, 28 * mm]
COLS[1] = LARGEUR_UTILE - sum(c for c in COLS if c)


def _entete_tableau():
    return [
        Paragraph("N°", S["entete_tab_c"]), Paragraph("DÉSIGNATION", S["entete_tab"]),
        Paragraph("UNITÉ", S["entete_tab_c"]), Paragraph("QUANTITÉ", S["entete_tab_d"]),
        Paragraph("P.U. HT", S["entete_tab_d"]), Paragraph("MONTANT HT", S["entete_tab_d"]),
    ]


def tableau_lot(lot):
    """Titre du lot + tableau numéroté (lot.sous-lot.ligne) + sous-totaux.
    L'en-tête du tableau est répété à chaque page ; aucune ligne n'est coupée."""
    titre_lot = Table([[Paragraph(_txt(lot["label"]), S["section"]),
                        Paragraph(fcfa(lot["sous_total"]), _style("tl", fontName=POLICE_GRAS, fontSize=Tailles.SECTION,
                                                                    alignment=TA_RIGHT, textColor=Couleurs.NUIT))]],
                      colWidths=[LARGEUR_UTILE - 50 * mm, 50 * mm])
    titre_lot.setStyle(TableStyle([
        ("LINEBELOW", (0, 0), (-1, 0), 1.2, Couleurs.NUIT),
        ("LEFTPADDING", (0, 0), (-1, -1), 0), ("RIGHTPADDING", (0, 0), (-1, -1), 0),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
    ]))

    data = [_entete_tableau()]
    st = [
        ("BACKGROUND", (0, 0), (-1, 0), Couleurs.NUIT),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("TOPPADDING", (0, 0), (-1, -1), 4.5), ("BOTTOMPADDING", (0, 0), (-1, -1), 4.5),
        ("LEFTPADDING", (0, 0), (-1, -1), 4), ("RIGHTPADDING", (0, 0), (-1, -1), 4),
    ]
    for i_sl, sl in enumerate(lot["sous_lots"], start=1):
        num_sl = f"{lot['numero']}.{i_sl:02d}"
        titre_sl = sl["libelle"] or ""
        if lot.get("plusieurs_parties"):
            titre_sl = f"{titre_sl} ({sl['partie']})"
        data.append([Paragraph(num_sl, _style("nsl", fontName=POLICE_GRAS, fontSize=Tailles.CORPS, alignment=TA_CENTER,
                                              textColor=Couleurs.BLEU)),
                     Paragraph(_txt(titre_sl).upper(), _style("tsl", fontName=POLICE_GRAS, fontSize=Tailles.PETIT + 0.4,
                                                              textColor=Couleurs.BLEU)), "", "", "", ""])
        r = len(data) - 1
        st += [("SPAN", (1, r), (-1, r)), ("BACKGROUND", (0, r), (-1, r), Couleurs.FOND),
               ("LINEABOVE", (0, r), (-1, r), 0.6, Couleurs.FILET)]
        for i_l, l in enumerate(sl["lignes"], start=1):
            detail = " · ".join(_txt(x) for x in (l.get("formule_quantite"), l.get("type_donnee")) if x)
            designation = _txt(l["designation"]) + (
                f"<br/><font size='{Tailles.PETIT - 0.6}' color='#{Couleurs.GRIS.hexval()[2:]}'>{detail}</font>"
                if detail else "")
            data.append([
                Paragraph(f"{num_sl}.{i_l:02d}", _style("nl", fontSize=Tailles.PETIT, alignment=TA_CENTER,
                                                        textColor=Couleurs.GRIS)),
                Paragraph(designation, S["corps"]),
                Paragraph(_txt(l["unite"]), S["centre"]),
                Paragraph(nombre(l["quantite"]), S["droite"]),
                Paragraph(nombre(l["prix_unitaire"]), S["droite"]),
                Paragraph(nombre(l["montant"]), S["droite_gras"]),
            ])
            r = len(data) - 1
            st.append(("LINEBELOW", (0, r), (-1, r), 0.35, Couleurs.FILET))
            if i_l % 2 == 0:
                st.append(("BACKGROUND", (0, r), (-1, r), Couleurs.FOND_LEGER))
        if len(lot["sous_lots"]) == 1:
            continue  # sous-total identique à celui du lot : non répété
        data.append(["", Paragraph(f"Sous-total {num_sl} — {_txt(sl['libelle'] or '')}", S["petit_droite"]), "", "", "",
                     Paragraph(nombre(sl["sous_total"]), _style("sst", fontName=POLICE_GRAS, fontSize=Tailles.CORPS,
                                                                alignment=TA_RIGHT, textColor=Couleurs.BLEU))])
        r = len(data) - 1
        st += [("SPAN", (1, r), (4, r)), ("LINEABOVE", (4, r), (-1, r), 0.8, Couleurs.BLEU)]

    data.append(["", Paragraph(f"Sous-total Lot {lot['numero']} — {_txt(lot['nom'].capitalize())}",
                               _style("stl", fontName=POLICE_GRAS, alignment=TA_RIGHT, textColor=Couleurs.NUIT)),
                 "", "", Paragraph(fcfa(lot["sous_total"]), _style("stv", fontName=POLICE_GRAS, alignment=TA_RIGHT,
                                                                  textColor=Couleurs.NUIT)), ""])
    r = len(data) - 1
    st += [("SPAN", (1, r), (3, r)), ("SPAN", (4, r), (5, r)), ("LINEABOVE", (0, r), (-1, r), 1, Couleurs.NUIT),
           ("BACKGROUND", (0, r), (-1, r), Couleurs.FOND), ("TOPPADDING", (0, r), (-1, r), 6),
           ("BOTTOMPADDING", (0, r), (-1, r), 6)]

    t = Table(data, colWidths=COLS, repeatRows=1, splitByRow=True)
    t.setStyle(TableStyle(st))
    # Le titre du lot ne reste jamais seul en bas de page : il voyage avec
    # l'en-tête et les premières lignes du tableau.
    return [CondPageBreak(45 * mm), titre_lot, Spacer(1, 4), t, Spacer(1, 6 * mm)]


def recap_lots(dqe_data, lots):
    total = dqe_data["total_general"]
    data = [[Paragraph("LOT", S["entete_tab"]), Paragraph("DÉSIGNATION", S["entete_tab"]),
             Paragraph("PART", S["entete_tab_d"]), Paragraph("MONTANT HT", S["entete_tab_d"])]]
    for l in lots:
        part = f"{round(l['sous_total'] / total * 100, 1):g} %".replace(".", ",") if total else "—"
        data.append([Paragraph(l["numero"], S["corps_gras"]), Paragraph(_txt(l["nom"].capitalize()), S["corps"]),
                     Paragraph(part, S["droite"]), Paragraph(fcfa(l["sous_total"]), S["droite_gras"])])
    t = Table(data, colWidths=[16 * mm, LARGEUR_UTILE - 16 * mm - 22 * mm - 40 * mm, 22 * mm, 40 * mm])
    t.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), Couleurs.NUIT),
        ("LINEBELOW", (0, 1), (-1, -1), 0.35, Couleurs.FILET),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("TOPPADDING", (0, 0), (-1, -1), 4.5), ("BOTTOMPADDING", (0, 0), (-1, -1), 4.5),
    ]))
    return KeepTogether([Paragraph("RÉCAPITULATIF PAR LOT", S["surtitre"]), Spacer(1, 3), t, Spacer(1, 7 * mm)])


LIBELLES_FINANCES = {"TOTAL HT": "Total HT", "TOTAL TTC": "Total TTC", "TVA": "TVA",
                     "DÉBOURSÉ SEC": "Déboursé sec", "MARGE": "Marge"}


def bloc_financier(dqe_data):
    """HT / (déboursé sec, marge) / TVA / TTC, à partir de dqe_data["finances"]
    exactement. Un montant non calculé est écrit comme tel."""
    from .dqe_exporters import lignes_recap_finances

    lignes = lignes_recap_finances(dqe_data)
    largeur = 100 * mm
    rows, st = [], [("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                    ("LEFTPADDING", (0, 0), (-1, -1), 8), ("RIGHTPADDING", (0, 0), (-1, -1), 8),
                    ("TOPPADDING", (0, 0), (-1, -1), 5), ("BOTTOMPADDING", (0, 0), (-1, -1), 5)]
    principal = next((i for i in range(len(lignes) - 1, -1, -1) if isinstance(lignes[i][1], int)), None)
    for i, (lib, val) in enumerate(lignes):
        texte_val = fcfa(val) if isinstance(val, int) else _txt(val)
        if i == principal and lib.startswith("TOTAL TTC"):
            rows.append([Paragraph("TOTAL TTC", S["ttc_libelle"]), Paragraph(texte_val, S["ttc_valeur"])])
            st += [("BACKGROUND", (0, i), (-1, i), Couleurs.NUIT), ("TOPPADDING", (0, i), (-1, i), 9),
                   ("BOTTOMPADDING", (0, i), (-1, i), 9), ("LINEBELOW", (0, i), (-1, i), 2, Couleurs.ACCENT)]
        else:
            gras = lib.startswith("TOTAL") or i == principal
            rows.append([Paragraph(LIBELLES_FINANCES.get(lib.split(" (")[0], lib.capitalize()) + (
                f" ({lib.split(' (', 1)[1]}" if " (" in lib else ""), S["corps_gras"] if gras else S["corps"]),
                         Paragraph(texte_val, S["droite_gras"] if gras and isinstance(val, int) else
                                   (S["droite"] if isinstance(val, int) else S["petit_droite"]))])
            st.append(("LINEBELOW", (0, i), (-1, i), 0.4, Couleurs.FILET))
    t = Table(rows, colWidths=[largeur * 0.42, largeur * 0.58])
    t.setStyle(TableStyle(st))
    gouttiere = 8 * mm
    lettres = montant_lettres(dqe_data, largeur=LARGEUR_UTILE - largeur - gouttiere)
    gauche = [Spacer(1, Tailles.PETIT * 1.5 + 3)] + lettres if lettres else ""
    conteneur = Table([[gauche, "", [Paragraph("RÉCAPITULATIF FINANCIER", S["surtitre"]), Spacer(1, 3), t]]],
                      colWidths=[LARGEUR_UTILE - largeur - gouttiere, gouttiere, largeur])
    conteneur.setStyle(TableStyle([("LEFTPADDING", (0, 0), (-1, -1), 0), ("RIGHTPADDING", (0, 0), (-1, -1), 0),
                                   ("VALIGN", (0, 0), (-1, -1), "TOP")]))
    messages = [Paragraph(_txt(m), S["petit_droite"]) for m in (dqe_data.get("finances") or {}).get("messages", [])]
    return KeepTogether([conteneur] + ([Spacer(1, 3)] + messages if messages else []) + [Spacer(1, 5 * mm)])


def montant_lettres(dqe_data, largeur=None):
    from .dqe_calculator import montant_en_toutes_lettres
    from .dqe_exporters import montant_arrete

    montant, qualif = montant_arrete(dqe_data)
    texte = montant_en_toutes_lettres(montant)
    if not texte:
        return []
    suffixe = {"TTC": "FRANCS CFA TTC", "HT": "FRANCS CFA HORS TAXES"}.get(qualif, f"FRANCS CFA ({qualif.upper()})")
    t = Table([[[Paragraph("Arrêté le présent devis à la somme de :", S["etiquette"]), Spacer(1, 3),
                 Paragraph(f"{_txt(texte).upper()} {suffixe}.", S["lettres"]),
                 Paragraph(f"soit {fcfa(montant)} {qualif}", S["petit"])]]],
              colWidths=[largeur or LARGEUR_UTILE])
    t.setStyle(TableStyle([
        ("LINEBEFORE", (0, 0), (0, 0), 2.5, Couleurs.ACCENT),
        ("BACKGROUND", (0, 0), (-1, -1), Couleurs.FOND),
        ("LEFTPADDING", (0, 0), (-1, -1), 10), ("TOPPADDING", (0, 0), (-1, -1), 8),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
    ]))
    return [t]


def infos_techniques(dqe_data):
    """Uniquement les hypothèses RÉELLEMENT utilisées (renvoyées par le calcul)."""
    calcul = dqe_data.get("hypotheses_projet") or []
    metre = dqe_data.get("hypotheses") or []
    if not calcul and not metre:
        return []
    blocs = [Paragraph("INFORMATIONS TECHNIQUES", S["surtitre"]), Spacer(1, 2)]
    if calcul:
        blocs.append(Paragraph("Méthode : pré-dimensionnement BAEL 91 modifié 99 — hypothèses de calcul", S["corps_gras"]))
        blocs += [Paragraph(f"• {_txt(h)}", S["petit"]) for h in calcul]
        blocs.append(Spacer(1, 3))
    if metre:
        blocs.append(Paragraph("Hypothèses de métré", S["corps_gras"]))
        blocs += [Paragraph(f"• {_txt(h)}", S["petit"]) for h in metre]
    t = Table([[blocs]], colWidths=[LARGEUR_UTILE])
    t.setStyle(TableStyle([("BOX", (0, 0), (-1, -1), 0.5, Couleurs.FILET),
                           ("LEFTPADDING", (0, 0), (-1, -1), 10), ("RIGHTPADDING", (0, 0), (-1, -1), 10),
                           ("TOPPADDING", (0, 0), (-1, -1), 8), ("BOTTOMPADDING", (0, 0), (-1, -1), 8)]))
    return [KeepTogether([t]), Spacer(1, 7 * mm)]


def cartouche(dqe_data, lots):
    """Cartouche de validation : données réelles ; « Vérifié par » et le visa
    sont des zones à remplir à la main (jamais pré-remplies)."""
    projet = dqe_data.get("projet", {})
    lots_txt = ", ".join(l["numero"] for l in lots)
    cell = lambda lib, val: [Paragraph(lib, S["etiquette"]), Paragraph(_txt(val) if val else "", S["corps_gras"])]  # noqa: E731
    ref = reference_devis(projet)
    data = [
        [cell("PROJET", projet.get("nom")), cell("LOT" + ("S" if len(lots) > 1 else ""), lots_txt),
         cell("DOCUMENT", "DQE"), cell("RÉFÉRENCE", ref or "non attribuée"),
         cell("DATE", _date_fr(projet.get("date_edition"))), cell("ÉTABLI PAR", projet.get("auteur"))],
        [cell("VÉRIFIÉ PAR", None), "", cell("DATE DE VALIDATION", None), "", cell("VISA / CACHET", None), ""],
    ]
    w = LARGEUR_UTILE / 6
    t = Table(data, colWidths=[w * 1.35, w * 0.6, w * 0.75, w * 1.1, w * 0.85, w * 1.35], rowHeights=[None, 15 * mm])
    t.setStyle(TableStyle([
        ("SPAN", (0, 1), (1, 1)), ("SPAN", (2, 1), (3, 1)), ("SPAN", (4, 1), (5, 1)),
        ("BOX", (0, 0), (-1, -1), 0.9, Couleurs.NUIT),
        ("INNERGRID", (0, 0), (-1, -1), 0.4, Couleurs.FILET),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LEFTPADDING", (0, 0), (-1, -1), 5), ("RIGHTPADDING", (0, 0), (-1, -1), 4),
        ("TOPPADDING", (0, 0), (-1, -1), 4), ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
    ]))
    return KeepTogether([t])


# ---------------------------------------------------------------------------
# Pages : en-tête courant, pied de page, pagination « Page x / n »
# ---------------------------------------------------------------------------

class CanevasNumerote(pdfcanvas.Canvas):
    """Deux passes : les pages sont mémorisées puis numérotées à la sauvegarde,
    pour écrire le nombre total réel de pages."""

    contexte = {}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._pages = []

    def showPage(self):
        self._pages.append(dict(self.__dict__))
        self._startPage()

    def save(self):
        total = len(self._pages)
        for etat in self._pages:
            self.__dict__.update(etat)
            self._decorer(total)
            super().showPage()
        super().save()

    def _decorer(self, total):
        c = self.contexte
        page = self._pageNumber
        gris = Couleurs.GRIS
        # Pied de page
        y = MARGE_BAS - 9 * mm
        self.setStrokeColor(Couleurs.FILET)
        self.setLineWidth(0.5)
        self.line(MARGE_X, y + 6.5 * mm, LARGEUR_PAGE - MARGE_X, y + 6.5 * mm)
        self.setFillColor(Couleurs.NUIT)
        self.setFont(POLICE_GRAS, Tailles.PIED)
        if c.get("cabinet"):
            self.drawString(MARGE_X, y + 3 * mm, c["cabinet"])
        self.setFillColor(gris)
        self.setFont(POLICE, Tailles.PIED)
        if c.get("contact"):
            self.drawString(MARGE_X, y, c["contact"])
        self.drawRightString(LARGEUR_PAGE - MARGE_X, y + 3 * mm, c.get("document", ""))
        self.setFont(POLICE_GRAS, Tailles.PIED)
        self.setFillColor(Couleurs.NUIT)
        self.drawRightString(LARGEUR_PAGE - MARGE_X, y, f"Page {page} / {total}")
        # En-tête courant (pages suivantes)
        if page > 1:
            yh = HAUTEUR_PAGE - MARGE_HAUT + 4 * mm
            self.setFont(POLICE_GRAS, Tailles.PIED)
            self.setFillColor(Couleurs.NUIT)
            self.drawString(MARGE_X, yh, "DEVIS QUANTITATIF ET ESTIMATIF")
            self.setFont(POLICE, Tailles.PIED)
            self.setFillColor(gris)
            self.drawRightString(LARGEUR_PAGE - MARGE_X, yh, c.get("entete_droite", ""))
            self.setStrokeColor(Couleurs.FILET)
            self.line(MARGE_X, yh - 2.5 * mm, LARGEUR_PAGE - MARGE_X, yh - 2.5 * mm)


# ---------------------------------------------------------------------------
# Assemblage
# ---------------------------------------------------------------------------

def generer_pdf(dqe_data, entreprise=None, lots=None) -> BytesIO:
    from .dqe_exporters import regrouper_par_lot

    lots = lots if lots is not None else regrouper_par_lot(dqe_data)
    lots = [l for l in lots if l["lignes"]]
    projet = dqe_data.get("projet", {})
    contact, _ = coordonnees_cabinet(entreprise)
    ref = reference_devis(projet)

    class Canevas(CanevasNumerote):
        contexte = {
            "cabinet": (entreprise or {}).get("nom") or "",
            "contact": " • ".join(contact),
            "document": f"DQE — {projet.get('nom', '')}",
            "entete_droite": " · ".join(x for x in (projet.get("nom"), f"Devis n° {ref}" if ref else None,
                                                    _date_fr(projet.get("date_edition"))) if x),
        }

    buffer = BytesIO()
    doc = SimpleDocTemplate(
        buffer, pagesize=A4, leftMargin=MARGE_X, rightMargin=MARGE_X, topMargin=MARGE_HAUT + 4 * mm,
        bottomMargin=MARGE_BAS, title=f"DQE — {projet.get('nom', '')}",
        author=(entreprise or {}).get("nom") or projet.get("auteur") or "", subject="Devis quantitatif et estimatif",
    )
    story = []
    story += entete(dqe_data, entreprise)
    story += titre(dqe_data, lots)
    story += infos_projet(dqe_data, lots, entreprise)
    for lot in lots:
        story += tableau_lot(lot)
    if len(lots) > 1:
        story.append(recap_lots(dqe_data, lots))
    story.append(bloc_financier(dqe_data))
    story += infos_techniques(dqe_data)
    story.append(cartouche(dqe_data, lots))
    doc.build(story, canvasmaker=Canevas)
    buffer.seek(0)
    return buffer
