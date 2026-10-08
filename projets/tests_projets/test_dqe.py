from decimal import Decimal
from io import BytesIO
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APITestCase
from openpyxl import load_workbook

from projets.models import Projet, ElementStructurel, PosteComplementaire
from projets.services.dqe_calculator import DQEIncomplet, calculer_element_dqe, calculer_projet_dqe
from projets.tests_projets.utils import BAREME_TEST, authentifier
from projets.services.dqe_exporters import exporter_dqe_pdf, exporter_dqe_excel

class DQECalculatorTestCase(TestCase):
    def setUp(self):
        self.projet = Projet.objects.create(
            nom="Immeuble Test R+1",
            usage_batiment="habitation",
            nb_niveaux=2
        )
        # 1. Poteau (avec cote_cm inclus pour la compatibilité DQE)
        self.poteau = ElementStructurel.objects.create(
            projet=self.projet,
            type_element=ElementStructurel.TypeElement.POTEAU,
            identifiant="P1",
            hauteur_poteau=3.0,
            resultat_calcul={"cote_cm": 20, "largeur_cm": 20, "profondeur_cm": 20},
            resultat_valide={"cote_cm": 20, "largeur_cm": 20, "profondeur_cm": 20},
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
        lignes = calculer_element_dqe(self.poteau, BAREME_TEST)
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
        self.poteau.resultat_valide = {
            "cote_cm": 20,
            "largeur_cm": 20,
            "profondeur_cm": 20,
            "poids_acier_total_kg": 15.5,
            "poids_acier_kg": 15.5
        }
        self.poteau.save()

        lignes = calculer_element_dqe(self.poteau, BAREME_TEST)
        acier = next(l for l in lignes if l["categorie"] == "ACIER")
        self.assertEqual(acier["quantite"], 15.5)

    def test_calculer_element_poutre(self):
        lignes = calculer_element_dqe(self.poutre, BAREME_TEST)
        self.assertEqual(len(lignes), 3)

        beton = next(l for l in lignes if l["categorie"] == "BETON")
        coffrage = next(l for l in lignes if l["categorie"] == "COFFRAGE")
        acier = next(l for l in lignes if l["categorie"] == "ACIER")

        self.assertEqual(beton["quantite"], 0.40)
        self.assertEqual(coffrage["quantite"], 5.0)
        # poids_acier = 0.40 * 150 = 60 kg
        self.assertEqual(acier["quantite"], 60.0)

    def test_calculer_element_semelle(self):
        lignes = calculer_element_dqe(self.semelle, BAREME_TEST)
        self.assertEqual(len(lignes), 3)

        beton = next(l for l in lignes if l["categorie"] == "BETON")
        coffrage = next(l for l in lignes if l["categorie"] == "COFFRAGE")
        acier = next(l for l in lignes if l["categorie"] == "ACIER")

        self.assertEqual(beton["quantite"], 0.90)
        self.assertEqual(coffrage["quantite"], 2.4)
        # poids_acier = 0.90 * 50 = 45 kg
        self.assertEqual(acier["quantite"], 45.0)

    def test_calculer_projet_exclut_non_valides(self):
        self.poutre.statut = ElementStructurel.Statut.PROPOSE
        self.poutre.save()
        
        self.semelle.statut = ElementStructurel.Statut.MODIFIE
        self.semelle.save()

        dqe_data = calculer_projet_dqe(self.projet, BAREME_TEST)
        
        reperes = [l["repere"] for l in dqe_data["lignes"]]
        self.assertIn("P1", reperes)
        self.assertNotIn("PT1", reperes)
        self.assertNotIn("S1", reperes)

    def test_calculer_projet_dqe_global_avec_main_doeuvre(self):
        PosteComplementaire.objects.create(
            projet=self.projet,
            lot=PosteComplementaire.Lot.ELECTRICITE,
            designation="Terrassement fouilles",
            unite="m³",
            quantite=15.0,
            prix_unitaire=5000.0
        )

        dqe_data = calculer_projet_dqe(self.projet, BAREME_TEST)

        mo_line = next(l for l in dqe_data["lignes"] if l["type_element"] == "MAIN_DOEUVRE")
        self.assertEqual(mo_line["designation"], "Terrassement fouilles")
        self.assertEqual(mo_line["montant"], 75000)

        # Un sous-total plat "main_doeuvre" mélangerait main d'œuvre et
        # gros œuvre dans un seul total sans distinction de lot ; les
        # postes de main d'œuvre sont donc comptabilisés dans le
        # sous-total de LEUR lot (voir calculer_projet_dqe).
        lot_electricite = next(
            l for l in dqe_data["lots"] if l["lot"] == PosteComplementaire.Lot.ELECTRICITE.value
        )
        self.assertEqual(lot_electricite["sous_total"], 75000)

    def test_calculer_element_dalle(self):
        dalle = ElementStructurel.objects.create(
            projet=self.projet,
            type_element=ElementStructurel.TypeElement.DALLE,
            identifiant="D1",
            portee=4.0,
            surface_m2=50.0,
            resultat_calcul={"epaisseur_cm": 15},
            resultat_valide={"epaisseur_cm": 15},
            statut=ElementStructurel.Statut.VALIDE
        )
        lignes = calculer_element_dqe(dalle, BAREME_TEST)
        self.assertEqual(len(lignes), 3)

        beton = next(l for l in lignes if l["categorie"] == "BETON")
        coffrage = next(l for l in lignes if l["categorie"] == "COFFRAGE")
        acier = next(l for l in lignes if l["categorie"] == "ACIER")

        self.assertEqual(beton["quantite"], 7.5)
        self.assertEqual(coffrage["quantite"], 50.0)
        self.assertEqual(acier["quantite"], 637.5)

    def test_calculer_element_semelle_filante_poids_moteur(self):
        sf = ElementStructurel.objects.create(
            projet=self.projet,
            type_element=ElementStructurel.TypeElement.SEMELLE_FILANTE,
            identifiant="SF1",
            longueur_m=10.0,
            resultat_calcul={
                "largeur_cm": 50,
                "hauteur_cm": 30,
                "acier_transversal_cm2_ml": 4.0,
                "acier_repartition_cm2_ml": 2.0
            },
            resultat_valide={
                "largeur_cm": 50,
                "hauteur_cm": 30,
                "acier_transversal_cm2_ml": 4.0,
                "acier_repartition_cm2_ml": 2.0
            },
            statut=ElementStructurel.Statut.VALIDE
        )
        lignes = calculer_element_dqe(sf, BAREME_TEST)
        self.assertEqual(len(lignes), 3)

        beton = next(l for l in lignes if l["categorie"] == "BETON")
        coffrage = next(l for l in lignes if l["categorie"] == "COFFRAGE")
        acier = next(l for l in lignes if l["categorie"] == "ACIER")

        self.assertEqual(beton["quantite"], 1.5)
        self.assertEqual(coffrage["quantite"], 6.0)
        self.assertEqual(acier["quantite"], 47.1)  # 6.0 cm2/ml * 10m * 7.85 kg/m/cm2 = 47.1 kg

    def test_calculer_element_semelle_filante_ratio(self):
        sf = ElementStructurel.objects.create(
            projet=self.projet,
            type_element=ElementStructurel.TypeElement.SEMELLE_FILANTE,
            identifiant="SF1",
            longueur_m=10.0,
            resultat_calcul={
                "largeur_cm": 50,
                "hauteur_cm": 30
            },
            resultat_valide={
                "largeur_cm": 50,
                "hauteur_cm": 30
            },
            statut=ElementStructurel.Statut.VALIDE
        )
        lignes = calculer_element_dqe(sf, BAREME_TEST)
        self.assertEqual(len(lignes), 3)

        beton = next(l for l in lignes if l["categorie"] == "BETON")
        coffrage = next(l for l in lignes if l["categorie"] == "COFFRAGE")
        acier = next(l for l in lignes if l["categorie"] == "ACIER")

        self.assertEqual(beton["quantite"], 1.5)
        self.assertEqual(coffrage["quantite"], 6.0)
        self.assertEqual(acier["quantite"], 75.0)  # 1.5 m3 * 50 kg/m3 = 75.0 kg

    def test_calculer_projet_dqe_global_cinq_elements(self):
        # On ajoute les 2 types Phase 2 manquants au projet du setUp
        ElementStructurel.objects.create(
            projet=self.projet,
            type_element=ElementStructurel.TypeElement.DALLE,
            identifiant="D1",
            portee=4.0,
            surface_m2=50.0,
            resultat_calcul={"epaisseur_cm": 15},
            resultat_valide={"epaisseur_cm": 15},
            statut=ElementStructurel.Statut.VALIDE
        )
        ElementStructurel.objects.create(
            projet=self.projet,
            type_element=ElementStructurel.TypeElement.SEMELLE_FILANTE,
            identifiant="SF1",
            longueur_m=10.0,
            resultat_calcul={"largeur_cm": 50, "hauteur_cm": 30},
            resultat_valide={"largeur_cm": 50, "hauteur_cm": 30},
            statut=ElementStructurel.Statut.VALIDE
        )

        dqe_data = calculer_projet_dqe(self.projet, BAREME_TEST)

        # Vérification des sous-totaux par catégorie
        # Béton : 0.12 (poteau) + 0.40 (poutre) + 0.90 (semelle) + 7.50 (dalle) + 1.50 (semelle filante) = 10.42 m3
        # Cost : 10.42 * 100 000 = 1 042 000 FCFA
        self.assertEqual(dqe_data["sous_totaux"]["beton"], 1042000)

        # Coffrage : 2.4 (poteau) + 5.0 (poutre) + 2.4 (semelle) + 50.0 (dalle) + 6.0 (semelle filante) = 65.8 m2
        # Cost : 65.8 * 12 000 = 789 600 FCFA
        self.assertEqual(dqe_data["sous_totaux"]["coffrage"], 789600)

        # Acier : 15.0 (poteau) + 60.0 (poutre) + 45.0 (semelle) + 637.5 (dalle) + 75.0 (semelle filante) = 832.5 kg
        # Cost : 832.5 * 800 = 666 000 FCFA
        self.assertEqual(dqe_data["sous_totaux"]["acier"], 666000)

        # Total Général : 1 042 000 + 789 600 + 666 000 = 2 497 600 FCFA
        self.assertEqual(dqe_data["total_general"], 2497600)

    def test_acier_au_ratio_signale_comme_estimation(self):
        acier = next(l for l in calculer_element_dqe(self.poteau, BAREME_TEST) if l["categorie"] == "ACIER")
        self.assertEqual(acier["source_quantite"], "ratio_reference")
        self.assertIn("125", acier["hypothese"])

    def test_prix_manquant_erreur_explicite_sans_valeur_par_defaut(self):
        bareme = {k: v for k, v in BAREME_TEST.items() if k != "acier_kg"}
        with self.assertRaises(DQEIncomplet) as ctx:
            calculer_projet_dqe(self.projet, bareme)
        codes = {(p["code"], p.get("cle_prix")) for p in ctx.exception.problemes}
        self.assertIn(("PRIX_MANQUANT", "acier_kg"), codes)

    def test_dimension_manquante_bloque_au_lieu_d_omettre(self):
        self.poutre.portee = None
        self.poutre.save()
        with self.assertRaises(DQEIncomplet) as ctx:
            calculer_projet_dqe(self.projet, BAREME_TEST)
        probleme = ctx.exception.problemes[0]
        self.assertEqual(probleme["code"], "DIMENSION_MANQUANTE")
        self.assertEqual(probleme["repere"], "PT1")

    def test_poste_simple_quantite_nulle_bloque(self):
        PosteComplementaire.objects.create(
            projet=self.projet, lot=PosteComplementaire.Lot.PLOMBERIE,
            designation="Réseau", unite="ml", quantite=None, prix_unitaire=2000,
        )
        with self.assertRaises(DQEIncomplet) as ctx:
            calculer_projet_dqe(self.projet, BAREME_TEST)
        self.assertEqual(ctx.exception.problemes[0]["code"], "POSTE_INCOMPLET")

    def test_poste_ratio_maconnerie_inclus_et_classe_en_maconnerie(self):
        """Périmètre 40 m, soubassement 0,6 m, agglos 15 pleins (unité m², validée) :
        S = 40 x 0,6 = 24 m² -> 24 x 9 000 = 216 000 FCFA.
        Élévation : 40 x 3 x 1 niveau x 0,8 (hypothèse signalée) = 96 m²."""
        PosteComplementaire.objects.create(
            projet=self.projet, lot=PosteComplementaire.Lot.GROS_OEUVRE_INFRA,
            mode=PosteComplementaire.Mode.RATIO, type_poste="maconnerie",
            geometrie={"perimetre_batiment_m": 40, "hauteur_soubassement_m": 0.6,
                       "hauteur_etage_m": 3, "nb_niveaux": 1},
        )
        dqe = calculer_projet_dqe(self.projet, BAREME_TEST)
        infra = next(l for l in dqe["lignes"] if "pleins" in l["designation"])
        self.assertEqual(infra["categorie"], "MACONNERIE")
        self.assertEqual(infra["unite"], "m²")
        self.assertEqual(infra["quantite"], 24.0)
        self.assertEqual(infra["montant"], 216000)
        self.assertEqual(infra["cle_prix"], "agglos_15_pleins_m2")
        elev = next(l for l in dqe["lignes"] if "creux" in l["designation"])
        self.assertEqual(elev["quantite"], 96.0)
        self.assertIn("0.8", elev["hypothese"])
        # Les agglos ne gonflent pas le volume de BÉTON du projet
        self.assertEqual(dqe["synthese"]["beton_m3"], 1.42)

    def test_ancien_prix_agglos_au_m3_jamais_converti(self):
        """Un barème qui n'a que l'ancien prix « au m³ » bloque la ligne avec un
        message explicite : aucune conversion m³ -> m² implicite."""
        PosteComplementaire.objects.create(
            projet=self.projet, lot=PosteComplementaire.Lot.GROS_OEUVRE_INFRA,
            mode=PosteComplementaire.Mode.RATIO, type_poste="maconnerie",
            geometrie={"perimetre_batiment_m": 40, "hauteur_soubassement_m": 0.6},
        )
        bareme = {k: v for k, v in BAREME_TEST.items() if k != "agglos_15_pleins_m2"} | {"agglos_pleins_m3": 9000}
        with self.assertRaises(DQEIncomplet) as ctx:
            calculer_projet_dqe(self.projet, bareme)
        codes = [p["code"] for p in ctx.exception.problemes]
        self.assertIn("PRIX_UNITE_A_CONFIRMER", codes)
        self.assertIn("aucune conversion automatique", str(ctx.exception))

    def test_poste_ratio_geometrie_incomplete_bloque(self):
        PosteComplementaire.objects.create(
            projet=self.projet, lot=PosteComplementaire.Lot.GROS_OEUVRE_SUPER,
            mode=PosteComplementaire.Mode.RATIO, type_poste="chainage",
            geometrie={"perimetre_batiment_m": 40},
        )
        with self.assertRaises(DQEIncomplet) as ctx:
            calculer_projet_dqe(self.projet, BAREME_TEST)
        self.assertEqual(ctx.exception.problemes[0]["code"], "GEOMETRIE_INCOMPLETE")

    def test_montant_egal_quantite_affichee_fois_prix(self):
        self.poutre.portee = 3.3333
        self.poutre.save()
        dqe = calculer_projet_dqe(self.projet, BAREME_TEST)
        for ligne in dqe["lignes"]:
            attendu = round(ligne["quantite"] * ligne["prix_unitaire"])
            self.assertEqual(ligne["montant"], attendu, ligne["designation"])

    def test_synthese_ratio_acier_beton(self):
        dqe = calculer_projet_dqe(self.projet, BAREME_TEST)
        # béton 0,12 + 0,40 + 0,90 = 1,42 m³ ; acier 15 + 60 + 45 = 120 kg
        self.assertEqual(dqe["synthese"]["beton_m3"], 1.42)
        self.assertEqual(dqe["synthese"]["acier_kg"], 120.0)
        self.assertEqual(dqe["synthese"]["ratio_acier_kg_m3"], 84.5)


class DQEExportersTestCase(TestCase):
    def setUp(self):
        ligne_poteau = {
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
        self.dqe_data = {
            "projet": {"id": 1, "nom": "Immeuble R+1"},
            "lignes": [ligne_poteau],
            "lots": [
                {
                    "lot": "lot_02_gros_oeuvre_superstructure",
                    "lignes": [ligne_poteau],
                    "sous_total": 12000,
                }
            ],
            "sous_totaux": {
                "beton": 12000,
                "coffrage": 0,
                "acier": 0,
            },
            "total_general": 12000,
            "montant_lettres": "douze mille",
            "devise": "FCFA"
        }

    def test_exporter_pdf(self):
        buffer = exporter_dqe_pdf(self.dqe_data)
        self.assertIsInstance(buffer, BytesIO)
        self.assertTrue(buffer.getvalue().startswith(b"%PDF"))

    def test_exporter_excel(self):
        buffer = exporter_dqe_excel(self.dqe_data)
        self.assertIsInstance(buffer, BytesIO)

        wb = load_workbook(buffer)
        # La feuille "Récapitulatif" (total par lot) remplace l'ancienne
        # feuille unique "DQE" ; le détail est désormais réparti sur une
        # feuille par lot (voir dqe_exporters.exporter_dqe_excel).
        self.assertIn("Récapitulatif", wb.sheetnames)
        ws = wb["Récapitulatif"]
        self.assertEqual(ws["A1"].value, "DEVIS QUANTITATIF ET ESTIMATIF (DQE)")

        self.assertIn("LOT 02 — GROS ŒUVRE", wb.sheetnames)


class DQEAPITestCase(APITestCase):
    def setUp(self):
        self.user, self.cabinet = authentifier(self, bareme=BAREME_TEST)
        self.projet = Projet.objects.create(
            nom="Projet API Test",
            usage_batiment="bureau",
            nb_niveaux=3,
            entreprise=self.cabinet,
        )
        self.url = reverse("projet-generer-dqe", kwargs={"pk": self.projet.id})

    def test_generer_dqe_sans_elements_echoue(self):
        # Aucun élément dans le projet
        response = self.client.get(f"{self.url}?export=pdf")
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("rien à chiffrer", response.data["erreur"])

    def test_generer_dqe_avec_elements_non_valides_echoue(self):
        ElementStructurel.objects.create(
            projet=self.projet,
            type_element=ElementStructurel.TypeElement.POTEAU,
            identifiant="P1",
            hauteur_poteau=3.0,
            statut=ElementStructurel.Statut.PROPOSE
        )
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("erreur", response.data)
        self.assertIn("P1", response.data["elements_en_attente"])

    def test_generer_dqe_format_invalide_echoue(self):
        ElementStructurel.objects.create(
            projet=self.projet,
            type_element=ElementStructurel.TypeElement.POTEAU,
            identifiant="P1",
            hauteur_poteau=3.0,
            resultat_calcul={"cote_cm": 20, "largeur_cm": 20, "profondeur_cm": 20},
            resultat_valide={"cote_cm": 20, "largeur_cm": 20, "profondeur_cm": 20},
            statut=ElementStructurel.Statut.VALIDE
        )
        response = self.client.get(f"{self.url}?export=word")
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("erreur", response.data)

    def test_generer_dqe_pdf_succes(self):
        ElementStructurel.objects.create(
            projet=self.projet,
            type_element=ElementStructurel.TypeElement.POTEAU,
            identifiant="P1",
            hauteur_poteau=3.0,
            resultat_calcul={"cote_cm": 20, "largeur_cm": 20, "profondeur_cm": 20},
            resultat_valide={"cote_cm": 20, "largeur_cm": 20, "profondeur_cm": 20},
            statut=ElementStructurel.Statut.VALIDE
        )
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
            resultat_calcul={"cote_cm": 20, "largeur_cm": 20, "profondeur_cm": 20},
            resultat_valide={"cote_cm": 20, "largeur_cm": 20, "profondeur_cm": 20},
            statut=ElementStructurel.Statut.VALIDE
        )
        # Test avec GET
        response = self.client.get(f"{self.url}?export=excel")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(
            response["Content-Type"],
            "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )
    def test_prix_manquant_dans_bareme_renvoie_liste_de_problemes(self):
        self.cabinet.prix_unitaires = {}
        self.cabinet.save()
        ElementStructurel.objects.create(
            projet=self.projet, type_element=ElementStructurel.TypeElement.POTEAU, identifiant="P1",
            hauteur_poteau=3.0, resultat_valide={"cote_cm": 20}, statut=ElementStructurel.Statut.VALIDE,
        )
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        cles = [p.get("cle_prix") for p in response.data["problemes"]]
        self.assertEqual(sorted(cles), ["acier_kg", "beton_m3", "coffrage_m2"])  # une fois chacun
        self.assertIn("1 ouvrage(s)", response.data["problemes"][0]["message"])

    def test_bareme_d_un_autre_cabinet_jamais_utilise(self):
        from projets.tests_projets.utils import creer_cabinet
        creer_cabinet("Autre", bareme={"beton_m3": 1, "acier_kg": 1, "coffrage_m2": 1})
        ElementStructurel.objects.create(
            projet=self.projet, type_element=ElementStructurel.TypeElement.POTEAU, identifiant="P1",
            hauteur_poteau=3.0, resultat_valide={"cote_cm": 20}, statut=ElementStructurel.Statut.VALIDE,
        )
        response = self.client.get(self.url)
        beton = next(l for l in response.data["lignes"] if l["categorie"] == "BETON")
        self.assertEqual(beton["prix_unitaire"], 100000)

    def test_generation_enregistre_un_evenement_reel(self):
        from projets.models import EvenementProduit
        ElementStructurel.objects.create(
            projet=self.projet, type_element=ElementStructurel.TypeElement.POTEAU, identifiant="P1",
            hauteur_poteau=3.0, resultat_valide={"cote_cm": 20}, statut=ElementStructurel.Statut.VALIDE,
        )
        response = self.client.get(self.url)
        ev = EvenementProduit.objects.get(type="dqe_genere")
        self.assertEqual(ev.donnees["total_general"], response.data["total_general"])
        self.assertEqual(ev.entreprise_id, self.cabinet.id)
