"""
Rendu PDF du DQE : présentation seule. On vérifie que le PDF reprend
EXACTEMENT les valeurs du DQE (aucun recalcul, aucune donnée inventée),
la pagination dynamique, le logo réel et les cas sans TVA / avec marge.
"""

import os
import re
import shutil
import subprocess
import tempfile
import unittest

from django.test import SimpleTestCase

from projets.services.dqe_exporters import exporter_dqe_pdf
from projets.services.pdf_dqe import get_logo

PDFTOTEXT = shutil.which("pdftotext")


def ligne(rep, des, cat, u, q, pu, m, sl="Poteaux"):
    return {"repere": rep, "designation": des, "categorie": cat, "unite": u, "quantite": q, "prix_unitaire": pu,
            "montant": m, "type_element": "POTEAU", "source_quantite": "calcul_moteur", "type_donnee": "calculé",
            "formule_quantite": "a² × h = 0,2² × 3", "lot": "lot_02_gros_oeuvre_superstructure"}


def dqe(nb_lignes=3, finances=None, lots_extra=()):
    lignes = [ligne(f"P{i}", f"Béton armé — Poteau P{i}", "BETON", "m³", 0.12, 100000, 12000) for i in range(nb_lignes)]
    total = sum(l["montant"] for l in lignes)
    lots = [{"lot": "lot_02_gros_oeuvre_superstructure", "libelle": "Gros Œuvre - Superstructure", "lignes": lignes,
             "sous_lots": [{"libelle": "Poteaux", "lignes": lignes, "sous_total": total}], "sous_total": total}]
    for code, lib, l in lots_extra:
        lots.append({"lot": code, "libelle": lib, "lignes": [l], "sous_lots": [{"libelle": "Postes saisis", "lignes": [l],
                     "sous_total": l["montant"]}], "sous_total": l["montant"]})
        lignes = lignes + [l]
        total += l["montant"]
    return {
        "projet": {"id": 1, "nom": "Projet Test", "usage_batiment": "habitation", "nb_niveaux": 2,
                   "numero_devis": "non attribué", "date_edition": "2026-10-07", "auteur": "ingenieur"},
        "lignes": lignes, "lots": lots, "sous_totaux": {"beton": total}, "synthese": {},
        "hypotheses": ["Poteaux : acier estimé à 125 kg par m³ de béton."],
        "hypotheses_projet": ["HYPOTHÈSE : charge permanente des planchers G = 5 kN/m²."],
        "total_general": total, "montant_lettres": "", "devise": "FCFA",
        "finances": finances if finances is not None else {
            "nature_prix": "vente_ht", "total_lignes": total, "debourse_sec": None, "taux_marge_pct": None,
            "montant_marge": None, "total_ht": total, "taux_tva_pct": 18.0, "montant_tva": round(total * 0.18),
            "total_ttc": total + round(total * 0.18), "messages": []},
    }


def texte_pdf(buffer):
    with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as f:
        f.write(buffer.getvalue())
    try:
        return subprocess.run([PDFTOTEXT, "-layout", f.name, "-"], capture_output=True, text=True).stdout
    finally:
        os.unlink(f.name)


fmt = lambda n: f"{n:,}".replace(",", " ")  # noqa: E731


@unittest.skipUnless(PDFTOTEXT, "pdftotext indisponible")
class RenduPDF(SimpleTestCase):
    def test_valeurs_reprises_a_l_identique(self):
        d = dqe()
        t = texte_pdf(exporter_dqe_pdf(d, entreprise={"nom": "Cabinet Test", "email": "c@test.ci"}))
        f = d["finances"]
        for v in (d["total_general"], f["montant_tva"], f["total_ttc"]):
            self.assertIn(fmt(v), t)
        self.assertEqual(len(re.findall(r"\b02\.01\.\d{2}\b", t)), 3)
        self.assertIn("DEVIS QUANTITATIF ET ESTIMATIF", t)
        self.assertIn("Cabinet Test", t)
        total = int(re.findall(r"Page \d+ / (\d+)", t)[0])
        self.assertIn(f"Page 1 / {total}", t)
        # Référence non attribuée : jamais inventée
        self.assertNotIn("DQE-", t)

    def test_pagination_dynamique_document_long(self):
        t = texte_pdf(exporter_dqe_pdf(dqe(nb_lignes=150)))
        total = int(re.findall(r"Page \d+ / (\d+)", t)[0])
        self.assertGreater(total, 2)
        for i in range(1, total + 1):
            self.assertIn(f"Page {i} / {total}", t)
        # En-tête du tableau répété sur chaque page de tableau
        self.assertGreaterEqual(t.count("DÉSIGNATION"), total - 1)

    def test_sans_tva_le_ttc_n_est_pas_invente(self):
        d = dqe(finances={"nature_prix": "vente_ht", "total_lignes": 36000, "debourse_sec": None, "taux_marge_pct": None,
                          "montant_marge": None, "total_ht": 36000, "taux_tva_pct": None, "montant_tva": None,
                          "total_ttc": None, "messages": ["Taux de TVA non renseigné : TTC non calculé."]})
        t = texte_pdf(exporter_dqe_pdf(d))
        self.assertIn("non calculé", t)
        self.assertIn("HORS TAXES", t)
        self.assertNotIn("TVA (", t)

    def test_debourse_et_marge(self):
        d = dqe(finances={"nature_prix": "debourse_sec", "total_lignes": 36000, "debourse_sec": 36000,
                          "taux_marge_pct": 10.0, "montant_marge": 3600, "total_ht": 39600, "taux_tva_pct": 18.0,
                          "montant_tva": 7128, "total_ttc": 46728, "messages": []})
        t = texte_pdf(exporter_dqe_pdf(d))
        for attendu in ("Déboursé sec", "Marge (10 %)", "39 600", "7 128", "46 728"):
            self.assertIn(attendu, t)

    def test_plusieurs_lots_recapitulatif(self):
        extra = ligne("MO", "Installation de chantier", "MAIN_DOEUVRE", "forfait", 1, 350000, 350000)
        extra["lot"] = "lot_00_generalites"
        d = dqe(lots_extra=[("lot_00_generalites", "Généralités", extra)])
        t = texte_pdf(exporter_dqe_pdf(d))
        self.assertIn("RÉCAPITULATIF PAR LOT", t)
        self.assertIn("LOT 00 — GÉNÉRALITÉS", t)
        self.assertIn(fmt(d["total_general"]), t)


class Logo(SimpleTestCase):
    def test_absence_de_logo(self):
        self.assertIsNone(get_logo({}))
        self.assertIsNone(get_logo({"logo_path": "/chemin/inexistant.png"}))

    def test_logo_reel_proportions_conservees(self):
        from PIL import Image as PILImage

        with tempfile.TemporaryDirectory() as d:
            chemin = os.path.join(d, "logo.png")
            PILImage.new("RGB", (400, 100), "white").save(chemin)
            img = get_logo({"logo_path": chemin})
            self.assertIsNotNone(img)
            self.assertAlmostEqual(img.drawWidth / img.drawHeight, 4.0, places=2)
