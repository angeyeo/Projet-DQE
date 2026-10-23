"""
Note de calcul (issue #96) : RENDU PDF uniquement.

Ne calcule rien : tout vient de construire_note() (note_calcul.py). Seul
traitement : l'écriture française des nombres (virgule décimale). Même
charte que le PDF du DQE (pdf_dqe.py).
"""

import re
from io import BytesIO

from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.platypus import CondPageBreak, KeepTogether, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

from .pdf_dqe import (
    LARGEUR_UTILE, MARGE_BAS, MARGE_HAUT, MARGE_X, POLICE, POLICE_GRAS, S, CanevasNumerote, Couleurs, Tailles,
    _style, _txt, nombre,
)

COULEURS_ORIGINE = {"calculé": Couleurs.BLEU, "saisi": Couleurs.ACCENT, "estimé": Couleurs.GRIS}
DECIMALE = re.compile(r"(?<=\d)\.(?=\d)")

ST = {
    "trace": _style("trace", fontSize=Tailles.PETIT, leading=Tailles.PETIT * 1.35),
    "trace_d": _style("trace_d", fontSize=Tailles.PETIT, leading=Tailles.PETIT * 1.35, alignment=2),
    "trace_g": _style("trace_g", fontName=POLICE_GRAS, fontSize=Tailles.PETIT, leading=Tailles.PETIT * 1.35),
    "element": _style("element", fontName=POLICE_GRAS, fontSize=9.4, leading=12, textColor=Couleurs.NUIT),
    "mention": _style("mention", fontSize=Tailles.PETIT + 0.3, leading=(Tailles.PETIT + 0.3) * 1.45,
                      textColor=Couleurs.TEXTE),
}


def fr(texte):
    """Texte d'une trace : virgule décimale, échappé pour reportlab."""
    return _txt(DECIMALE.sub(",", str(texte)))


def nombre_note(v):
    """Nombre tel que le moteur l'a enregistré (jusqu'à 4 décimales, déjà
    arrondi par le moteur), virgule décimale, espace des milliers. Le
    formatage du DQE arrondit à 3 décimales : 0,0745 y deviendrait 0,074."""
    if isinstance(v, int):
        return nombre(v)
    texte = f"{v:,.4f}".rstrip("0").rstrip(".")
    return texte.replace(",", " ").replace(".", ",")


def valeur(v):
    if isinstance(v, bool):
        return "oui" if v else "non"
    if isinstance(v, (int, float)):
        return nombre_note(v)
    return fr(v)


def origine(o):
    if not o:
        return Paragraph("—", ST["trace"])
    c = COULEURS_ORIGINE.get(o, Couleurs.GRIS).hexval()[2:]
    return Paragraph(f'<font color="#{c}"><b>{_txt(o)}</b></font>', ST["trace"])


def _table(data, largeurs, entete=True, zebre=True):
    t = Table(data, colWidths=largeurs, repeatRows=1 if entete else 0)
    style = [
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LEFTPADDING", (0, 0), (-1, -1), 4), ("RIGHTPADDING", (0, 0), (-1, -1), 4),
        ("TOPPADDING", (0, 0), (-1, -1), 2.5), ("BOTTOMPADDING", (0, 0), (-1, -1), 2.5),
        ("LINEBELOW", (0, 0), (-1, -1), 0.3, Couleurs.FILET),
    ]
    if entete:
        style += [("BACKGROUND", (0, 0), (-1, 0), Couleurs.NUIT)]
    if zebre:
        style += [("ROWBACKGROUNDS", (0, 1 if entete else 0), (-1, -1), [Couleurs.BLANC, Couleurs.FOND_LEGER])]
    t.setStyle(TableStyle(style))
    return t


def _entete(*libelles, droite=()):
    return [Paragraph(_txt(l), S["entete_tab_d"] if i in droite else S["entete_tab"]) for i, l in enumerate(libelles)]


def section(numero, titre):
    return [CondPageBreak(30 * mm), Spacer(1, 4 * mm),
            Paragraph(f"{numero}. {_txt(titre).upper()}", S["section"]), Spacer(1, 2 * mm)]


def tableau_donnees(lignes):
    w = LARGEUR_UTILE
    data = [_entete("Donnée", "Valeur", "Origine", "Précision")]
    for d in lignes:
        v = valeur(d["valeur"]) + (f" {_txt(d['unite'])}" if d["unite"] else "")
        data.append([Paragraph(_txt(d["libelle"]), ST["trace"]), Paragraph(v, ST["trace_g"]), origine(d["origine"]),
                     Paragraph(_txt(d["detail"]), ST["trace"])])
    return _table(data, [w * 0.36, w * 0.17, w * 0.1, w * 0.37])


def page_de_garde(note):
    p, e, st = note["projet"], note["edition"], note["statut"]
    blocs = []
    if p["cabinet"]:
        blocs.append(Paragraph(_txt(p["cabinet"]), _style("cab", fontName=POLICE_GRAS, fontSize=11, leading=14,
                                                            textColor=Couleurs.NUIT)))
    blocs += [Spacer(1, 6 * mm), Paragraph("NOTE DE CALCUL", S["surtitre"]),
              Paragraph(_txt(p["nom"]), S["titre"]), Spacer(1, 2 * mm),
              Paragraph("Pré-dimensionnement et métré — " + _txt(e["norme"]), S["sous_titre"]), Spacer(1, 5 * mm)]
    cell = lambda lib, val: [Paragraph(lib, S["etiquette"]), Paragraph(_txt(val), S["corps_gras"])]  # noqa: E731
    statut = (f"PROVISOIRE — {st['valides']} / {st['elements']} éléments validés" if st["provisoire"]
              else f"Définitive — {st['elements']} éléments validés")
    w = LARGEUR_UTILE / 3
    t = Table([
        [cell("DEVIS N°", p["numero_devis"] or "non attribué"), cell("DATE D'ÉDITION", e["date"]),
         cell("ÉTABLIE PAR", e["auteur"] or "—")],
        [cell("VERSION DU MOTEUR", e["version_moteur"]), cell("STATUT", statut),
         cell("ORIGINE DE LA STRUCTURE", p["source_structure"])],
    ], colWidths=[w, w, w])
    t.setStyle(TableStyle([("BOX", (0, 0), (-1, -1), 0.9, Couleurs.NUIT),
                           ("INNERGRID", (0, 0), (-1, -1), 0.4, Couleurs.FILET), ("VALIGN", (0, 0), (-1, -1), "TOP"),
                           ("LEFTPADDING", (0, 0), (-1, -1), 6), ("TOPPADDING", (0, 0), (-1, -1), 5),
                           ("BOTTOMPADDING", (0, 0), (-1, -1), 5)]))
    blocs += [t, Spacer(1, 5 * mm)]
    mention = Table([[Paragraph("<b>Responsabilité.</b> " + _txt(note["mention"]), ST["mention"])]],
                    colWidths=[LARGEUR_UTILE])
    mention.setStyle(TableStyle([("BACKGROUND", (0, 0), (-1, -1), Couleurs.FOND),
                                 ("LINEBEFORE", (0, 0), (0, -1), 2, Couleurs.ACCENT),
                                 ("LEFTPADDING", (0, 0), (-1, -1), 8), ("TOPPADDING", (0, 0), (-1, -1), 6),
                                 ("BOTTOMPADDING", (0, 0), (-1, -1), 6)]))
    blocs += [mention, Spacer(1, 4 * mm)]
    legende = ("<b>Origine des valeurs</b> — "
               f'<font color="#{COULEURS_ORIGINE["calculé"].hexval()[2:]}"><b>calculé</b></font> : produit par le moteur ; '
               f'<font color="#{COULEURS_ORIGINE["saisi"].hexval()[2:]}"><b>saisi</b></font> : donnée de l\'utilisateur ou '
               "valeur modifiée par l'ingénieur à la validation ; "
               f'<font color="#{COULEURS_ORIGINE["estimé"].hexval()[2:]}"><b>estimé</b></font> : valeur par défaut, '
               "valeur normative ou ratio.")
    blocs.append(Paragraph(legende, S["petit"]))
    for a in note["avertissements"]:
        blocs += [Spacer(1, 2 * mm), Paragraph(f'<font color="#{Couleurs.ACCENT.hexval()[2:]}"><b>⚠</b></font> '
                                               + _txt(a), S["corps"])]
    return blocs


def fiche_element(f):
    w = LARGEUR_UTILE
    infos = [f"{_txt(f['libelle_type'])}", f"statut : {_txt(f['libelle_statut'])}",
             f"géométrie : {_txt(f['origine_geometrie'])}"]
    if f["position"]:
        infos.insert(1, f"position X {nombre(f['position'][0])} m ; Y {nombre(f['position'][1])} m")
    if f["portee_m"]:
        infos.insert(1, f"portée {nombre(f['portee_m'])} m")
    if f["nombre_identiques"] > 1:
        infos.append(f"× {f['nombre_identiques']} (niveaux identiques)")
    blocs = [Paragraph(_txt(f["identifiant"]), ST["element"]), Paragraph(" · ".join(infos), S["petit"]),
             Spacer(1, 1.5 * mm)]

    if f["trace"]:
        data = [_entete("Étape", "Formule", "Application numérique", "Résultat", droite=(3,))]
        for t in f["trace"]:
            data.append([Paragraph(fr(t.get("etape", "")), ST["trace_g"]), Paragraph(fr(t.get("formule", "")), ST["trace"]),
                         Paragraph(fr(t.get("calcul", "")) or "—", ST["trace"]),
                         Paragraph(f"{valeur(t.get('resultat'))} {fr(t.get('unite', '')) if t.get('unite') != '—' else ''}",
                                   ST["trace_d"])])
        blocs.append(_table(data, [w * 0.18, w * 0.32, w * 0.33, w * 0.17]))
    else:
        blocs.append(Paragraph("Détail de calcul non enregistré pour cet élément : seuls les résultats sont donnés.",
                               S["petit"]))
    blocs.append(Spacer(1, 1.5 * mm))

    if f["resultats"]:
        data = [_entete("Résultat retenu", "Valeur", "Origine", "Précision")]
        for r in f["resultats"]:
            v = valeur(r["valeur"]) + (f" {_txt(r['unite'])}" if r["unite"] else "")
            data.append([Paragraph(_txt(r["libelle"]), ST["trace"]), Paragraph(v, ST["trace_g"]), origine(r["origine"]),
                         Paragraph(_txt(r["detail"]), ST["trace"])])
        blocs.append(_table(data, [w * 0.33, w * 0.22, w * 0.1, w * 0.35]))

    q = f["quantites"]
    if q.get("manquants"):
        blocs.append(Paragraph("Quantités non calculées : " + _txt(", ".join(q["manquants"])), S["petit"]))
    else:
        fois = f" (× {q['nombre_identiques']})" if q["nombre_identiques"] > 1 else ""
        data = [_entete("Quantité" + fois, "Formule", "Valeur", "Origine", droite=(2,)),
                [Paragraph("Béton", ST["trace"]), Paragraph(fr(q["formule_beton"]), ST["trace"]),
                 Paragraph(f"{nombre(round(q['beton_m3'], 3))} m³", ST["trace_d"]), origine("calculé")],
                [Paragraph("Coffrage", ST["trace"]), Paragraph(fr(q["formule_coffrage"]), ST["trace"]),
                 Paragraph(f"{nombre(round(q['coffrage_m2'], 2))} m²", ST["trace_d"]), origine("calculé")],
                [Paragraph("Acier", ST["trace"]), Paragraph(_txt(q["detail_acier"]), ST["trace"]),
                 Paragraph(f"{nombre(round(q['acier_kg'], 2))} kg", ST["trace_d"]), origine(q["origine_acier"])]]
        blocs += [Spacer(1, 1.5 * mm), _table(data, [w * 0.22, w * 0.43, w * 0.2, w * 0.15])]
        if q["hypothese_beton"]:
            blocs.append(Paragraph(_txt(q["hypothese_beton"]), S["petit"]))
    return [CondPageBreak(45 * mm), KeepTogether(blocs[:3]), *blocs[3:], Spacer(1, 5 * mm)]


def recapitulatif(note):
    w = LARGEUR_UTILE
    data = [_entete("Type", "Éléments", "Béton (m³)", "Coffrage (m²)", "Acier (kg)", droite=(1, 2, 3, 4))]
    for g in note["groupes"]:
        qs = [f["quantites"] for f in g["elements"] if not f["quantites"].get("manquants")]
        data.append([Paragraph(_txt(g["titre"]), ST["trace"]), Paragraph(str(len(g["elements"])), ST["trace_d"]),
                     Paragraph(nombre(round(sum(q["beton_m3"] for q in qs), 3)), ST["trace_d"]),
                     Paragraph(nombre(round(sum(q["coffrage_m2"] for q in qs), 2)), ST["trace_d"]),
                     Paragraph(nombre(round(sum(q["acier_kg"] for q in qs), 2)), ST["trace_d"])])
    t = note["totaux"]
    data.append([Paragraph("<b>Total</b>", ST["trace"]), Paragraph("", ST["trace"]),
                 Paragraph(f"<b>{nombre(round(t['beton_m3'], 3))}</b>", ST["trace_d"]),
                 Paragraph(f"<b>{nombre(round(t['coffrage_m2'], 2))}</b>", ST["trace_d"]),
                 Paragraph(f"<b>{nombre(round(t['acier_calcule_kg'] + t['acier_estime_kg'], 2))}</b>", ST["trace_d"])])
    blocs = [KeepTogether([_table(data, [w * 0.32, w * 0.12, w * 0.18, w * 0.19, w * 0.19])]), Spacer(1, 2 * mm),
             Paragraph(f"Dont acier calculé par le moteur : {nombre(round(t['acier_calcule_kg'], 2))} kg ; "
                       f"acier estimé au ratio : {nombre(round(t['acier_estime_kg'], 2))} kg.", S["petit"])]
    return blocs


def visa():
    cell = lambda lib: [Paragraph(lib, S["etiquette"])]  # noqa: E731
    t = Table([[cell("VÉRIFIÉ PAR (ingénieur structure)"), cell("DATE"), cell("VISA / CACHET")]],
              colWidths=[LARGEUR_UTILE * 0.45, LARGEUR_UTILE * 0.2, LARGEUR_UTILE * 0.35], rowHeights=[20 * mm])
    t.setStyle(TableStyle([("BOX", (0, 0), (-1, -1), 0.9, Couleurs.NUIT),
                           ("INNERGRID", (0, 0), (-1, -1), 0.4, Couleurs.FILET), ("VALIGN", (0, 0), (-1, -1), "TOP")]))
    return [Spacer(1, 6 * mm), KeepTogether([t])]


def exporter_note_pdf(note) -> BytesIO:
    p = note["projet"]

    class Canevas(CanevasNumerote):
        contexte = {
            "cabinet": p["cabinet"],
            "contact": f"Version du moteur {note['edition']['version_moteur']} · {note['edition']['norme']}",
            "document": f"Note de calcul — {p['nom']}",
            "titre_courant": "NOTE DE CALCUL",
            "entete_droite": f"{p['nom']} · {note['edition']['date']}",
        }

    buffer = BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=A4, leftMargin=MARGE_X, rightMargin=MARGE_X,
                            topMargin=MARGE_HAUT + 4 * mm, bottomMargin=MARGE_BAS,
                            title=f"Note de calcul — {p['nom']}", author=p["cabinet"] or "",
                            subject="Note de calcul (pré-dimensionnement BAEL 91 mod. 99)")
    story = page_de_garde(note)
    story += section(1, "Données d'entrée") + [tableau_donnees(note["donnees_entree"])]
    story += section(2, "Matériaux et coefficients") + [tableau_donnees(note["materiaux"])]
    story += section(3, "Combinaisons d'actions") + [Paragraph("• " + fr(c), S["corps"]) for c in note["combinaisons"]]
    story += section(4, "Hypothèses du moteur") + [Paragraph("• " + fr(h), S["petit"]) for h in note["hypotheses"]]
    n = 5
    for g in note["groupes"]:
        story += section(n, f"{g['titre']} ({len(g['elements'])})")
        for f in g["elements"]:
            story += fiche_element(f)
        n += 1
    story += section(n, "Récapitulatif des quantités") + recapitulatif(note) + visa()
    doc.build(story, canvasmaker=Canevas)
    buffer.seek(0)
    return buffer
