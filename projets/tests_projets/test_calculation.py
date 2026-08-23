"""
Tests de services/calculations.py -- notamment le câblage entre le
lien `poteau_associe` (Module 6) et le moteur de calcul.
"""

from rest_framework.test import APITestCase

from projets.models import Projet, ElementStructurel, CoucheCharge
from projets.services import calculer_element
from projets.services.calculations import degression_renseignee


class TestLienSemellePoteau(APITestCase):
    """
    Régression : `poteau_associe.resultat_calcul["cote_cm"]` était lu
    dans calculations.py mais jamais transmis à dimensionner_semelle()
    -- le lien existait en base sans effet sur le calcul réel.
    """

    def setUp(self):
        self.projet = Projet.objects.create(
            nom="Immeuble test", usage_batiment="habitation", nb_niveaux=2
        )
        self.poteau = ElementStructurel.objects.create(
            projet=self.projet,
            type_element=ElementStructurel.TypeElement.POTEAU,
            identifiant="P1",
            charge_calculee=500,
            hauteur_poteau=3.0,
            # Résultat déjà calculé du poteau : côté 35 cm
            resultat_calcul={"cote_cm": 35.0},
        )

    def test_cote_poteau_transmis_au_calcul_de_semelle(self):
        semelle_liee = ElementStructurel.objects.create(
            projet=self.projet,
            type_element=ElementStructurel.TypeElement.SEMELLE,
            identifiant="S1",
            charge_calculee=500,
            taux_travail_sol=1.5,
            poteau_associe=self.poteau,
        )
        semelle_sans_lien = ElementStructurel.objects.create(
            projet=self.projet,
            type_element=ElementStructurel.TypeElement.SEMELLE,
            identifiant="S2",
            charge_calculee=500,
            taux_travail_sol=1.5,
            poteau_associe=None,
        )

        resultat_lie = calculer_element(semelle_liee)
        resultat_sans_lien = calculer_element(semelle_sans_lien)

        # Avec le lien : l'hypothèse par défaut (25 cm) n'est plus utilisée.
        self.assertFalse(resultat_lie["hypothese_cote_poteau"])
        # Sans lien : l'hypothèse par défaut reste utilisée.
        self.assertTrue(resultat_sans_lien["hypothese_cote_poteau"])
        # La hauteur de semelle doit refléter le vrai côté du poteau (35 cm),
        # donc différer du résultat obtenu avec l'hypothèse par défaut (25 cm).
        self.assertNotEqual(resultat_lie["hauteur_cm"], resultat_sans_lien["hauteur_cm"])


class TestDegressionChargesPoteau(APITestCase):
    """
    Régression Module 1 : calculer_descente_charges_complete() (moteur,
    déjà testé isolément) était codée mais jamais appelée par
    calculer_element() -- le poteau utilisait charge_calculee brute,
    sans dégression, même quand les portées étaient connues.
    """

    def setUp(self):
        self.projet = Projet.objects.create(
            nom="Immeuble R+3", usage_batiment="habitation", nb_niveaux=4
        )

    def test_poteau_sans_portees_garde_le_comportement_historique(self):
        """Sans portées/nb_niveaux_charges, on retombe sur charge_calculee brute."""
        poteau = ElementStructurel.objects.create(
            projet=self.projet,
            type_element=ElementStructurel.TypeElement.POTEAU,
            identifiant="P1",
            charge_calculee=450,
            hauteur_poteau=3.0,
        )
        self.assertFalse(degression_renseignee(poteau))
        resultat = calculer_element(poteau)
        self.assertNotIn("descente_charges", resultat)

    def test_poteau_avec_portees_declenche_la_descente_avec_degression(self):
        poteau = ElementStructurel.objects.create(
            projet=self.projet,
            type_element=ElementStructurel.TypeElement.POTEAU,
            identifiant="P1",
            hauteur_poteau=3.0,
            portee_gauche=4.0,
            portee_droite=4.0,
            portee_avant=3.0,
            portee_arriere=3.0,
            epaisseur_dalle=0.15,
            nb_niveaux_charges=4,
            avec_degression=True,
        )
        self.assertTrue(degression_renseignee(poteau))
        resultat = calculer_element(poteau)

        self.assertIn("descente_charges", resultat)
        descente = resultat["descente_charges"]
        self.assertTrue(descente["degression_appliquee"])
        # Coefficient de dégression à 3 étages sous la toiture (NF P06-001) : 0,90
        self.assertEqual(descente["coefficient_degression"], 0.90)
        # Le poteau doit avoir été dimensionné avec la charge cumulée du moteur,
        # pas une charge brute arbitraire.
        self.assertGreater(resultat["cote_cm"], 0)

    def test_avec_degression_false_desactive_la_reduction(self):
        poteau_sans_degression = ElementStructurel.objects.create(
            projet=self.projet,
            type_element=ElementStructurel.TypeElement.POTEAU,
            identifiant="P1",
            hauteur_poteau=3.0,
            portee_gauche=4.0,
            portee_droite=4.0,
            portee_avant=3.0,
            portee_arriere=3.0,
            epaisseur_dalle=0.15,
            nb_niveaux_charges=4,
            avec_degression=False,
        )
        resultat = calculer_element(poteau_sans_degression)
        descente = resultat["descente_charges"]
        self.assertFalse(descente["degression_appliquee"])
        self.assertEqual(descente["coefficient_degression"], 1.0)

    def test_couches_permanentes_module2_reprises_dans_la_descente(self):
        """Si des CoucheCharge existent sur l'élément, elles remplacent epaisseur_dalle."""
        poteau = ElementStructurel.objects.create(
            projet=self.projet,
            type_element=ElementStructurel.TypeElement.POTEAU,
            identifiant="P1",
            hauteur_poteau=3.0,
            portee_gauche=4.0,
            portee_droite=4.0,
            portee_avant=3.0,
            portee_arriere=3.0,
            epaisseur_dalle=0.15,
            nb_niveaux_charges=2,
        )
        CoucheCharge.objects.create(
            element=poteau,
            designation="Dalle béton",
            epaisseur_cm=15,
            poids_volumique_kn_m3=25.0,
        )
        CoucheCharge.objects.create(
            element=poteau,
            designation="Chape + carrelage",
            epaisseur_cm=5,
            poids_volumique_kn_m3=20.0,
        )
        resultat = calculer_element(poteau)
        descente = resultat["descente_charges"]
        # 0.15*25 + 0.05*20 = 4.75 kN/m2, contre 0.15*25 = 3.75 pour la dalle seule
        self.assertEqual(descente["charge_permanente_par_niveau_kn"] / descente["surface_influence_m2"], 4.75)
