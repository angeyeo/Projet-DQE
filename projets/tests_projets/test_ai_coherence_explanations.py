import os
from copy import deepcopy
from unittest.mock import MagicMock, patch
from django.test import TestCase

from projets.models import Projet, ElementStructurel
from projets.services.assistant_ia.coherence import (
    analyser_element_coherence,
    analyser_projet_coherence,
)
from projets.services.assistant_ia.coherence_explanations import (
    expliquer_analyse_coherence,
)
from projets.services.assistant_ia.client import (
    MockAIClient,
    GeminiAIClient,
    LLMServiceError,
)


class TestCoherenceExplanations(TestCase):
    """Tests pour l'explication IA et les garde-fous de cohérence."""

    @classmethod
    def setUpTestData(cls):
        cls.projet = Projet.objects.create(nom="Projet Test Explication IA")

    def _creer_element(self, type_element, statut="valide", **kwargs):
        return ElementStructurel.objects.create(
            projet=self.projet,
            identifiant=kwargs.pop("identifiant", f"EL_{type_element}"),
            type_element=type_element,
            statut=statut,
            **kwargs,
        )

    # 1. Analyse CRITIQUE + Mock valide → MOCK
    def test_01_critique_mock_valide(self):
        el = self._creer_element(
            "semelle_filante",
            resultat_valide={"condition_respectee": False},
        )
        analyse = analyser_element_coherence(el)
        self.assertEqual(analyse["statut_analyse"], "CRITIQUE")

        res = expliquer_analyse_coherence(analyse, client=MockAIClient())
        self.assertEqual(res["source_explication"], "MOCK")
        self.assertIsNotNone(res["explication_ia"])
        self.assertTrue(res["validation_humaine_requise"])
        self.assertIn("vérification humaine", res["message_validation"])
        self.assertEqual(res["statut_analyse"], "CRITIQUE")
        self.assertEqual(res["signaux"], analyse["signaux"])

    # 2. Analyse ATTENTION + Mock valide → MOCK
    def test_02_attention_mock_valide(self):
        el = self._creer_element(
            "semelle",
            resultat_valide={"hypothese_sol": True},
        )
        analyse = analyser_element_coherence(el)
        self.assertEqual(analyse["statut_analyse"], "ATTENTION")

        res = expliquer_analyse_coherence(analyse, client=MockAIClient())
        self.assertEqual(res["source_explication"], "MOCK")
        self.assertIsNotNone(res["explication_ia"])
        self.assertEqual(res["statut_analyse"], "ATTENTION")

    # 3. Analyse INFORMATION + Mock valide → MOCK
    def test_03_information_mock_valide(self):
        el = self._creer_element(
            "poutre",
            resultat_valide={"non_fragilite_respectee": False},
        )
        analyse = analyser_element_coherence(el)
        self.assertEqual(analyse["statut_analyse"], "INFORMATION")

        res = expliquer_analyse_coherence(analyse, client=MockAIClient())
        self.assertEqual(res["source_explication"], "MOCK")
        self.assertIsNotNone(res["explication_ia"])

    # 4. AUCUN_SIGNAL → aucun appel LLM → LOCAL
    def test_04_aucun_signal_pas_d_appel_llm(self):
        el = self._creer_element(
            "dalle",
            resultat_valide={"longueur_m": 4.0},
        )
        analyse = analyser_element_coherence(el)
        self.assertEqual(analyse["statut_analyse"], "AUCUN_SIGNAL")

        mock_client = MagicMock()
        res = expliquer_analyse_coherence(analyse, client=mock_client)

        mock_client.appeler_llm.assert_not_called()
        self.assertEqual(res["source_explication"], "LOCAL")
        self.assertIsNone(res["explication_ia"])
        self.assertTrue(res["validation_humaine_requise"])

    # 5. CALCUL_A_VALIDER → aucun appel LLM → LOCAL
    def test_05_calcul_a_valider_pas_d_appel_llm(self):
        el = self._creer_element(
            "poteau",
            statut="propose",
            resultat_calcul={"section_acier_retenue_cm2": 5.0},
        )
        analyse = analyser_element_coherence(el)
        self.assertEqual(analyse["statut_analyse"], "CALCUL_A_VALIDER")

        mock_client = MagicMock()
        res = expliquer_analyse_coherence(analyse, client=mock_client)

        mock_client.appeler_llm.assert_not_called()
        self.assertEqual(res["source_explication"], "LOCAL")
        self.assertIsNone(res["explication_ia"])

    # 6. CALCUL_A_REFAIRE → aucun appel LLM → LOCAL
    def test_06_calcul_a_refaire_pas_d_appel_llm(self):
        el = self._creer_element(
            "poteau",
            statut="modifie",
            resultat_calcul={"section_acier_retenue_cm2": 5.0},
            resultat_valide={"section_acier_retenue_cm2": 4.0},
        )
        analyse = analyser_element_coherence(el)
        self.assertEqual(analyse["statut_analyse"], "CALCUL_A_REFAIRE")

        mock_client = MagicMock()
        res = expliquer_analyse_coherence(analyse, client=mock_client)

        mock_client.appeler_llm.assert_not_called()
        self.assertEqual(res["source_explication"], "LOCAL")
        self.assertIsNone(res["explication_ia"])

    # 7. CALCUL_NON_DISPONIBLE → aucun appel LLM → LOCAL
    def test_07_calcul_non_disponible_pas_d_appel_llm(self):
        el = self._creer_element(
            "poteau",
            statut="propose",
            resultat_calcul=None,
        )
        analyse = analyser_element_coherence(el)
        self.assertEqual(analyse["statut_analyse"], "CALCUL_NON_DISPONIBLE")

        mock_client = MagicMock()
        res = expliquer_analyse_coherence(analyse, client=mock_client)

        mock_client.appeler_llm.assert_not_called()
        self.assertEqual(res["source_explication"], "LOCAL")
        self.assertIsNone(res["explication_ia"])

    # 8. Timeout LLM → LOCAL avec signaux conservés
    def test_08_timeout_llm_fallback_local(self):
        el = self._creer_element(
            "semelle_filante",
            resultat_valide={"condition_respectee": False},
        )
        analyse = analyser_element_coherence(el)

        mock_client = MagicMock()
        mock_client.appeler_llm.side_effect = TimeoutError("Délai d'attente dépassé")

        res = expliquer_analyse_coherence(analyse, client=mock_client)

        self.assertEqual(res["source_explication"], "LOCAL")
        self.assertIsNone(res["explication_ia"])
        self.assertEqual(res["statut_analyse"], "CRITIQUE")
        self.assertEqual(res["signaux"], analyse["signaux"])

    # 9. LLMServiceError → LOCAL
    def test_09_llm_service_error_fallback_local(self):
        el = self._creer_element(
            "semelle_filante",
            resultat_valide={"condition_respectee": False},
        )
        analyse = analyser_element_coherence(el)

        mock_client = MagicMock()
        mock_client.appeler_llm.side_effect = LLMServiceError("Erreur quota")

        res = expliquer_analyse_coherence(analyse, client=mock_client)

        self.assertEqual(res["source_explication"], "LOCAL")
        self.assertIsNone(res["explication_ia"])

    # 10. Terme interdit → LOCAL
    def test_10_terme_interdit_rejet_local(self):
        el = self._creer_element(
            "semelle_filante",
            resultat_valide={"condition_respectee": False},
        )
        analyse = analyser_element_coherence(el)

        mock_client = MagicMock()
        mock_client.appeler_llm.return_value = (
            "L'ouvrage est entièrement conforme et validé selon les normes."
        )

        res = expliquer_analyse_coherence(analyse, client=mock_client)

        self.assertEqual(res["source_explication"], "LOCAL")
        self.assertIsNone(res["explication_ia"])
        self.assertEqual(res["statut_analyse"], "CRITIQUE")

    # 11. Nombre inventé → LOCAL
    def test_11_nombre_invente_rejet_local(self):
        el = self._creer_element(
            "semelle_filante",
            resultat_valide={"condition_respectee": False},
        )
        analyse = analyser_element_coherence(el)

        mock_client = MagicMock()
        # "999" est un nombre inventé non présent dans l'analyse
        mock_client.appeler_llm.return_value = (
            "La contrainte dépasse 999 bar sur cet élément."
        )

        res = expliquer_analyse_coherence(analyse, client=mock_client)

        self.assertEqual(res["source_explication"], "LOCAL")
        self.assertIsNone(res["explication_ia"])

    # 12. Nombre autorisé → réponse acceptée
    def test_12_nombre_autorise_accepte(self):
        el = self._creer_element(
            "semelle_filante",
            resultat_valide={
                "condition_respectee": False,
                "pression_reelle_mpa": 0.25,
            },
        )
        analyse = analyser_element_coherence(el)

        mock_client = MagicMock()
        # 0.25 est présent dans les signaux
        mock_client.appeler_llm.return_value = (
            "La pression mesurée de 0.25 MPa dépasse la capacité."
        )

        res = expliquer_analyse_coherence(analyse, client=mock_client)

        self.assertNotEqual(res["source_explication"], "LOCAL")
        self.assertEqual(
            res["explication_ia"],
            "La pression mesurée de 0.25 MPa dépasse la capacité.",
        )

    # 13. Identifiant contenant chiffre (ex : S1) → pas de faux rejet
    def test_13_identifiant_avec_chiffre_non_rejete(self):
        el = self._creer_element(
            "semelle",
            identifiant="S1",
            resultat_valide={"hypothese_sol": True},
        )
        analyse = analyser_element_coherence(el)

        mock_client = MagicMock()
        mock_client.appeler_llm.return_value = (
            "L'élément S1 nécessite de vérifier la contrainte de sol."
        )

        res = expliquer_analyse_coherence(analyse, client=mock_client)

        self.assertNotEqual(res["source_explication"], "LOCAL")
        self.assertEqual(
            res["explication_ia"],
            "L'élément S1 nécessite de vérifier la contrainte de sol.",
        )

    # 14. validation_humaine_requise toujours True
    def test_14_validation_humaine_requise_toujours_true(self):
        el = self._creer_element(
            "semelle",
            resultat_valide={"hypothese_sol": True},
        )
        analyse = analyser_element_coherence(el)

        res_local = me_res = expliquer_analyse_coherence(analyse, client=MagicMock(side_effect=Exception))
        self.assertTrue(res_local["validation_humaine_requise"])

        res_mock = expliquer_analyse_coherence(analyse, client=MockAIClient())
        self.assertTrue(res_mock["validation_humaine_requise"])

    # 15. Phrase de vérification humaine présente
    def test_15_phrase_verification_humaine_presente(self):
        el = self._creer_element(
            "semelle",
            resultat_valide={"hypothese_sol": True},
        )
        analyse = analyser_element_coherence(el)

        res = expliquer_analyse_coherence(analyse, client=MockAIClient())
        self.assertEqual(
            res["message_validation"],
            "Cette analyse nécessite une vérification humaine par l’ingénieur structure.",
        )

    # 16. Gemini/Mock ne peut modifier aucun signal Python
    def test_16_signaux_python_inviolables(self):
        el = self._creer_element(
            "semelle_filante",
            resultat_valide={"condition_respectee": False},
        )
        analyse = analyser_element_coherence(el)
        signaux_originaux = list(analyse["signaux"])

        mock_client = MagicMock()
        mock_client.appeler_llm.return_value = "Explication neutre sans danger."

        res = expliquer_analyse_coherence(analyse, client=mock_client)
        self.assertEqual(res["signaux"], signaux_originaux)
        self.assertEqual(res["statut_analyse"], "CRITIQUE")

    def test_immutabilite_analyse_entree(self):
        el = self._creer_element(
            "semelle_filante",
            resultat_valide={"condition_respectee": False},
        )
        analyse = analyser_element_coherence(el)
        copie_avant = deepcopy(analyse)

        # 1. Chemin MOCK valide
        res_mock = expliquer_analyse_coherence(analyse, client=MockAIClient())
        self.assertEqual(analyse, copie_avant)
        self.assertNotEqual(res_mock, analyse)

        # 2. Chemin Fallback LOCAL
        failing_mock = MagicMock()
        failing_mock.appeler_llm.side_effect = RuntimeError("Service crash")
        res_local = expliquer_analyse_coherence(analyse, client=failing_mock)
        self.assertEqual(analyse, copie_avant)
        self.assertNotEqual(res_local, analyse)

    def test_gemini_sans_cle_api_fallback_local(self):
        el = self._creer_element(
            "semelle_filante",
            resultat_valide={"condition_respectee": False},
        )
        analyse = analyser_element_coherence(el)

        with patch.dict(os.environ, {"LLM_PROVIDER": "gemini", "LLM_API_KEY": ""}):
            res = expliquer_analyse_coherence(analyse)
            self.assertEqual(res["source_explication"], "LOCAL")
            self.assertIsNone(res["explication_ia"])
            self.assertEqual(res["statut_analyse"], "CRITIQUE")


class TestSourceMockGemini(TestCase):
    """Vérifie la distinction MOCK / GEMINI."""

    @classmethod
    def setUpTestData(cls):
        cls.projet = Projet.objects.create(nom="Projet Source Test")

    def test_source_mock(self):
        el = ElementStructurel.objects.create(
            projet=self.projet,
            identifiant="SF1",
            type_element="semelle_filante",
            statut="valide",
            resultat_valide={"condition_respectee": False},
        )
        analyse = analyser_element_coherence(el)
        res = expliquer_analyse_coherence(analyse, client=MockAIClient())
        self.assertEqual(res["source_explication"], "MOCK")

    def test_source_gemini(self):
        el = ElementStructurel.objects.create(
            projet=self.projet,
            identifiant="SF1",
            type_element="semelle_filante",
            statut="valide",
            resultat_valide={"condition_respectee": False},
        )
        analyse = analyser_element_coherence(el)

        gemini_mock_client = MagicMock(spec=GeminiAIClient)
        gemini_mock_client.appeler_llm.return_value = (
            "Pression sol trop élevée sur l'élément SF1."
        )

        res = expliquer_analyse_coherence(analyse, client=gemini_mock_client)
        self.assertEqual(res["source_explication"], "GEMINI")


class TestAgregationProjet(TestCase):
    """Tests pour l'agrégation de cohérence au niveau projet (analyser_projet_coherence)."""

    def test_agregation_projet_multi_elements(self):
        projet = Projet.objects.create(nom="Projet Agrégation Complexe")

        # 1. CRITIQUE (semelle_filante, condition_respectee=False)
        ElementStructurel.objects.create(
            projet=projet,
            identifiant="SF_CRIT",
            type_element="semelle_filante",
            statut="valide",
            resultat_valide={"condition_respectee": False},
        )

        # 2. ATTENTION (semelle, hypothese_sol=True)
        ElementStructurel.objects.create(
            projet=projet,
            identifiant="S_ATT",
            type_element="semelle",
            statut="valide",
            resultat_valide={"hypothese_sol": True},
        )

        # 3. INFORMATION (poutre, non_fragilite_respectee=False)
        ElementStructurel.objects.create(
            projet=projet,
            identifiant="P_INF",
            type_element="poutre",
            statut="valide",
            resultat_valide={"non_fragilite_respectee": False},
        )

        # 4. AUCUN_SIGNAL (dalle, VALIDE)
        ElementStructurel.objects.create(
            projet=projet,
            identifiant="D_OK",
            type_element="dalle",
            statut="valide",
            resultat_valide={"longueur_m": 5.0},
        )

        # 5. CALCUL_A_VALIDER (poteau, PROPOSE avec resultat_calcul)
        ElementStructurel.objects.create(
            projet=projet,
            identifiant="P_PROP",
            type_element="poteau",
            statut="propose",
            resultat_calcul={"section_acier_retenue_cm2": 4.0},
        )

        # 6. CALCUL_A_REFAIRE (poteau, MODIFIE)
        ElementStructurel.objects.create(
            projet=projet,
            identifiant="P_MODIF",
            type_element="poteau",
            statut="modifie",
            resultat_calcul={"section_acier_retenue_cm2": 5.0},
            resultat_valide={"section_acier_retenue_cm2": 4.0},
        )

        # 7. CALCUL_NON_DISPONIBLE (poteau, PROPOSE sans resultat)
        ElementStructurel.objects.create(
            projet=projet,
            identifiant="P_NODATA",
            type_element="poteau",
            statut="propose",
            resultat_calcul=None,
        )

        # Exécution de l'agrégation projet
        res_projet = analyser_projet_coherence(projet)

        self.assertEqual(res_projet["projet_id"], projet.id)
        self.assertEqual(res_projet["nom_projet"], "Projet Agrégation Complexe")

        resume = res_projet["resume"]
        self.assertEqual(resume["total_elements"], 7)
        self.assertEqual(resume["critiques"], 1)
        self.assertEqual(resume["attentions"], 1)
        self.assertEqual(resume["informations"], 1)
        self.assertEqual(resume["aucun_signal"], 1)
        self.assertEqual(resume["calculs_a_valider"], 1)
        self.assertEqual(resume["calculs_a_refaire"], 1)
        self.assertEqual(resume["calculs_non_disponibles"], 1)

        self.assertEqual(len(res_projet["elements"]), 7)

    def test_agregation_projet_vide(self):
        projet = Projet.objects.create(nom="Projet Vide")
        res_projet = analyser_projet_coherence(projet)

        self.assertEqual(res_projet["resume"]["total_elements"], 0)
        self.assertEqual(res_projet["resume"]["critiques"], 0)
        self.assertEqual(res_projet["elements"], [])

    def test_agregation_projet_ordre_stable(self):
        projet = Projet.objects.create(nom="Projet Ordre Stable")
        e1 = ElementStructurel.objects.create(
            projet=projet, identifiant="E1", type_element="dalle", statut="valide", resultat_valide={}
        )
        e2 = ElementStructurel.objects.create(
            projet=projet, identifiant="E2", type_element="dalle", statut="valide", resultat_valide={}
        )
        res_projet = analyser_projet_coherence(projet)
        ids_retournes = [el["element_id"] for el in res_projet["elements"]]
        self.assertEqual(ids_retournes, [e1.id, e2.id])

    def test_agregation_projet_invariance_db(self):
        projet = Projet.objects.create(nom="Projet Invariance DB")
        ElementStructurel.objects.create(
            projet=projet, identifiant="E1", type_element="semelle", statut="valide", resultat_valide={"hypothese_sol": True}
        )

        elements_avant = list(ElementStructurel.objects.values())
        analyser_projet_coherence(projet)
        elements_apres = list(ElementStructurel.objects.values())

        self.assertEqual(elements_avant, elements_apres)

    def test_agregation_projet_aucun_llm_appele(self):
        projet = Projet.objects.create(nom="Projet Sans LLM")
        ElementStructurel.objects.create(
            projet=projet, identifiant="E1", type_element="semelle", statut="valide", resultat_valide={"hypothese_sol": True}
        )

        mock_client = MagicMock()
        analyser_projet_coherence(projet)
        mock_client.appeler_llm.assert_not_called()
