from decimal import Decimal
from io import BytesIO
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APITestCase
from openpyxl import load_workbook

from projets.models import Projet, ElementStructurel, PosteMainDoeuvre
from projets.services.dqe_calculator import calculer_element_dqe, calculer_projet_dqe
from projets.services.dqe_exporters import exporter_dqe_pdf, exporter_dqe_excel

class DQECalculatorTestCase(TestCase):
    def setUp(self):
        self.projet = Projet.objects.create(
            nom="Immeuble Test R+1",
            usage_batiment="habitation",
            nb_niveaux=2
        )
        # 1. Poteau
        self.poteau = ElementStructurel.objects.create(
            projet=self.projet,
            type_element=ElementStructurel.TypeElement.POTEAU,
            identifiant="P1",
            hauteur_poteau=3.0,
            resultat_calcul={"cote_cm": 20},
            resultat_valide={"cote_cm": 20},
            statut=ElementStructurel.Statut.VALIDE
        )
        # 2. Poutre
        self.poutre = ElementStructurel.objects.create(
            projet=self.projet,
            type_element=ElementStructurel.TypeElement.POUTRE,
            identifiant="PT1",
            portee=5.0,
            resultat_calcul={"largeur_cm": 20, "hauteur_cm": 40},
            resultat_valide={"largeur_cm": 20, "hauteur_cm": 40},
            statut=ElementStructurel.Statut.VALIDE
        )
        # 3. Semelle
        self.semelle = ElementStructurel.objects.create(
            projet=self.projet,
            type_element=ElementStructurel.TypeElement.SEMELLE,
            identifiant="S1",
            resultat_calcul={"cote_cm": 150, "hauteur_cm": 40},
            resultat_valide={"cote_cm": 150, "hauteur_cm": 40},
            statut=ElementStructurel.Statut.VALIDE
        )

    def test_calculer_element_poteau_ratio(self):
        lignes = calculer_element_dqe(self.poteau, {})
        # Doit générer 3 lignes (Béton, Coffrage, Acier)
        self.assertEqual(len(lignes), 3)
        
        beton = next(l for l in lignes if l["categorie"] == "BETON")
        coffrage = next(l for l in lignes if l["categorie"] == "COFFRAGE")
        acier = next(l for l in lignes if l["categorie"] == "ACIER")

        # volume_beton = 0.20 * 0.20 * 3.0 = 0.12 m3
        self.assertEqual(beton["quantite"], 0.12)
        # surf_coffrage = 4 * 0.20 * 3.0 = 2.4 m2
        self.assertEqual(coffrage["quantite"], 2.4)
        # poids_acier = 0.12 * 125 = 15.0 kg
        self.assertEqual(acier["quantite"], 15.0)

    def test_calculer_element_poteau_poids_moteur(self):
        # Modification de resultat_valide pour y inclure le poids fourni par le moteur
        self.poteau.resultat_valide = {
            "cote_cm": 20,
            "poids_acier_total_kg": 15.5
        }
        self.poteau.save()

        lignes = calculer_element_dqe(self.poteau, {})
        acier = next(l for l in lignes if l["categorie"] == "ACIER")
        self.assertEqual(acier["quantite"], 15.5)

    def test_calculer_element_poutre(self):
        lignes = calculer_element_dqe(self.poutre, {})
        self.assertEqual(len(lignes), 3)

        beton = next(l for l in lignes if l["categorie"] == "BETON")
        coffrage = next(l for l in lignes if l["categorie"] == "COFFRAGE")
        acier = next(l for l in lignes if l["categorie"] == "ACIER")

        # volume_beton = 0.20 * 0.40 * 5.0 = 0.40 m3
        self.assertEqual(beton["quantite"], 0.40)
        # surf_coffrage = (0.20 + 2 * 0.40) * 5.0 = 5.0 m2
        self.assertEqual(coffrage["quantite"], 5.0)
        # poids_acier = 0.40 * 150 = 60 kg
        self.assertEqual(acier["quantite"], 60.0)

    def test_calculer_element_semelle(self):
        lignes = calculer_element_dqe(self.semelle, {})
        self.assertEqual(len(lignes), 3)

        beton = next(l for l in lignes if l["categorie"] == "BETON")
        coffrage = next(l for l in lignes if l["categorie"] == "COFFRAGE")
        acier = next(l for l in lignes if l["categorie"] == "ACIER")

        # volume_beton = 1.5 * 1.5 * 0.40 = 0.90 m3
        self.assertEqual(beton["quantite"], 0.90)
        # surf_coffrage = 2 * (1.5 + 1.5) * 0.40 = 2.4 m2
        self.assertEqual(coffrage["quantite"], 2.4)
        # poids_acier = 0.90 * 50 = 45 kg
        self.assertEqual(acier["quantite"], 45.0)

    def test_calculer_projet_exclut_non_valides(self):
        # On passe un élément en statut PROPOSE et un en MODIFIE
        self.poutre.statut = ElementStructurel.Statut.PROPOSE
        self.poutre.save()
        
        self.semelle.statut = ElementStructurel.Statut.MODIFIE
        self.semelle.save()

        dqe_data = calculer_projet_dqe(self.projet)
        
        # Seul le poteau P1 doit être dans le DQE
        reperes = [l["repere"] for l in dqe_data["lignes"]]
        self.assertIn("P1", reperes)
        self.assertNotIn("PT1", reperes)
        self.assertNotIn("S1", reperes)

    def test_calculer_projet_dqe_global_avec_main_doeuvre(self):
        # Ajout d'un poste de main d'oeuvre
        PosteMainDoeuvre.objects.create(
            projet=self.projet,
            designation="Terrassement fouilles",
            unite="m³",
            quantite=15.0,
            prix_unitaire=5000.0
        )

        dqe_data = calculer_projet_dqe(self.projet)

        # Vérification de l'existence de la ligne de main d'œuvre
        mo_line = next(l for l in dqe_data["lignes"] if l["type_element"] == "MAIN_DOEUVRE")
        self.assertEqual(mo_line["designation"], "Terrassement fouilles")
        self.assertEqual(mo_line["montant"], 75000) # 15 * 5000

        # Vérification des sous-totaux
        self.assertEqual(dqe_data["sous_totaux"]["main_doeuvre"], 75000)


class DQEExportersTestCase(TestCase):
    def setUp(self):
        self.dqe_data = {
            "projet": {"id": 1, "nom": "Immeuble R+1"},
            "lignes": [
                {
                    "element_id": 1,
                    "repere": "P1",
                    "type_element": "POTEAU",
                    "designation": "Béton armé — Poteau P1",
                    "categorie": "BETON",
                    "unite": "m³",
                    "quantite": 0.12,
                    "prix_unitaire": 100000,
                    "montant": 12000
                }
            ],
            "sous_totaux": {
                "beton": 12000,
                "coffrage": 0,
                "acier": 0,
                "main_doeuvre": 0
            },
            "total_general": 12000,
            "devise": "FCFA"
        }

    def test_exporter_pdf(self):
        buffer = exporter_dqe_pdf(self.dqe_data)
        self.assertIsInstance(buffer, BytesIO)
        # Un PDF valide commence par le descripteur PDF %PDF
        self.assertTrue(buffer.getvalue().startswith(b"%PDF"))

    def test_exporter_excel(self):
        buffer = exporter_dqe_excel(self.dqe_data)
        self.assertIsInstance(buffer, BytesIO)
        
        # Test d'ouverture avec openpyxl pour vérifier l'intégrité du fichier Excel
        wb = load_workbook(buffer)
        self.assertIn("DQE", wb.sheetnames)
        ws = wb["DQE"]
        # Vérification d'une valeur dans la feuille
        self.assertEqual(ws["A1"].value, "DEVIS QUANTITATIF ESTIMATIF (DQE)")


class DQEAPITestCase(APITestCase):
    def setUp(self):
        self.projet = Projet.objects.create(
            nom="Projet API Test",
            usage_batiment="bureau",
            nb_niveaux=3
        )
        self.url = reverse("projet-generer-dqe", kwargs={"pk": self.projet.id})

    def test_generer_dqe_sans_elements_echoue(self):
        # Aucun élément dans le projet
        response = self.client.post(self.url, {"export": "pdf"})
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(response.data["detail"], "Aucun élément validé n'est disponible pour générer le DQE.")

    def test_generer_dqe_avec_elements_non_valides_echoue(self):
        # Ajout d'un élément non validé
        ElementStructurel.objects.create(
            projet=self.projet,
            type_element=ElementStructurel.TypeElement.POTEAU,
            identifiant="P1",
            hauteur_poteau=3.0,
            statut=ElementStructurel.Statut.PROPOSE
        )
        response = self.client.post(self.url, {"export": "pdf"})
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("erreur", response.data)
        self.assertIn("P1", response.data["elements_en_attente"])

    def test_generer_dqe_format_invalide_echoue(self):
        # Ajout d'un élément validé pour contourner la première étape
        ElementStructurel.objects.create(
            projet=self.projet,
            type_element=ElementStructurel.TypeElement.POTEAU,
            identifiant="P1",
            hauteur_poteau=3.0,
            resultat_calcul={"cote_cm": 20},
            resultat_valide={"cote_cm": 20},
            statut=ElementStructurel.Statut.VALIDE
        )
        response = self.client.post(self.url, {"export": "word"})
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(response.data["erreur"], "Le format d'export est requis et doit être 'pdf' ou 'excel'.")

    def test_generer_dqe_pdf_succes(self):
        ElementStructurel.objects.create(
            projet=self.projet,
            type_element=ElementStructurel.TypeElement.POTEAU,
            identifiant="P1",
            hauteur_poteau=3.0,
            resultat_calcul={"cote_cm": 20},
            resultat_valide={"cote_cm": 20},
            statut=ElementStructurel.Statut.VALIDE
        )
        # Test avec GET
        response = self.client.get(f"{self.url}?export=pdf")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response["Content-Type"], "application/pdf")
        self.assertTrue(response.content.startswith(b"%PDF"))

    def test_generer_dqe_excel_succes(self):
        ElementStructurel.objects.create(
            projet=self.projet,
            type_element=ElementStructurel.TypeElement.POTEAU,
            identifiant="P1",
            hauteur_poteau=3.0,
            resultat_calcul={"cote_cm": 20},
            resultat_valide={"cote_cm": 20},
            statut=ElementStructurel.Statut.VALIDE
        )
        # Test avec POST
        response = self.client.post(self.url, {"export": "excel"})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(
            response["Content-Type"],
            "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )
