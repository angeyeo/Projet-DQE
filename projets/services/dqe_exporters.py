"""
Génération des exports DQE (PDF via reportlab, Excel via openpyxl) à
partir de la structure commune produite par calculer_projet_dqe.

Structure attendue pour `dqe_data` (voir dqe_calculator.calculer_projet_dqe) :
    {
        "projet": {"id", "nom", "description", "usage_batiment",
                   "nb_niveaux", "numero_devis", "date_edition"},
        "lignes": [...],
        "lots": [{"lot": <code>, "lignes": [...], "sous_total": int}, ...],
        "sous_totaux": {...},   # par catégorie (béton/coffrage/acier)
        "total_general": int,
        "montant_lettres": str,
        "devise": "FCFA",
    }

Les deux exports regroupent les lignes par LOT (façon CIMBAT) : un
récapitulatif général (un total par lot) suivi du détail de chaque lot.

`entreprise` est un dict optionnel (voir views._entreprise_export_dict)
permettant de personnaliser l'en-tête avec le logo et les coordonnées de
l'utilisateur. Absent ou vide, l'en-tête société est simplement omis.
"""

import logging
from io import BytesIO
from decimal import Decimal
from datetime import datetime


from openpyxl import Workbook
from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
from openpyxl.drawing.image import Image as XLImage


# Nom d'affichage générique par numéro de lot (les deux sous-lots
# GROS_OEUVRE_INFRA / GROS_OEUVRE_SUPER du modèle sont fusionnés sous le
# même numéro "02" pour l'affichage, comme dans le DQE de référence).
LOT_NOMS = {
    "00": "GÉNÉRALITÉS",
    "01": "TERRASSEMENT",
    "02": "GROS ŒUVRE",
    "03": "ÉTANCHÉITÉ",
    "04": "PLOMBERIE",
    "05": "ASSAINISSEMENT",
    "06": "ÉLECTRICITÉ",
    "07": "CHARPENTE",
    "08": "COUVERTURE",
    "09": "MENUISERIE BOIS",
    "10": "MENUISERIE MÉTALLIQUE ET ALUMINIUM",
    "11": "REVÊTEMENTS DE SOLS ET MURS",
    "12": "PEINTURE",
    "13": "FAUX PLAFOND",
    "14": "VRD",
    "15": "DIVERS",
}



from .dqe_calculator import montant_en_toutes_lettres  # noqa: E402
from .decomposition_prix import totaux as totaux_decomposition  # noqa: E402


def lignes_recap_finances(dqe_data):
    """Lignes de récapitulatif (libellé, montant ou texte) issues de
    dqe_data["finances"] -- aucun taux supposé : un montant non calculable
    est écrit en clair comme tel."""
    f = dqe_data.get("finances") or {}
    total = dqe_data["total_general"]
    if not f:
        return [("TOTAL HT", total)]
    rows = []
    if f.get("nature_prix") == "debourse_sec":
        rows.append(("DÉBOURSÉ SEC", f["debourse_sec"]))
        if f.get("montant_marge") is not None:
            rows.append((f"MARGE ({f['taux_marge_pct']:g} %)", f["montant_marge"]))
    rows.append(("TOTAL HT", f["total_ht"] if f.get("total_ht") is not None else "non calculé (marge non renseignée)"))
    if f.get("total_ttc") is not None:
        rows.append((f"TVA ({f['taux_tva_pct']:g} %)", f["montant_tva"]))
        rows.append(("TOTAL TTC", f["total_ttc"]))
    elif f.get("total_ht") is not None:
        rows.append(("TOTAL TTC", "non calculé (TVA non renseignée)"))
    return rows


def montant_arrete(dqe_data):
    """(montant, qualificatif) pour la phrase « Arrêté le présent devis »."""
    f = dqe_data.get("finances") or {}
    if f.get("total_ttc") is not None:
        return f["total_ttc"], "TTC"
    if f.get("total_ht") is not None:
        return f["total_ht"], "HT"
    return dqe_data["total_general"], "déboursé sec"

def formater_nombre(valeur) -> str:
    """Formate un nombre avec un espace comme séparateur des milliers."""
    if valeur is None:
        return "0"
    if isinstance(valeur, (int, Decimal)):
        if isinstance(valeur, Decimal) and valeur != valeur.to_integral_value():
            valeur = float(valeur)
        else:
            return f"{int(valeur):,}".replace(",", " ")
    texte = f"{valeur:,.3f}".rstrip("0").rstrip(".")
    return texte.replace(",", " ").replace(".", ",")


def formater_date(date_iso: str) -> str:
    """'2026-08-19' -> '19/08/2026'. Retourne la valeur brute si non parsable."""
    try:
        return datetime.strptime(date_iso, "%Y-%m-%d").strftime("%d/%m/%Y")
    except (ValueError, TypeError):
        return date_iso or ""


def _numero_lot(code_lot: str) -> str:
    """'lot_02_gros_oeuvre_superstructure' -> '02'."""
    parts = code_lot.split("_")
    if len(parts) >= 2 and parts[0] == "lot":
        return parts[1]
    return "99"


def decomposition_active(dqe_data: dict) -> bool:
    """Vrai si au moins une ligne a ses parts matériaux / main-d'œuvre
    (issue #92) : les colonnes ne sont ajoutées qu'à ce moment-là."""
    return any(l.get("decomposition") == "decompose" for l in dqe_data.get("lignes", []))


def regrouper_par_lot(dqe_data: dict) -> list:
    """
    Fusionne dqe_data["lots"] par numéro de lot (deux sous-lots Gros
    Œuvre Infra/Super comptent comme un seul "LOT 02") et retourne une
    liste ordonnée de dicts :
        [{"numero": "00", "nom": "GÉNÉRALITÉS",
          "label": "LOT 00 — GÉNÉRALITÉS",
          "lignes": [...], "sous_total": int}, ...]
    """
    groupes = {}
    for lot_entry in dqe_data.get("lots", []):
        numero = _numero_lot(lot_entry["lot"])
        groupe = groupes.setdefault(numero, {"lignes": [], "sous_total": 0, "sous_lots": [], "parties": []})
        groupe["lignes"].extend(lot_entry["lignes"])
        groupe["sous_total"] += lot_entry["sous_total"]
        groupe["parties"].append(lot_entry.get("libelle") or lot_entry["lot"])
        for sl in lot_entry.get("sous_lots") or [{"libelle": lot_entry.get("libelle"), "lignes": lot_entry["lignes"],
                                                 "sous_total": lot_entry["sous_total"]}]:
            groupe["sous_lots"].append(dict(sl, partie=lot_entry.get("libelle") or lot_entry["lot"],
                                            decomposition=sl.get("decomposition") or totaux_decomposition(sl["lignes"])))

    resultat = []
    for numero in sorted(groupes.keys()):
        nom = LOT_NOMS.get(numero, numero)
        resultat.append({
            "numero": numero,
            "nom": nom,
            "label": f"LOT {numero} — {nom}",
            "lignes": groupes[numero]["lignes"],
            "sous_lots": groupes[numero]["sous_lots"],
            "plusieurs_parties": len(groupes[numero]["parties"]) > 1,
            "sous_total": groupes[numero]["sous_total"],
            "decomposition": totaux_decomposition(groupes[numero]["lignes"]),
        })
    return resultat


def _parts_excel(ws, row, d, font, fill=None):
    """Sous-total matériaux / main-d'œuvre dans les colonnes F et G."""
    for col, v in ((6, d["materiaux"]), (7, d["main_oeuvre"])):
        c = ws.cell(row=row, column=col, value=v)
        c.font = font
        c.number_format = "#,##0"
        c.alignment = Alignment(horizontal="right")
        if fill is not None:
            c.fill = fill


def _entreprise_champ(entreprise: dict, cle: str) -> str:
    if not entreprise:
        return ""
    return (entreprise.get(cle) or "").strip()


# ---------------------------------------------------------------------------
# PDF
# ---------------------------------------------------------------------------

def exporter_dqe_pdf(dqe_data: dict, entreprise: dict = None) -> BytesIO:
    """PDF du DQE -- rendu délégué à pdf_dqe (présentation uniquement :
    aucune valeur n'est recalculée)."""
    from .pdf_dqe import generer_pdf

    return generer_pdf(dqe_data, entreprise=entreprise, lots=regrouper_par_lot(dqe_data))


# ---------------------------------------------------------------------------
# Excel
# ---------------------------------------------------------------------------

def _feuille_nom_unique(wb: Workbook, base: str) -> str:
    """openpyxl limite les noms de feuille à 31 caractères et refuse les doublons."""
    base = base[:31] or "Lot"
    nom = base
    i = 2
    while nom in wb.sheetnames:
        suffixe = f" ({i})"
        nom = base[: 31 - len(suffixe)] + suffixe
        i += 1
    return nom


def exporter_dqe_excel(dqe_data: dict, entreprise: dict = None) -> BytesIO:
    """
    Génère le classeur Excel du DQE : une feuille "Récapitulatif" (en-tête
    société + total par lot) puis une feuille de détail par lot.
    """
    lots = regrouper_par_lot(dqe_data)
    projet = dqe_data.get("projet", {})

    font_title = Font(name="Calibri", size=16, bold=True, color="2C3E50")
    font_bold = Font(name="Calibri", size=11, bold=True)
    font_header = Font(name="Calibri", size=11, bold=True, color="FFFFFF")
    font_normal = Font(name="Calibri", size=11)
    font_small = Font(name="Calibri", size=9, color="555555")

    fill_header = PatternFill(start_color="2C3E50", end_color="2C3E50", fill_type="solid")
    fill_total = PatternFill(start_color="ECF0F1", end_color="ECF0F1", fill_type="solid")
    fill_total_general = PatternFill(start_color="FFF200", end_color="FFF200", fill_type="solid")

    thin_border = Border(
        left=Side(style='thin', color='BDC3C7'), right=Side(style='thin', color='BDC3C7'),
        top=Side(style='thin', color='BDC3C7'), bottom=Side(style='thin', color='BDC3C7'),
    )

    wb = Workbook()

    # ---- Feuille Récapitulatif ------------------------------------------
    ws = wb.active
    ws.title = "Récapitulatif"
    ws.views.sheetView[0].showGridLines = True

    row = 1
    logo_path = _entreprise_champ(entreprise, "logo_path")
    if logo_path:
        try:
            img = XLImage(logo_path)
            img.height = 70
            img.width = 120
            ws.add_image(img, "A1")
            row = 6
        except Exception:  # logo illisible : export sans logo, mais tracé
            logging.getLogger(__name__).warning("Logo du cabinet illisible pour l'export Excel : %s", logo_path)

    nom_societe = _entreprise_champ(entreprise, "nom")
    if nom_societe:
        ws.cell(row=row, column=1, value=nom_societe).font = font_bold
        row += 1
        for cle, prefixe in [("siege_social", "Siège social : "), ("telephone", "Tél : "), ("email", "Email : ")]:
            valeur = _entreprise_champ(entreprise, cle)
            if valeur:
                ws.cell(row=row, column=1, value=f"{prefixe}{valeur}").font = font_small
                row += 1
        row += 1

    ws.cell(row=row, column=1, value="DEVIS QUANTITATIF ET ESTIMATIF (DQE)").font = font_title
    row += 1
    ws.cell(row=row, column=1, value=f"Devis N° {projet.get('numero_devis', '')} — Édition du {formater_date(projet.get('date_edition', ''))}").font = font_normal
    row += 1
    if projet.get("auteur"):
        ws.cell(row=row, column=1, value=f"Établi par {projet['auteur']}").font = font_small
        row += 1
    titre_projet = projet.get("nom", "")
    if projet.get("description"):
        titre_projet += f" — {projet['description']}"
    ws.cell(row=row, column=1, value=titre_projet).font = font_bold
    row += 2

    avec_parts = decomposition_active(dqe_data)
    headers = ["N°", "Désignation", f"Montant ({dqe_data.get('devise', 'FCFA')})"]
    if avec_parts:
        headers += ["dont matériaux", "dont main-d'œuvre", "dont non décomposé"]
    header_row = row
    for col_idx, header in enumerate(headers, 1):
        cell = ws.cell(row=header_row, column=col_idx, value=header)
        cell.font = font_header
        cell.fill = fill_header
        cell.alignment = Alignment(horizontal="center", vertical="center")
        cell.border = thin_border
    row += 1

    for lot in lots:
        ws.cell(row=row, column=1, value=lot["numero"]).border = thin_border
        ws.cell(row=row, column=1).alignment = Alignment(horizontal="center")
        ws.cell(row=row, column=2, value=f"TOTAL {lot['label']} (HT)").border = thin_border
        m_cell = ws.cell(row=row, column=3, value=lot["sous_total"])
        m_cell.number_format = "#,##0"
        m_cell.alignment = Alignment(horizontal="right")
        m_cell.border = thin_border
        if avec_parts:
            d = lot["decomposition"]
            for col, v in ((4, d["materiaux"]), (5, d["main_oeuvre"]), (6, d["non_decompose"])):
                c = ws.cell(row=row, column=col, value=v)
                c.number_format = "#,##0"
                c.alignment = Alignment(horizontal="right")
                c.border = thin_border
        row += 1

    if avec_parts:
        # Somme des lignes (avant marge / TVA), avec ses parts : la marge et
        # la TVA ne sont jamais réparties entre matériaux et main-d'œuvre.
        d = dqe_data["decomposition"]
        ws.merge_cells(start_row=row, start_column=1, end_row=row, end_column=2)
        lbl = ws.cell(row=row, column=1, value="TOTAL DES LIGNES (avant marge et TVA)")
        lbl.font = font_bold
        lbl.alignment = Alignment(horizontal="right")
        for col, v in ((3, dqe_data["total_general"]), (4, d["materiaux"]), (5, d["main_oeuvre"]),
                       (6, d["non_decompose"])):
            c = ws.cell(row=row, column=col, value=v)
            c.font = font_bold
            c.number_format = "#,##0"
            c.alignment = Alignment(horizontal="right")
        row += 1
    recap_finances = lignes_recap_finances(dqe_data)
    for k, (libelle, valeur) in enumerate(recap_finances):
        dernier = k == len(recap_finances) - 1
        ws.merge_cells(start_row=row, start_column=1, end_row=row, end_column=2)
        lbl = ws.cell(row=row, column=1, value=libelle)
        lbl.font = font_bold
        lbl.alignment = Alignment(horizontal="right")
        lbl.fill = fill_total_general if dernier else fill_total
        val = ws.cell(row=row, column=3, value=valeur)
        val.font = font_bold
        if isinstance(valeur, int):
            val.number_format = "#,##0"
        val.alignment = Alignment(horizontal="right")
        val.fill = fill_total_general if dernier else fill_total
        row += 1
    row += 1

    montant, qualif = montant_arrete(dqe_data)
    ws.cell(
        row=row, column=1,
        value=f"Arrêté le présent devis à la somme de ({qualif}) : {montant_en_toutes_lettres(montant)}",
    ).font = font_small
    row += 2

    for titre, cle in (("HYPOTHÈSES DE CALCUL", "hypotheses_projet"), ("HYPOTHÈSES DE MÉTRÉ", "hypotheses")):
        if dqe_data.get(cle):
            ws.cell(row=row, column=1, value=titre).font = font_bold
            row += 1
            for h in dqe_data[cle]:
                ws.cell(row=row, column=1, value=f"• {h}").font = font_small
                row += 1
            row += 1

    ws.column_dimensions["A"].width = 8
    ws.column_dimensions["B"].width = 45
    ws.column_dimensions["C"].width = 20
    for lettre in ("D", "E", "F"):
        ws.column_dimensions[lettre].width = 18

    # ---- Une feuille de détail par lot ------------------------------------
    for lot in lots:
        if not lot["lignes"]:
            continue
        ws_lot = wb.create_sheet(_feuille_nom_unique(wb, lot["label"]))
        ws_lot.views.sheetView[0].showGridLines = True

        ws_lot.cell(row=1, column=1, value=lot["label"]).font = font_title
        ws_lot.row_dimensions[1].height = 22

        headers = ["Désignation", "Unité", "Quantité", "Prix Unitaire (FCFA)", "Montant (FCFA)"]
        if avec_parts:
            headers += ["dont matériaux (FCFA)", "dont main-d'œuvre (FCFA)"]
        headers += ["Formule de métré", "Nature quantité", "Source du prix", "Date du prix"]
        nb_col = len(headers)
        start_row = 3
        for col_idx, header in enumerate(headers, 1):
            cell = ws_lot.cell(row=start_row, column=col_idx, value=header)
            cell.font = font_header
            cell.fill = fill_header
            cell.alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)
            cell.border = thin_border
        ws_lot.row_dimensions[start_row].height = 30

        current_row = start_row + 1
        for sl in lot["sous_lots"]:
            titre = sl["libelle"] or ""
            if lot["plusieurs_parties"]:
                titre = f"{sl['partie']} — {titre}"
            ws_lot.merge_cells(start_row=current_row, start_column=1, end_row=current_row, end_column=nb_col)
            c = ws_lot.cell(row=current_row, column=1, value=titre)
            c.font = font_bold
            c.fill = fill_total
            current_row += 1
            for ligne in sl["lignes"]:
                valeurs = [
                    (ligne["designation"], None, "left"),
                    (ligne["unite"], None, "center"),
                    (float(ligne["quantite"]), "#,##0.000", "right"),
                    (ligne["prix_unitaire"], "#,##0", "right"),
                    (int(ligne["montant"]), "#,##0", "right"),
                ]
                if avec_parts:
                    if ligne.get("decomposition") == "decompose":
                        valeurs += [(ligne["montant_materiaux"], "#,##0", "right"),
                                    (ligne["montant_main_oeuvre"], "#,##0", "right")]
                    else:
                        valeurs += [("non décomposé", None, "center"), ("", None, "center")]
                valeurs += [
                    (ligne.get("formule_quantite") or "", None, "left"),
                    (ligne.get("type_donnee") or "", None, "center"),
                    (ligne.get("prix_source") or "", None, "left"),
                    (ligne.get("prix_date") or "", None, "center"),
                ]
                for col, (v, fmt, align) in enumerate(valeurs, 1):
                    cell = ws_lot.cell(row=current_row, column=col, value=v)
                    cell.font = font_normal
                    cell.border = thin_border
                    cell.alignment = Alignment(horizontal=align)
                    if fmt:
                        cell.number_format = fmt
                current_row += 1
            ws_lot.merge_cells(start_row=current_row, start_column=1, end_row=current_row, end_column=4)
            lbl = ws_lot.cell(row=current_row, column=1, value=f"Sous-total {sl['libelle'] or ''}")
            lbl.font = font_small
            lbl.alignment = Alignment(horizontal="right")
            st = ws_lot.cell(row=current_row, column=5, value=sl["sous_total"])
            st.font = font_bold
            st.number_format = "#,##0"
            if avec_parts:
                _parts_excel(ws_lot, current_row, sl["decomposition"], font_bold)
            current_row += 1

        ws_lot.merge_cells(start_row=current_row, start_column=1, end_row=current_row, end_column=4)
        lbl_cell = ws_lot.cell(row=current_row, column=1, value=f"TOTAL {lot['label']} (HT)")
        lbl_cell.font = font_bold
        lbl_cell.alignment = Alignment(horizontal="right")
        lbl_cell.fill = fill_total

        val_cell = ws_lot.cell(row=current_row, column=5, value=lot["sous_total"])
        val_cell.font = font_bold
        val_cell.number_format = "#,##0"
        val_cell.alignment = Alignment(horizontal="right")
        val_cell.fill = fill_total
        if avec_parts:
            _parts_excel(ws_lot, current_row, lot["decomposition"], font_bold, fill_total)
            if lot["decomposition"]["non_decompose"]:
                current_row += 1
                ws_lot.merge_cells(start_row=current_row, start_column=1, end_row=current_row, end_column=4)
                n = ws_lot.cell(row=current_row, column=1, value="dont non décomposé (prix sans parts)")
                n.font = font_small
                n.alignment = Alignment(horizontal="right")
                v = ws_lot.cell(row=current_row, column=5, value=lot["decomposition"]["non_decompose"])
                v.font = font_small
                v.number_format = "#,##0"

        largeurs = [45, 10, 15, 20, 20] + ([20, 20] if avec_parts else []) + [38, 14, 30, 13]
        for i, largeur in enumerate(largeurs):
            ws_lot.column_dimensions[chr(ord("A") + i)].width = largeur

    buffer = BytesIO()
    wb.save(buffer)
    buffer.seek(0)
    return buffer

def exporter_approvisionnement_excel(fiche: dict, entreprise: dict = None) -> BytesIO:
    """Fiche d'approvisionnement : matériaux à commander, origine de chaque
    paramètre, et ce qui n'a pas pu être converti (rien n'est caché)."""
    projet = fiche.get("projet", {})
    gras = Font(name="Calibri", size=11, bold=True)
    titre = Font(name="Calibri", size=16, bold=True, color="2C3E50")
    entete = Font(name="Calibri", size=11, bold=True, color="FFFFFF")
    petit = Font(name="Calibri", size=9, color="555555")
    fond = PatternFill(start_color="2C3E50", end_color="2C3E50", fill_type="solid")
    fond_total = PatternFill(start_color="ECF0F1", end_color="ECF0F1", fill_type="solid")
    bord = Border(*(Side(style="thin", color="BDC3C7"),) * 4)

    wb = Workbook()
    ws = wb.active
    ws.title = "Approvisionnement"
    ws["A1"] = _entreprise_champ(entreprise, "nom") or ""
    ws["A1"].font = gras
    ws["A2"] = "FICHE D'APPROVISIONNEMENT EN MATÉRIAUX"
    ws["A2"].font = titre
    ws["A3"] = f"Projet : {projet.get('nom', '')}"
    ws["A4"] = f"Édité le {formater_date(projet.get('date_edition', ''))} — béton total {formater_nombre(fiche['volume_beton_m3'])} m³"
    ws["A4"].font = petit

    colonnes = ["Matériau", "Unité", "Quantité nette", "Pertes (%)", "À commander", "Conditionnement / voyages",
                "Prix unitaire", "Montant (FCFA)", "Calcul"]
    r = 6
    for c, nom in enumerate(colonnes, start=1):
        cell = ws.cell(row=r, column=c, value=nom)
        cell.font, cell.fill, cell.border = entete, fond, bord
        cell.alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)
    for l in fiche["lignes"]:
        r += 1
        cond = l["conditionnement"] or (l["voyages"] or {}).get("message") or ""
        valeurs = [l["materiau"], l["unite"], l["quantite_nette"], l["pertes_pct"], l["quantite_commande"], cond,
                   l["prix_unitaire"] if l["prix_unitaire"] is not None else "prix non renseigné",
                   l["montant"] if l["montant"] is not None else "non calculé", l["formule"]]
        for c, v in enumerate(valeurs, start=1):
            cell = ws.cell(row=r, column=c, value=v)
            cell.border = bord
            if c in (3, 5):
                cell.number_format = "#,##0.000" if l["unite"] != "u" else "#,##0"
            if c in (7, 8) and isinstance(v, (int, float)):
                cell.number_format = "#,##0"
    r += 2
    totaux = [("Total HT", fiche["total_ht"]),
              (f"TVA ({formater_nombre(fiche['taux_tva_pct'])} %)" if fiche["taux_tva_pct"] is not None else "TVA",
               fiche["montant_tva"]),
              ("Total TTC", fiche["total_ttc"])]
    for libelle, valeur in totaux:
        ws.cell(row=r, column=7, value=libelle).font = gras
        cell = ws.cell(row=r, column=8, value=valeur if valeur is not None else "non calculé")
        cell.font, cell.fill = gras, fond_total
        if isinstance(valeur, int):
            cell.number_format = "#,##0"
        r += 1
    for m in fiche["messages"]:
        ws.cell(row=r, column=1, value=m).font = petit
        r += 1

    r += 1
    ws.cell(row=r, column=1, value="Paramètres utilisés").font = gras
    for p in fiche["parametres"].values():
        r += 1
        ws.cell(row=r, column=1, value=p["libelle"])
        ws.cell(row=r, column=3, value=p["valeur"] if p["valeur"] is not None else "non renseigné")
        ws.cell(row=r, column=4, value=p["unite"])
        ws.cell(row=r, column=6, value=p["source"]).font = petit
    if fiche["non_convertis"]:
        r += 2
        ws.cell(row=r, column=1, value="Lignes du DQE non converties en matériaux").font = gras
        for n in fiche["non_convertis"]:
            r += 1
            ws.cell(row=r, column=1, value=n["designation"])
            ws.cell(row=r, column=3, value=n["quantite"])
            ws.cell(row=r, column=4, value=n["unite"])
            ws.cell(row=r, column=6, value=n["raison"]).font = petit
    for col, largeur in zip("ABCDEFGHI", (30, 8, 15, 10, 15, 30, 16, 18, 60)):
        ws.column_dimensions[col].width = largeur

    buffer = BytesIO()
    wb.save(buffer)
    buffer.seek(0)
    return buffer
