import json
from unittest.mock import patch

from django.test import SimpleTestCase
from rest_framework.test import APITestCase

from moteur_calcul.constantes import NB_NIVEAUX_MAX, PORTEE_MAX_M, PORTEE_MIN_M
from moteur_calcul.validators import CONTRAINTE_SOL_MAX_KN_M2, CONTRAINTE_SOL_MIN_KN_M2
from projets.models import Projet
from projets.services.assistant_ia.parser import structurer_description_projet
from projets.services.assistant_ia.prompts import PROMPT_STRUCTURATION
from projets.services.assistant_ia.schemas import valider_donnees_extraites
from projets.tests_projets.utils import authentifier


class BornesStructurationIATests(SimpleTestCase):
    def test_niveaux_aux_bornes_metier(self):
        for valeur in (1, NB_NIVEAUX_MAX):
            with self.subTest(valeur=valeur):
                self.assertEqual(valider_donnees_extraites({'nombre_niveaux': valeur})['nombre_niveaux'], valeur)

    def test_niveaux_hors_limite_rejetes_sans_correction(self):
        for valeur in (NB_NIVEAUX_MAX + 1, 100):
            with self.subTest(valeur=valeur), self.assertRaisesRegex(ValueError, str(NB_NIVEAUX_MAX)):
                valider_donnees_extraites({'nombre_niveaux': valeur})

    def test_reponse_mock_hors_limite_rejetee(self):
        with patch('projets.services.assistant_ia.parser.get_ai_client') as client:
            client.return_value.appeler_llm.return_value = json.dumps({'nombre_niveaux': 21})
            with self.assertRaisesRegex(ValueError, str(NB_NIVEAUX_MAX)):
                structurer_description_projet('Bâtiment de 21 niveaux')

    def test_portees_aux_bornes_metier(self):
        for champ in ('portee_m', 'portee_x_m', 'portee_y_m'):
            for valeur in (PORTEE_MIN_M, PORTEE_MAX_M):
                with self.subTest(champ=champ, valeur=valeur):
                    self.assertEqual(valider_donnees_extraites({champ: valeur})[champ], valeur)

    def test_portees_hors_limite_rejetees_sans_correction(self):
        for champ in ('portee_m', 'portee_x_m', 'portee_y_m'):
            for valeur in (PORTEE_MIN_M - 0.01, PORTEE_MAX_M + 0.01):
                with self.subTest(champ=champ, valeur=valeur), self.assertRaisesRegex(ValueError, 'comprise entre'):
                    valider_donnees_extraites({champ: valeur})

    def test_contrainte_sol_alignee_sur_le_backend(self):
        for valeur in (CONTRAINTE_SOL_MIN_KN_M2, CONTRAINTE_SOL_MAX_KN_M2):
            self.assertEqual(valider_donnees_extraites({'contrainte_sol_kn_m2': valeur})['contrainte_sol_kn_m2'], valeur)
        for valeur in (CONTRAINTE_SOL_MIN_KN_M2 - 1, CONTRAINTE_SOL_MAX_KN_M2 + 1):
            with self.subTest(valeur=valeur), self.assertRaises(ValueError):
                valider_donnees_extraites({'contrainte_sol_kn_m2': valeur})

    def test_hauteur_reste_strictement_positive_sans_borne_inventee(self):
        self.assertEqual(valider_donnees_extraites({'hauteur_niveau_m': 25})['hauteur_niveau_m'], 25)
        with self.assertRaisesRegex(ValueError, 'strictement positive'):
            valider_donnees_extraites({'hauteur_niveau_m': 0})

    def test_prompt_reprend_les_constantes_metier(self):
        self.assertIn(f'entier de 1 à {NB_NIVEAUX_MAX}', PROMPT_STRUCTURATION)
        self.assertIn(f'de {PORTEE_MIN_M} à {PORTEE_MAX_M}', PROMPT_STRUCTURATION)
        self.assertIn(
            f'de {CONTRAINTE_SOL_MIN_KN_M2:g} à {CONTRAINTE_SOL_MAX_KN_M2:g}',
            PROMPT_STRUCTURATION,
        )


class ReferentielBornesAPITests(APITestCase):
    def setUp(self):
        self.user, self.cabinet = authentifier(self)
        self.projet = Projet.objects.create(nom='Bornes', entreprise=self.cabinet)
        self.url = f'/api/projets/{self.projet.pk}/'

    def test_referentiel_expose_les_bornes_du_moteur(self):
        data = self.client.get('/api/referentiel/').data['limites_structuration']
        self.assertEqual(data, {
            'nb_niveaux_max': NB_NIVEAUX_MAX,
            'portee_min_m': PORTEE_MIN_M,
            'portee_max_m': PORTEE_MAX_M,
            'contrainte_sol_min_kn_m2': CONTRAINTE_SOL_MIN_KN_M2,
            'contrainte_sol_max_kn_m2': CONTRAINTE_SOL_MAX_KN_M2,
        })

    def test_serializer_refuse_21_niveaux_sans_correction(self):
        response = self.client.patch(self.url, {'nb_niveaux': 21}, format='json')
        self.assertEqual(response.status_code, 400)
        self.assertIn(str(NB_NIVEAUX_MAX), str(response.data['nb_niveaux']))
        self.projet.refresh_from_db()
        self.assertIsNone(self.projet.nb_niveaux)
