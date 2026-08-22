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
    generer_poteau_depuis_position_reelle,
    generer_poutre_depuis_positions_reelles,
    detecter_poutres_adjacentes,
    _trouver_voisin_direct,
)


class TestDegressionBrancheeSurLaTrame(SimpleTestCase):
    """
    Régression : avant ce test, generer_poteau_sur_grille() calculait
    toujours la charge d'UN SEUL niveau, quel que soit nb_niveaux réel
    du projet -- un poteau de RDC d'un immeuble R+4 était dimensionné
    comme une maison de plain-pied. Voir _cumuler_charge_poteau_multi_niveaux.
    """

    PARAMS = dict(
        portee_x=5.0, portee_y=4.0, nb_travees_x=2, nb_travees_y=1,
        charge_exploitation=1.5, hauteur_etage=3.0,
    )

    def test_defaut_nb_niveaux_1_comportement_inchange(self):
        """Sans préciser nb_niveaux, le résultat doit rester identique à avant (1 niveau)."""
        resultat = generer_poteau_sur_grille(i=1, j=0, **self.PARAMS)
        self.assertAlmostEqual(resultat["charge_elu_kn"], 90.0, delta=0.5)
        self.assertFalse(resultat["degression_appliquee"])

    def test_charge_augmente_avec_le_nombre_de_niveaux(self):
        un_niveau = generer_poteau_sur_grille(i=1, j=0, **self.PARAMS, nb_niveaux=1)
        cinq_niveaux = generer_poteau_sur_grille(
            i=1, j=0, **self.PARAMS, nb_niveaux=5, usage_batiment="habitation"
        )
        self.assertGreater(cinq_niveaux["charge_elu_kn"], un_niveau["charge_elu_kn"])

    def test_degression_reduit_la_charge_par_rapport_a_une_sommation_simple(self):
        """
        La dégression doit toujours réduire (ou laisser égale) la charge
        cumulée par rapport à une simple sommation des étages -- jamais
        l'augmenter.
        """
        avec_degression = generer_poteau_sur_grille(
            i=1, j=0, **self.PARAMS, nb_niveaux=5, usage_batiment="habitation"
        )
        sans_degression = generer_poteau_sur_grille(
            i=1, j=0, **self.PARAMS, nb_niveaux=5, usage_batiment="commerce"
        )
        self.assertTrue(avec_degression["degression_appliquee"])
        self.assertFalse(sans_degression["degression_appliquee"])
        self.assertLess(avec_degression["charge_elu_kn"], sans_degression["charge_elu_kn"])

    def test_generer_poteau_depuis_position_reelle_accepte_aussi_nb_niveaux(self):
        poteau = _poteau("P1", 0.0, 0.0)
        voisins = [poteau, _poteau("P2", 5.0, 0.0), _poteau("P3", 0.0, 4.0)]
        resultat = generer_poteau_depuis_position_reelle(
            poteau, voisins, charge_exploitation=1.5, hauteur_etage=3.0,
            nb_niveaux=3, usage_batiment="bureau",
        )
        self.assertIn("degression_appliquee", resultat)
        self.assertEqual(resultat["nb_niveaux"], 3)


def _poteau(nom, x, y):
    """Fixture minimale au format extraire_poteaux() (Phase A)."""
    return {"nom": nom, "guid": nom, "x": x, "y": y, "z": 0.0}


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


class TestGenererPoteauDepuisPositionReelle(SimpleTestCase):
    def _nuage_2x1(self):
        """Même trame 2x1, 5,0x4,0 m que TestGenererPoteauSurGrille, mais
        comme nuage de points réel (positions absolues) plutôt qu'indices."""
        return [
            _poteau("A", 0.0, 0.0), _poteau("B", 5.0, 0.0), _poteau("C", 10.0, 0.0),
            _poteau("D", 0.0, 4.0), _poteau("E", 5.0, 4.0), _poteau("F", 10.0, 4.0),
        ]

    def test_equivalent_a_generer_poteau_sur_grille_sur_grille_reguliere(self):
        """Sur une grille parfaitement régulière, la version Phase B doit
        retomber sur exactement les mêmes charges que la version grille."""
        voisins = self._nuage_2x1()
        params_communs = dict(
            portee_x=5.0, portee_y=4.0, nb_travees_x=2, nb_travees_y=1,
            charge_exploitation=1.5, hauteur_etage=3.0,
        )
        angle_grille = generer_poteau_sur_grille(i=0, j=0, **params_communs)
        centre_grille = generer_poteau_sur_grille(i=1, j=0, **params_communs)

        poteau_a = next(p for p in voisins if p["nom"] == "A")
        poteau_b = next(p for p in voisins if p["nom"] == "B")
        angle_reel = generer_poteau_depuis_position_reelle(
            poteau_a, voisins, charge_exploitation=1.5, hauteur_etage=3.0
        )
        centre_reel = generer_poteau_depuis_position_reelle(
            poteau_b, voisins, charge_exploitation=1.5, hauteur_etage=3.0
        )

        self.assertAlmostEqual(angle_reel["charge_elu_kn"], angle_grille["charge_elu_kn"], places=6)
        self.assertAlmostEqual(centre_reel["charge_elu_kn"], centre_grille["charge_elu_kn"], places=6)
        self.assertEqual(angle_reel["x"], 0.0)
        self.assertEqual(angle_reel["y"], 0.0)

    def test_poteau_isole_sans_voisin_leve_une_erreur_explicite(self):
        """Aucun voisin détecté dans aucune direction -> surface nulle :
        erreur explicite plutôt que de laisser planter dimensionner_poteau
        plus loin avec une charge nulle."""
        poteau_seul = _poteau("SEUL", 0.0, 0.0)
        with self.assertRaises(ValueError):
            generer_poteau_depuis_position_reelle(
                poteau_seul, [poteau_seul], charge_exploitation=1.5, hauteur_etage=3.0
            )

    def test_grille_irreguliere_utilise_les_distances_reelles(self):
        """Portées différentes de chaque côté (poteau non centré) --
        la surface doit refléter les distances réelles, pas une moyenne."""
        voisins = [
            _poteau("A", 0.0, 0.0), _poteau("B", 3.0, 0.0), _poteau("C", 8.0, 0.0),
            _poteau("A2", 0.0, 4.0), _poteau("B2", 3.0, 4.0), _poteau("C2", 8.0, 4.0),
        ]
        poteau_b = next(p for p in voisins if p["nom"] == "B")
        resultat = generer_poteau_depuis_position_reelle(
            poteau_b, voisins, charge_exploitation=1.5, hauteur_etage=3.0
        )
        self.assertAlmostEqual(resultat["portees_detectees"]["gauche"], 3.0)
        self.assertAlmostEqual(resultat["portees_detectees"]["droite"], 5.0)
        self.assertAlmostEqual(resultat["portees_detectees"]["avant"], 0.0)
        self.assertAlmostEqual(resultat["portees_detectees"]["arriere"], 4.0)

    def test_traçabilite_guid_et_nom_transmis(self):
        voisins = self._nuage_2x1()
        poteau_b = next(p for p in voisins if p["nom"] == "B")
        resultat = generer_poteau_depuis_position_reelle(
            poteau_b, voisins, charge_exploitation=1.5, hauteur_etage=3.0
        )
        self.assertEqual(resultat["guid"], "B")
        self.assertEqual(resultat["nom"], "B")


class TestTrouverVoisinDirect(SimpleTestCase):
    def test_ignore_les_poteaux_non_alignes(self):
        """Un poteau décalé en y de plus que la tolérance ne doit pas être
        considéré comme voisin sur l'axe x."""
        origine = _poteau("O", 0.0, 0.0)
        voisins = [origine, _poteau("DECALE", 5.0, 1.0)]
        voisin, distance = _trouver_voisin_direct(origine, voisins, axe="x", sens=1)
        self.assertIsNone(voisin)
        self.assertEqual(distance, 0.0)

    def test_retient_le_plus_proche_parmi_plusieurs_alignes(self):
        origine = _poteau("O", 0.0, 0.0)
        voisins = [origine, _poteau("PROCHE", 3.0, 0.0), _poteau("LOIN", 8.0, 0.0)]
        voisin, distance = _trouver_voisin_direct(origine, voisins, axe="x", sens=1)
        self.assertEqual(voisin["nom"], "PROCHE")
        self.assertAlmostEqual(distance, 3.0)


class TestGenererPoutreDepuisPositionsReelles(SimpleTestCase):
    def test_equivalent_a_generer_poutre_sur_grille_sur_grille_reguliere(self):
        voisins = [
            _poteau("A", 0.0, 0.0), _poteau("B", 5.0, 0.0),
            _poteau("D", 0.0, 4.0), _poteau("E", 5.0, 4.0),
        ]
        poteau_a = next(p for p in voisins if p["nom"] == "A")
        poteau_b = next(p for p in voisins if p["nom"] == "B")
        resultat = generer_poutre_depuis_positions_reelles(
            poteau_a, poteau_b, axe="x", voisins=voisins, charge_exploitation=1.5
        )
        self.assertAlmostEqual(resultat["portee_m"], 5.0)
        self.assertEqual(resultat["poteau_origine_guid"], "A")
        self.assertEqual(resultat["poteau_destination_guid"], "B")
        self.assertIn("hauteur_cm", resultat["resultat_poutre"])

    def test_detecter_poutres_adjacentes_pas_de_doublon(self):
        """Trame 2x1 (6 poteaux) -> 7 poutres attendues (3 en x sur chaque
        rangée y=0 et y=4, soit 4, + 3 en y entre les deux rangées),
        chaque segment une seule fois."""
        voisins = [
            _poteau("A", 0.0, 0.0), _poteau("B", 5.0, 0.0), _poteau("C", 10.0, 0.0),
            _poteau("D", 0.0, 4.0), _poteau("E", 5.0, 4.0), _poteau("F", 10.0, 4.0),
        ]
        poutres = detecter_poutres_adjacentes(voisins, charge_exploitation=1.5)
        self.assertEqual(len(poutres), 7)
        paires = {(p["poteau_origine_guid"], p["poteau_destination_guid"]) for p in poutres}
        self.assertEqual(len(paires), len(poutres))  # aucune paire générée deux fois


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