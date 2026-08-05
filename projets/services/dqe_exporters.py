from io import BytesIO
from decimal import Decimal
from reportlab.lib.pagesizes import A4
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib import colors
from openpyxl import Workbook
from openpyxl.styles import Font, PatternFill, Alignment, Border, Side

def formater_nombre(valeur) -> str:
    """Formate un nombre avec un espace comme séparateur des milliers."""
    if valeur is None:
        return "0"
    if isinstance(valeur, (int, Decimal)):
        if isinstance(valeur, Decimal) and valeur != valeur.to_integral_value():
            valeur = float(valeur)
        else:
            return f"{int(valeur):,}".replace(",", " ")
    return f"{valeur:,.4f}".replace(",", " ").rstrip("0").rstrip(".")

def exporter_dqe_pdf(dqe_data: dict) -> BytesIO:
    """
    Génère le document PDF du DQE en mémoire à partir de la structure DQE commune.
    """
    buffer = BytesIO()
    # Marges de 2 cm (56.7 points)
    doc = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        rightMargin=40,
        leftMargin=40,
        topMargin=40,
        bottomMargin=40
    )
    story = []

    styles = getSampleStyleSheet()

    # Styles personnalisés
    title_style = ParagraphStyle(
        'DQETitle',
        parent=styles['Heading1'],
        fontName='Helvetica-Bold',
        fontSize=18,
        spaceAfter=15,
        alignment=1  # Centré
    )

    normal_style = ParagraphStyle(
        'DQENormal',
        parent=styles['Normal'],
        fontName='Helvetica',
        fontSize=10,
        leading=14
    )

    bold_style = ParagraphStyle(
        'DQEBold',
        parent=styles['Normal'],
        fontName='Helvetica-Bold',
        fontSize=10,
        leading=14
    )

    header_style = ParagraphStyle(
        'DQEHeader',
        parent=styles['Normal'],
        fontName='Helvetica-Bold',
        fontSize=10,
        textColor=colors.whitesmoke
    )

    # Titre et Infos Projet
    story.append(Paragraph("DEVIS QUANTITATIF ESTIMATIF (DQE)", title_style))
    story.append(Paragraph(f"<b>Projet :</b> {dqe_data['projet']['nom']} (ID: {dqe_data['projet']['id']})", normal_style))
    story.append(Paragraph(f"<b>Devise :</b> {dqe_data['devise']}", normal_style))
    story.append(Spacer(1, 15))

    # Préparation du tableau DQE
    headers = ["Désignation", "Unité", "Quantité", "Prix Unitaire", "Montant"]
    data = [[Paragraph(h, header_style) for h in headers]]

    # Lignes d'éléments
    for ligne in dqe_data["lignes"]:
        data.append([
            Paragraph(ligne["designation"], normal_style),
            Paragraph(ligne["unite"], normal_style),
            Paragraph(formater_nombre(ligne["quantite"]), normal_style),
            Paragraph(formater_nombre(ligne["prix_unitaire"]), normal_style),
            Paragraph(formater_nombre(ligne["montant"]), normal_style)
        ])

    # Espacement
    data.append(["", "", "", "", ""])

    # Sous-totaux et Totaux
    data.append([Paragraph("<b>Sous-total Béton</b>", bold_style), "", "", "", Paragraph(formater_nombre(dqe_data["sous_totaux"]["beton"]), bold_style)])
    data.append([Paragraph("<b>Sous-total Coffrage</b>", bold_style), "", "", "", Paragraph(formater_nombre(dqe_data["sous_totaux"]["coffrage"]), bold_style)])
    data.append([Paragraph("<b>Sous-total Acier</b>", bold_style), "", "", "", Paragraph(formater_nombre(dqe_data["sous_totaux"]["acier"]), bold_style)])
    data.append([Paragraph("<b>Sous-total Main d'œuvre</b>", bold_style), "", "", "", Paragraph(formater_nombre(dqe_data["sous_totaux"]["main_doeuvre"]), bold_style)])
    data.append([Paragraph("<b>TOTAL GÉNÉRAL</b>", bold_style), "", "", "", Paragraph(formater_nombre(dqe_data["total_general"]), bold_style)])

    # Largeur totale disponible = 595.27 (A4 width) - 80 (marges) = 515.27
    col_widths = [225, 45, 65, 90, 90]
    t = Table(data, colWidths=col_widths)

    t_style = TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#2C3E50')),
        ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('TOPPADDING', (0, 0), (-1, -1), 6),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
        ('GRID', (0, 0), (-1, -7), 0.5, colors.lightgrey),
        
        # Spans pour sous-totaux et totaux
        ('SPAN', (0, -5), (3, -5)),
        ('SPAN', (0, -4), (3, -4)),
        ('SPAN', (0, -3), (3, -3)),
        ('SPAN', (0, -2), (3, -2)),
        ('SPAN', (0, -1), (3, -1)),
        
        # Styles de lignes des totaux
        ('LINEABOVE', (0, -5), (-1, -5), 1.5, colors.HexColor('#2C3E50')),
        ('BACKGROUND', (0, -1), (-1, -1), colors.HexColor('#ECF0F1')),
    ])
    t.setStyle(t_style)
    story.append(t)

    # Signature
    story.append(Spacer(1, 40))
    story.append(Paragraph("<b>Pour l'ingénieur structure responsable :</b>", normal_style))
    story.append(Spacer(1, 10))
    story.append(Paragraph("Date de validation : ________________________", normal_style))
    story.append(Spacer(1, 10))
    story.append(Paragraph("Signature & Cachet :", normal_style))

    doc.build(story)
    buffer.seek(0)
    return buffer

def exporter_dqe_excel(dqe_data: dict) -> BytesIO:
    """
    Génère le fichier Excel du DQE en mémoire à partir de la structure DQE commune.
    """
    wb = Workbook()
    ws = wb.active
    ws.title = "DQE"

    # Affichage de la grille de lignes
    ws.views.sheetView[0].showGridLines = True

    # Styles Excel
    font_title = Font(name="Calibri", size=16, bold=True, color="2C3E50")
    font_bold = Font(name="Calibri", size=11, bold=True)
    font_header = Font(name="Calibri", size=11, bold=True, color="FFFFFF")
    font_normal = Font(name="Calibri", size=11)
    
    fill_header = PatternFill(start_color="2C3E50", end_color="2C3E50", fill_type="solid")
    fill_total = PatternFill(start_color="ECF0F1", end_color="ECF0F1", fill_type="solid")

    thin_border = Border(
        left=Side(style='thin', color='BDC3C7'),
        right=Side(style='thin', color='BDC3C7'),
        top=Side(style='thin', color='BDC3C7'),
        bottom=Side(style='thin', color='BDC3C7')
    )

    double_bottom_border = Border(
        top=Side(style='thin', color='2C3E50'),
        bottom=Side(style='double', color='2C3E50')
    )

    # Remplissage du titre et métadonnées
    ws["A1"] = "DEVIS QUANTITATIF ESTIMATIF (DQE)"
    ws["A1"].font = font_title
    ws.row_dimensions[1].height = 25

    ws["A3"] = f"Projet : {dqe_data['projet']['nom']} (ID: {dqe_data['projet']['id']})"
    ws["A3"].font = font_bold
    ws["A4"] = f"Devise : {dqe_data['devise']}"
    ws["A4"].font = font_normal

    # En-têtes du tableau
    headers = ["Désignation", "Unité", "Quantité", "Prix Unitaire (FCFA)", "Montant (FCFA)"]
    start_row = 6
    for col_idx, header in enumerate(headers, 1):
        cell = ws.cell(row=start_row, column=col_idx, value=header)
        cell.font = font_header
        cell.fill = fill_header
        cell.alignment = Alignment(horizontal="center", vertical="center")
        cell.border = thin_border
    ws.row_dimensions[start_row].height = 24

    # Remplissage des éléments
    current_row = start_row + 1
    for ligne in dqe_data["lignes"]:
        ws.cell(row=current_row, column=1, value=ligne["designation"]).font = font_normal
        ws.cell(row=current_row, column=1).alignment = Alignment(horizontal="left")
        ws.cell(row=current_row, column=1).border = thin_border

        ws.cell(row=current_row, column=2, value=ligne["unite"]).font = font_normal
        ws.cell(row=current_row, column=2).alignment = Alignment(horizontal="center")
        ws.cell(row=current_row, column=2).border = thin_border

        # Quantité formatée jusqu'à 4 décimales
        q_cell = ws.cell(row=current_row, column=3, value=float(ligne["quantite"]))
        q_cell.font = font_normal
        q_cell.number_format = "0.####"
        q_cell.alignment = Alignment(horizontal="right")
        q_cell.border = thin_border

        # Prix Unitaire
        pu_cell = ws.cell(row=current_row, column=4, value=int(ligne["prix_unitaire"]))
        pu_cell.font = font_normal
        pu_cell.number_format = "#,##0"
        pu_cell.alignment = Alignment(horizontal="right")
        pu_cell.border = thin_border

        # Montant : valeur déjà calculée par dqe_calculator (source de vérité unique)
        m_cell = ws.cell(row=current_row, column=5, value=int(ligne["montant"]))
        m_cell.font = font_normal
        m_cell.number_format = "#,##0"
        m_cell.alignment = Alignment(horizontal="right")
        m_cell.border = thin_border

        current_row += 1

    # Ligne vide de séparation
    current_row += 1

    # Lignes de sous-totaux et total général
    categories = [
        ("Sous-total Béton", dqe_data["sous_totaux"]["beton"]),
        ("Sous-total Coffrage", dqe_data["sous_totaux"]["coffrage"]),
        ("Sous-total Acier", dqe_data["sous_totaux"]["acier"]),
        ("Sous-total Main d'œuvre", dqe_data["sous_totaux"]["main_doeuvre"]),
    ]

    for label, val in categories:
        # Fusionner A à D pour le label du sous-total
        ws.merge_cells(start_row=current_row, start_column=1, end_row=current_row, end_column=4)
        lbl_cell = ws.cell(row=current_row, column=1, value=label)
        lbl_cell.font = font_bold
        lbl_cell.alignment = Alignment(horizontal="right")
        
        val_cell = ws.cell(row=current_row, column=5, value=int(val))
        val_cell.font = font_bold
        val_cell.number_format = "#,##0"
        val_cell.alignment = Alignment(horizontal="right")
        
        current_row += 1

    # Total général
    ws.merge_cells(start_row=current_row, start_column=1, end_row=current_row, end_column=4)
    total_lbl = ws.cell(row=current_row, column=1, value="TOTAL GÉNÉRAL")
    total_lbl.font = font_bold
    total_lbl.alignment = Alignment(horizontal="right")
    total_lbl.fill = fill_total
    
    total_val = ws.cell(row=current_row, column=5, value=int(dqe_data["total_general"]))
    total_val.font = font_bold
    total_val.number_format = "#,##0"
    total_val.alignment = Alignment(horizontal="right")
    total_val.fill = fill_total
    total_val.border = double_bottom_border

    # Ajustement automatique des largeurs de colonnes
    ws.column_dimensions["A"].width = 35
    ws.column_dimensions["B"].width = 10
    ws.column_dimensions["C"].width = 15
    ws.column_dimensions["D"].width = 20
    ws.column_dimensions["E"].width = 20

    buffer = BytesIO()
    wb.save(buffer)
    buffer.seek(0)
    return buffer
