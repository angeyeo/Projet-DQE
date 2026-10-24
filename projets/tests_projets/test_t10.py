import json
from unittest.mock import patch
from django.test import SimpleTestCase
from projets.models import Projet
from projets.services.assistant_ia.parser import structurer_description_projet
from projets.services.assistant_ia.schemas import valider_donnees_extraites
from projets.services.parametres_projet import parametres_structure, ParametresIncomplets


class StructurationAxesTests(SimpleTestCase):
    def test_reponse_mockee_conserve_les_axes_independants(self):
        for donnees in ({'portee_x_m': 4}, {'portee_x_m': 4, 'portee_y_m': 6}, {}):
            with self.subTest(donnees=donnees), patch(
                'projets.services.assistant_ia.parser.get_ai_client'
            ) as client:
                client.return_value.appeler_llm.return_value = json.dumps(donnees)
                res = structurer_description_projet('Description fictive')['donnees']
                self.assertEqual(res['portee_x_m'], donnees.get('portee_x_m'))
                self.assertEqual(res['portee_y_m'], donnees.get('portee_y_m'))

    def test_portee_generique_ne_devient_pas_un_axe(self):
        res = valider_donnees_extraites({'portee_m': 4})
        self.assertIsNone(res['portee_x_m'])
        self.assertIsNone(res['portee_y_m'])

    def test_axe_manquant_signale_meme_si_le_llm_l_omet(self):
        res = valider_donnees_extraites({'portee_x_m': 4, 'donnees_manquantes': []})
        self.assertIn('portee_y_m', res['donnees_manquantes'])

    def test_axes_invalides_refuses(self):
        for axe in ('portee_x_m', 'portee_y_m'):
            for valeur in (0, -1, False, float('nan')):
                with self.subTest(axe=axe, valeur=valeur), self.assertRaises(ValueError):
                    valider_donnees_extraites({axe: valeur})

    def test_ly_absente_empeche_le_calcul(self):
        projet = Projet(portee_x=4, portee_y=None)
        with self.assertRaises(ParametresIncomplets) as erreur:
            parametres_structure(projet, avec_grille=True)
        self.assertTrue(any(c['champ'] == 'portee_y' for c in erreur.exception.manquants))


from rest_framework.test import APITestCase
from projets.tests_projets.utils import creer_cabinet, creer_membre
from projets.services.assistant_ia.provenance import signer_proposition


class ProvenanceTests(APITestCase):
    def setUp(self):
        self.cabinet = creer_cabinet()
        self.user = creer_membre(self.cabinet)
        self.client.force_authenticate(self.user)
        self.projet = Projet.objects.create(nom='Projet test', entreprise=self.cabinet, portee_x=3)
        self.url = f'/api/projets/{self.projet.pk}/'
        self.jeton = signer_proposition({'source': 'GEMINI', 'donnees': {'portee_x_m': 4}}, self.user)

    def accepter(self):
        r = self.client.patch(self.url, {'portee_x': 4, 'acceptations_ia': {'portee_x': self.jeton}}, format='json')
        self.assertEqual(r.status_code, 200, r.data)
        return r.data['provenance_parametres']

    def test_acceptation_rechargement_sans_changement_et_patch(self):
        p = self.accepter()
        self.assertEqual(p['portee_x']['origine'], 'ia_acceptee')
        self.assertEqual(p['portee_x']['source'], 'GEMINI')
        self.assertEqual(p['portee_x']['accepte_par'], self.user.pk)
        self.assertTrue(p['portee_x']['accepte_le'])
        self.assertEqual(self.client.get(self.url).data['provenance_parametres'], p)
        self.assertEqual(self.client.patch(self.url, {'portee_x': 4}, format='json').data['provenance_parametres'], p)
        self.assertEqual(self.accepter(), p)
        self.assertEqual(self.client.patch(self.url, {'nom': 'Renommé'}, format='json').data['provenance_parametres'], p)
        r = self.client.patch(self.url, {'portee_y': 7}, format='json')
        self.assertEqual(r.data['provenance_parametres']['portee_x'], p['portee_x'])
        self.assertEqual(r.data['provenance_parametres']['portee_y']['origine'], 'manuelle')

    def test_modification_apres_acceptation(self):
        p = self.accepter()['portee_x']
        r = self.client.patch(self.url, {'portee_x': 5}, format='json')
        provenance = r.data['provenance_parametres']['portee_x']
        self.assertEqual(provenance['origine'], 'modifiee_apres_ia')
        self.assertEqual(provenance['valeur_proposee'], 4)
        self.assertEqual(provenance['accepte_le'], p['accepte_le'])
        self.assertEqual(provenance['modifie_par'], self.user.pk)
        self.assertTrue(provenance['modifie_le'])
        self.assertEqual(self.client.get(self.url).data['provenance_parametres']['portee_x'], provenance)

    def test_modification_avant_premiere_sauvegarde(self):
        r = self.client.patch(self.url, {'portee_x': 5, 'acceptations_ia': {'portee_x': self.jeton}}, format='json')
        self.assertEqual(r.data['provenance_parametres']['portee_x']['origine'], 'modifiee_apres_ia')
        self.assertEqual(r.data['provenance_parametres']['portee_x']['valeur_proposee'], 4)

    def test_historique_ne_recoit_pas_de_provenance_inventee(self):
        self.assertEqual(self.client.get(self.url).data['provenance_parametres'], {})
        r = self.client.patch(self.url, {'portee_x': 3}, format='json')
        self.assertEqual(r.data['provenance_parametres'], {})

    def test_falsification_et_incoherence_refusees(self):
        for payload in (
            {'provenance_parametres': {'portee_x': {'source': 'GEMINI'}}},
            {'portee_x': 4, 'acceptations_ia': {'portee_x': self.jeton + 'faux'}},
            {'portee_y': 4, 'acceptations_ia': {'portee_y': self.jeton}},
            {'acceptations_ia': {'portee_x': self.jeton}},
        ):
            with self.subTest(payload=list(payload)):
                self.assertEqual(self.client.patch(self.url, payload, format='json').status_code, 400)
        self.projet.refresh_from_db()
        self.assertEqual(self.projet.portee_x, 3)
        self.assertEqual(self.projet.provenance_parametres, {})

    def test_autre_utilisateur_et_autre_cabinet(self):
        autre = creer_membre(self.cabinet, username='autre')
        self.client.force_authenticate(autre)
        self.assertEqual(self.client.patch(self.url, {'portee_x': 4, 'acceptations_ia': {'portee_x': self.jeton}}, format='json').status_code, 400)
        externe = creer_membre(creer_cabinet('Externe'), username='externe')
        self.client.force_authenticate(externe)
        self.assertEqual(self.client.patch(self.url, {'portee_x': 4}, format='json').status_code, 404)

    def test_creation_et_source_mock(self):
        jeton = signer_proposition({'source': 'MOCK', 'donnees': {'portee_x_m': 4}}, self.user)
        r = self.client.post('/api/projets/', {'nom': 'Nouveau', 'portee_x': 4, 'acceptations_ia': {'portee_x': jeton}}, format='json')
        self.assertEqual(r.status_code, 201, r.data)
        self.assertEqual(r.data['provenance_parametres']['portee_x']['source'], 'MOCK')
        self.assertIsNone(r.data['portee_y'])

    @patch('projets.views.structurer_description_projet')
    def test_endpoint_delivre_une_preuve_utilisable(self, service):
        import os
        service.return_value = {'source': 'GEMINI', 'donnees': {'portee_x_m': 4}}
        with patch.dict(os.environ, {'LLM_PROVIDER': 'mock'}):
            r = self.client.post('/api/assistant/structurer-projet/', {'description': 'Lx 4 m'}, format='json')
        self.assertEqual(r.status_code, 200, r.data)
        self.jeton = r.data['preuve_proposition']
        self.accepter()
