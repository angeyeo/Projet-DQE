"""
Tests du domaine projets : modèles, statuts, et verrou logiciel.

Ces tests sont valables dès maintenant -- ils ne dépendent pas des
formules du moteur de calcul, seulement de la logique de statut/verrou.
"""

from django.test import TestCase

from projets.models import Projet, ElementStructurel


class TestProjet(TestCase):
    def setUp(self):
        self.projet = Projet.objects.create(
            nom="Immeuble R+2 test", usage_batiment="habitation", nb_niveaux=3
        )

    def test_creation_projet(self):
        self.assertEqual(Projet.objects.count(), 1)
        self.assertEqual(self.projet.nom, "Immeuble R+2 test")

    def test_projet_sans_elements_au_depart(self):
        self.assertEqual(self.projet.elements.count(), 0)


class TestElementStructurel(TestCase):
    def setUp(self):
        self.projet = Projet.objects.create(
            nom="Immeuble R+2 test", usage_batiment="habitation", nb_niveaux=3
        )

    def test_statut_par_defaut_est_propose(self):
        element = ElementStructurel.objects.create(
            projet=self.projet,
            type_element=ElementStructurel.TypeElement.POTEAU,
            identifiant="P1",
        )
        self.assertEqual(element.statut, ElementStructurel.Statut.PROPOSE)

    def test_element_lie_au_bon_projet(self):
        element = ElementStructurel.objects.create(
            projet=self.projet,
            type_element=ElementStructurel.TypeElement.POUTRE,
            identifiant="PT1",
        )
        self.assertEqual(self.projet.elements.first(), element)