"""
Tests d'isolation de moteur_calcul/formules/trame.py -- feuille de
route "Ma partie -- Backend", Jour 1 (fin de journée) et Jour 5
(stabilisation, cas limites 1x1).

Ces fonctions ne touchent pas la base -- elles sont testées ici en
isolation complète, indépendamment de la couche Django.
"""

from django.test import SimpleTestCase

from moteur_calcul.formules.trame import (
    generer_poteau_sur_grille,
    calculer_longueur_chainage,
)


class TestGenererPoteauSurGrille(SimpleTestCase):
    def test_poteau_angle_vs_centre_trame_2x1(self):
        """
        Trame 2x1 (2 travées en x, 1 en y), portées 5,0 x 4,0 m --
        exemple déjà calculé à la main dans la feuille de route :
        poteau central ~90 kN, poteau d'angle ~45 kN.
        """
        params_communs = dict(
            portee_x=5.0, portee_y=4.0, nb_travees_x=2, nb_travees_y=1,
            charge_exploitation=1.5, hauteur_etage=3.0,
        )
        angle = generer_poteau_sur_grille(i=0, j=0, **params_communs)
        centre = generer_poteau_sur_grille(i=1, j=0, **params_communs)

        self.assertLess(angle["charge_elu_kn"], centre["charge_elu_kn"])
        self.assertAlmostEqual(centre["charge_elu_kn"], 2 * angle["charge_elu_kn"], delta=0.5)
        self.assertAlmostEqual(angle["charge_elu_kn"], 45.0, delta=0.5)
        self.assertAlmostEqual(centre["charge_elu_kn"], 90.0, delta=0.5)

    def test_position_reelle_calculee_depuis_les_indices(self):
        resultat = generer_poteau_sur_grille(
            i=2, j=1, portee_x=5.0, portee_y=4.0, nb_travees_x=3, nb_travees_y=2,
            charge_exploitation=1.5, hauteur_etage=3.0,
        )
        self.assertEqual(resultat["x"], 10.0)
        self.assertEqual(resultat["y"], 4.0)

    def test_resultat_contient_poteau_et_semelle_dimensionnes(self):
        resultat = generer_poteau_sur_grille(
            i=1, j=1, portee_x=5.0, portee_y=4.0, nb_travees_x=2, nb_travees_y=2,
            charge_exploitation=1.5, hauteur_etage=3.0,
        )
        self.assertIn("cote_cm", resultat["resultat_poteau"])
        self.assertIn("cote_cm", resultat["resultat_semelle"])

    def test_fix_module6_cote_poteau_transmis_a_la_semelle(self):
        """
        Régression Module 6 : la semelle générée par la trame doit
        utiliser le vrai côté du poteau, pas l'hypothèse par défaut.
        """
        resultat = generer_poteau_sur_grille(
            i=1, j=1, portee_x=6.0, portee_y=6.0, nb_travees_x=2, nb_travees_y=2,
            charge_exploitation=4.0, hauteur_etage=3.0,
        )
        self.assertFalse(resultat["resultat_semelle"]["hypothese_cote_poteau"])

    def test_trame_1x1_les_deux_poteaux_sont_en_bord_aucun_au_centre(self):
        """
        Cas limite explicitement signalé dans la feuille de route
        (Jour 5) : avec nb_travees_x=1 et nb_travees_y=1, i et j ne
        valent que 0 ou 1 -- LES QUATRE poteaux sont en bord de grille,
        aucun n'est "au centre". Vérifie l'absence de surface nulle ou
        négative, et que les 4 poteaux (symétriques) portent la même charge.
        """
        params = dict(portee_x=5.0, portee_y=4.0, nb_travees_x=1, nb_travees_y=1,
                       charge_exploitation=1.5, hauteur_etage=3.0)
        charges = [
            generer_poteau_sur_grille(i=i, j=j, **params)["charge_elu_kn"]
            for i in (0, 1) for j in (0, 1)
        ]
        for charge in charges:
            self.assertGreater(charge, 0)
        self.assertAlmostEqual(min(charges), max(charges), delta=0.01)

    def test_indices_hors_grille_leve_une_erreur_explicite(self):
        with self.assertRaises(ValueError):
            generer_poteau_sur_grille(
                i=5, j=0, portee_x=5.0, portee_y=4.0, nb_travees_x=2, nb_travees_y=1,
                charge_exploitation=1.5, hauteur_etage=3.0,
            )


class TestCalculerLongueurChainage(SimpleTestCase):
    def test_exemple_feuille_de_route_2x1(self):
        """Trame 2x1, portées 5,0 x 4,0 m -> 32 ml (vérifié à la main)."""
        self.assertAlmostEqual(
            calculer_longueur_chainage(nb_travees_x=2, nb_travees_y=1, portee_x=5.0, portee_y=4.0),
            32.0,
        )

    def test_trame_carree(self):
        # 3x3 travées de 4m : x = 3*4*4=48, y = 3*4*4=48 -> 96
        self.assertAlmostEqual(
            calculer_longueur_chainage(nb_travees_x=3, nb_travees_y=3, portee_x=4.0, portee_y=4.0),
            96.0,
        )

    def test_trame_1x1(self):
        # x = 1*5*2=10, y = 1*4*2=8 -> 18 (un simple rectangle, 4 poteaux)
        self.assertAlmostEqual(
            calculer_longueur_chainage(nb_travees_x=1, nb_travees_y=1, portee_x=5.0, portee_y=4.0),
            18.0,
        )

    def test_trame_allongee_6x1(self):
        # x = 6*4*2=48, y = 1*4*7=28 -> 76
        self.assertAlmostEqual(
            calculer_longueur_chainage(nb_travees_x=6, nb_travees_y=1, portee_x=4.0, portee_y=4.0),
            76.0,
        )

    def test_zero_travee_leve_une_erreur(self):
        with self.assertRaises(ValueError):
            calculer_longueur_chainage(nb_travees_x=0, nb_travees_y=1, portee_x=5.0, portee_y=4.0)
