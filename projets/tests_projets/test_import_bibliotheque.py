"""
Import d'un DQE Excel dans la bibliothèque d'ouvrages (aperçu puis
confirmation). Classeur construit par le test (prix DE TEST) :

  ligne 3  en-tête : N° | Désignation | U | Qté | P.U | Montant
  LOT 1 : TERRASSEMENT
    Fouille en rigole            m³  3 500        (déjà en bibliothèque au même prix -> identique)
  Sous-total lot 1                                 (ignoré)
  LOT 9 : MENUISERIE BOIS
    Porte isoplane 0,80 × 2,10   u   "85 000 FCFA" (prix en texte)
    Porte isoplane 0,80 × 2,10   u   85 000        (même ouvrage, même prix -> 1 ligne, 2 occurrences)
  Gros œuvre                                       (titre ambigu : lot à choisir)
    Béton de propreté            m³  60 000
  LOT 12 : PEINTURE
    Peinture glycéro             m²  2 500
    Peinture glycéro             m²  2 800         (deux prix -> à arbitrer)
    Peinture vinylique           m²  (vide)        (sans prix)
    Plinthes                     (sans unité)       (ignorée)
    Enduit                       m²  =2*1500       (formule sans valeur enregistrée)
  TOTAL HT                                          (ignoré)
"""

import io

import openpyxl
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import SimpleTestCase
from rest_framework.test import APITestCase

from projets.models import OuvrageType, Profil
from projets.services.import_bibliotheque import lire_prix, reconnaitre_lot
from projets.tests_projets.utils import authentifier, creer_cabinet, creer_membre

URL = "/api/ouvrages/importer/"


def classeur_test():
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "DQE Villa"
    lignes = [
        ["DEVIS QUANTITATIF ET ESTIMATIF"],
        [],
        ["N°", "Désignation", "U", "Qté", "P.U", "Montant"],
        [None, "LOT 1 : TERRASSEMENT"],
        ["1.1", "Fouille en rigole", "m³", 20, 3500, 70000],
        [None, "Sous-total lot 1", None, None, None, 70000],
        [None, "LOT 9 : MENUISERIE BOIS"],
        ["9.1", "Porte isoplane 0,80 × 2,10", "u", 3, "85 000 FCFA", 255000],
        ["9.2", "Porte isoplane 0,80 × 2,10", "u", 2, 85000, 170000],
        [None, "Gros œuvre"],
        ["2.1", "Béton de propreté", "m³", 1, 60000, 60000],
        [None, "LOT 12 : PEINTURE"],
        ["12.1", "Peinture glycéro", "m²", 100, 2500, 250000],
        ["12.2", "Peinture glycéro", "m²", 50, 2800, 140000],
        ["12.3", "Peinture vinylique", "m²", 10, None, None],
        ["12.4", "Plinthes", None, 5, 100, 500],
        ["12.5", "Enduit", "m²", 1, "=2*1500", None],
        [None, "TOTAL HT", None, None, None, 999],
    ]
    for l in lignes:
        ws.append(l)
    tampon = io.BytesIO()
    wb.save(tampon)
    return tampon.getvalue()


class Lecture(SimpleTestCase):
    def test_reconnaissance_des_lots(self):
        self.assertEqual(reconnaitre_lot("LOT 3 : ÉTANCHÉITÉ"), ("lot_03_etancheite", False))
        self.assertEqual(reconnaitre_lot("MENUISERIES BOIS"), ("lot_09_menuiserie_bois", False))
        self.assertEqual(reconnaitre_lot("Gros Œuvre - Infrastructure"), ("lot_02_gros_oeuvre_infrastructure", False))
        self.assertEqual(reconnaitre_lot("LOT 02 — GROS ŒUVRE"), (None, True))       # ambigu
        self.assertEqual(reconnaitre_lot("Menuiserie"), (None, True))                 # ambigu
        self.assertEqual(reconnaitre_lot("VRD (voirie et réseaux divers)"), ("lot_14_vrd", False))
        self.assertEqual(reconnaitre_lot("REZ-DE-CHAUSSEE"), (None, False))           # pas un lot

    def test_lecture_des_prix(self):
        self.assertEqual(lire_prix("85 000 FCFA"), 85000)
        self.assertEqual(lire_prix("1 250,5"), 1250.5)
        self.assertEqual(lire_prix(3500), 3500)
        self.assertIsNone(lire_prix(-10))
        self.assertIsNone(lire_prix("sur devis"))
        self.assertIsNone(lire_prix(True))


class APIImport(APITestCase):
    def setUp(self):
        self.user, self.cabinet = authentifier(self, role=Profil.Role.INGENIEUR)
        OuvrageType.objects.create(entreprise=self.cabinet, lot="lot_01_terrassement",
                                   designation="Fouille en rigole", unite="m³", prix_unitaire=3500)

    def apercu(self, contenu=None, nom="dqe.xlsx"):
        f = SimpleUploadedFile(nom, contenu if contenu is not None else classeur_test())
        return self.client.post(URL, {"fichier": f}, format="multipart")

    def test_apercu(self):
        r = self.apercu()
        self.assertEqual(r.status_code, 200, r.data)
        par_des = {(l["designation"], l["statut"]): l for l in r.data["lignes"]}
        self.assertEqual(len(r.data["lignes"]), 6)
        self.assertEqual(r.data["compte"], {"identique": 1, "nouveau": 1, "lot_a_choisir": 1,
                                            "prix_a_arbitrer": 1, "sans_prix": 2})
        self.assertIn(("Fouille en rigole", "identique"), par_des)
        porte = par_des[("Porte isoplane 0,80 × 2,10", "nouveau")]
        self.assertEqual((porte["lot"], porte["prix_unitaire"], porte["occurrences"]), ("lot_09_menuiserie_bois", 85000, 2))
        self.assertTrue(porte["a_importer"])
        beton = par_des[("Béton de propreté", "lot_a_choisir")]
        self.assertIsNone(beton["lot"])
        self.assertFalse(beton["a_importer"])
        glycero = par_des[("Peinture glycéro", "prix_a_arbitrer")]
        self.assertEqual(glycero["prix_possibles"], [2500, 2800])
        self.assertIsNone(glycero["prix_unitaire"])
        self.assertIn(("Peinture vinylique", "sans_prix"), par_des)
        self.assertIn(("Enduit", "sans_prix"), par_des)
        self.assertTrue(any("1 prix calculé(s) par une formule" in a for a in r.data["avertissements"]))
        self.assertTrue(any("1 ligne(s) sans unité" in a for a in r.data["avertissements"]))
        self.assertEqual(OuvrageType.objects.count(), 1)          # rien n'est écrit

    def test_confirmation(self):
        r = self.client.post(f"{URL}confirmer/", {
            "source_prix": "DQE test", "date_prix": "2026-10-16",
            "lignes": [
                {"lot": "lot_09_menuiserie_bois", "designation": "Porte isoplane 0,80 × 2,10", "unite": "u",
                 "prix_unitaire": 85000, "action": "creer"},
                {"lot": "lot_02_gros_oeuvre_infrastructure", "designation": "Béton de propreté", "unite": "m³",
                 "prix_unitaire": 60000, "action": "creer"},
                {"lot": "lot_12_peinture", "designation": "Peinture vinylique", "unite": "m²",
                 "prix_unitaire": None, "action": "creer"},
                {"lot": "lot_01_terrassement", "designation": "fouille en rigole", "unite": "m³",
                 "prix_unitaire": 3700, "action": "mettre_a_jour"},
            ]}, format="json")
        self.assertEqual(r.status_code, 201, r.data)
        self.assertEqual((r.data["crees"], r.data["mis_a_jour"]), (3, 1))
        porte = OuvrageType.objects.get(designation__startswith="Porte")
        self.assertEqual((porte.source_prix, str(porte.date_prix), porte.cree_par), ("DQE test", "2026-10-16", self.user))
        self.assertEqual(OuvrageType.objects.get(designation="Fouille en rigole").prix_unitaire, 3700)

    def test_tout_ou_rien(self):
        r = self.client.post(f"{URL}confirmer/", {"lignes": [
            {"lot": "lot_12_peinture", "designation": "Peinture glycéro", "unite": "m²", "prix_unitaire": 2500},
            {"lot": "lot_12_peinture", "designation": "Peinture à l'huile", "unite": "m²", "prix_unitaire": -5},
            {"lot": "lot_99", "designation": "X", "unite": "u", "prix_unitaire": 1},
        ]}, format="json")
        self.assertEqual(r.status_code, 400)
        self.assertEqual(set(r.data["lignes"]), {"2", "3"})
        self.assertEqual(OuvrageType.objects.count(), 1)

    def test_doublon_dans_l_import_refuse(self):
        ligne = {"lot": "lot_12_peinture", "designation": "Peinture glycéro", "unite": "m²", "prix_unitaire": 2500}
        r = self.client.post(f"{URL}confirmer/", {"lignes": [ligne, ligne]}, format="json")
        self.assertEqual(r.status_code, 400)
        self.assertEqual(OuvrageType.objects.count(), 1)

    def test_fichiers_refuses(self):
        r = self.apercu(b"pas un classeur", "dqe.xlsx")
        self.assertEqual(r.status_code, 400)
        self.assertIn(".xlsx", r.data["erreur"])
        self.assertEqual(self.apercu(b"x", "dqe.xls").status_code, 400)
        wb = openpyxl.Workbook()
        wb.active.append(["Rien", "d'utile"])
        t = io.BytesIO()
        wb.save(t)
        r = self.apercu(t.getvalue())
        self.assertEqual(r.status_code, 400)
        self.assertIn("Désignation", r.data["erreur"])

    def test_droits(self):
        tech = creer_membre(self.cabinet, username="tech", role=Profil.Role.TECHNICIEN)
        self.client.force_authenticate(tech)
        self.assertEqual(self.apercu().status_code, 403)
        autre = creer_membre(creer_cabinet("Autre"), username="autre", role=Profil.Role.ADMIN)
        self.client.force_authenticate(autre)
        r = self.apercu()
        fouille = next(l for l in r.data["lignes"] if l["designation"] == "Fouille en rigole")
        self.assertEqual(fouille["statut"], "nouveau")          # la bibliothèque de l'autre cabinet n'est pas vue
        self.client.post(f"{URL}confirmer/", {"lignes": [{"lot": "lot_01_terrassement", "designation": "Fouille en rigole",
                                                          "unite": "m³", "prix_unitaire": 1, "action": "mettre_a_jour"}]},
                         format="json")
        self.assertEqual(OuvrageType.objects.get(entreprise=self.cabinet).prix_unitaire, 3500)
