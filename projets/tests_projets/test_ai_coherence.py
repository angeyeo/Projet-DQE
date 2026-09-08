"""
Tests du module de contrôle de cohérence déterministe V1.

Couvre :
  - Fraîcheur des résultats (VALIDE, MODIFIE, PROPOSE, sans résultat)
  - Règle 1 : PRESSION_SOL_DEPASSEE (semelle / semelle_filante)
  - Règle 2 : FRETTAGE_ACIER_DEPASSE (poteau)
  - Règle 3 : HYPOTHESE_SOL_NON_CONFIRMEE (semelle / semelle_filante)
  - Règle 4 : MINIMUM_NON_FRAGILITE_APPLIQUE (poutre / longrine)
  - Validation défensive des types (bool strict, numériques strict)
  - Invariance DB (aucune écriture)
  - Isolation moteur (aucune fonction moteur appelée)
"""

from django.test import TestCase
from projets.models import Projet, ElementStructurel
from projets.services.assistant_ia.coherence import analyser_element_coherence


class _BaseCoherenceTest(TestCase):
    """Classe de base fournissant un projet et des helpers de création."""

    @classmethod
    def setUpTestData(cls):
        cls.projet = Projet.objects.create(
            nom="Projet cohérence test",
        )

    def _creer_element(self, type_element, statut="valide",
                       resultat_valide=None, resultat_calcul=None, **kwargs):
        """Crée un élément structurel sans appel au moteur."""
        return ElementStructurel.objects.create(
            projet=self.projet,
            identifiant=f"TEST_{type_element.upper()[:3]}",
            type_element=type_element,
            statut=statut,
            resultat_valide=resultat_valide,
            resultat_calcul=resultat_calcul,
            **kwargs,
        )


# ============================================================
# FRAÎCHEUR
# ============================================================

class TestFraicheurResultat(_BaseCoherenceTest):
    """Tests 1–4 : sélection du résultat selon le statut."""

    def test_01_valide_avec_resultat_valide(self):
        """VALIDE + resultat_valide → analyse autorisée."""
        el = self._creer_element(
            "semelle",
            statut="valide",
            resultat_valide={"condition_respectee": True, "hypothese_sol": False},
        )
        result = analyser_element_coherence(el)
        self.assertEqual(result["source_resultat"], "resultat_valide")
        self.assertNotIn(result["statut_analyse"], [
            "CALCUL_A_REFAIRE", "CALCUL_A_VALIDER", "CALCUL_NON_DISPONIBLE"
        ])

    def test_02_modifie(self):
        """MODIFIE → CALCUL_A_REFAIRE."""
        el = self._creer_element(
            "poteau",
            statut="modifie",
            resultat_valide={"frettage_necessaire": True},
            resultat_calcul={"frettage_necessaire": True},
        )
        result = analyser_element_coherence(el)
        self.assertEqual(result["statut_analyse"], "CALCUL_A_REFAIRE")
        self.assertEqual(result["nombre_signaux"], 0)
        self.assertEqual(result["signaux"], [])

    def test_03_propose_avec_resultat_calcul(self):
        """PROPOSE + resultat_calcul → CALCUL_A_VALIDER."""
        el = self._creer_element(
            "poutre",
            statut="propose",
            resultat_calcul={"non_fragilite_respectee": False},
        )
        result = analyser_element_coherence(el)
        self.assertEqual(result["statut_analyse"], "CALCUL_A_VALIDER")
        self.assertEqual(result["nombre_signaux"], 0)

    def test_04_propose_sans_resultat(self):
        """PROPOSE sans résultat → CALCUL_NON_DISPONIBLE."""
        el = self._creer_element(
            "poutre",
            statut="propose",
        )
        result = analyser_element_coherence(el)
        self.assertEqual(result["statut_analyse"], "CALCUL_NON_DISPONIBLE")
        self.assertEqual(result["nombre_signaux"], 0)


# ============================================================
# SEMELLES — PRESSION SOL
# ============================================================

class TestPressionSolDepassee(_BaseCoherenceTest):
    """Tests 5–10 : règle PRESSION_SOL_DEPASSEE."""

    def test_05_condition_non_respectee(self):
        """condition_respectee=False → PRESSION_SOL_DEPASSEE / CRITIQUE."""
        el = self._creer_element(
            "semelle_filante",
            resultat_valide={
                "condition_respectee": False,
                "pression_reelle_mpa": 0.25,
                "hypothese_sol": False,
            },
        )
        result = analyser_element_coherence(el)
        self.assertEqual(result["statut_analyse"], "CRITIQUE")
        codes = [s["code"] for s in result["signaux"]]
        self.assertIn("PRESSION_SOL_DEPASSEE", codes)

    def test_06_condition_respectee(self):
        """condition_respectee=True → pas de PRESSION_SOL_DEPASSEE."""
        el = self._creer_element(
            "semelle_filante",
            resultat_valide={
                "condition_respectee": True,
                "hypothese_sol": False,
            },
        )
        result = analyser_element_coherence(el)
        codes = [s["code"] for s in result["signaux"]]
        self.assertNotIn("PRESSION_SOL_DEPASSEE", codes)

    def test_07_hypothese_sol_true(self):
        """hypothese_sol=True → HYPOTHESE_SOL_NON_CONFIRMEE / ATTENTION."""
        el = self._creer_element(
            "semelle_filante",
            resultat_valide={
                "hypothese_sol": True,
            },
        )
        result = analyser_element_coherence(el)
        codes = [s["code"] for s in result["signaux"]]
        self.assertIn("HYPOTHESE_SOL_NON_CONFIRMEE", codes)
        signal = [s for s in result["signaux"]
                  if s["code"] == "HYPOTHESE_SOL_NON_CONFIRMEE"][0]
        self.assertEqual(signal["categorie"], "ATTENTION")

    def test_08_condition_false_et_hypothese_true(self):
        """condition False + hypothese_sol True sur semelle_filante → statut global CRITIQUE."""
        el = self._creer_element(
            "semelle_filante",
            resultat_valide={
                "condition_respectee": False,
                "hypothese_sol": True,
            },
        )
        result = analyser_element_coherence(el)
        self.assertEqual(result["statut_analyse"], "CRITIQUE")
        codes = [s["code"] for s in result["signaux"]]
        self.assertIn("PRESSION_SOL_DEPASSEE", codes)
        self.assertIn("HYPOTHESE_SOL_NON_CONFIRMEE", codes)

    def test_09_valeurs_mpa_presentes(self):
        """Valeurs MPa présentes → valeurs et unité correctes."""
        el = self._creer_element(
            "semelle_filante",
            resultat_valide={
                "condition_respectee": False,
                "pression_reelle_mpa": 0.25,
            },
        )
        result = analyser_element_coherence(el)
        signal = result["signaux"][0]
        self.assertEqual(signal["valeur_mesuree"], 0.25)
        self.assertIsNone(signal["valeur_limite"])
        self.assertEqual(signal["unite"], "MPa")

    def test_10_valeurs_absentes(self):
        """Valeurs absentes → valeur_mesuree/limite/unite null."""
        el = self._creer_element(
            "semelle_filante",
            resultat_valide={
                "condition_respectee": False,
                "hypothese_sol": False,
            },
        )
        result = analyser_element_coherence(el)
        signal = [s for s in result["signaux"]
                  if s["code"] == "PRESSION_SOL_DEPASSEE"][0]
        self.assertIsNone(signal["valeur_mesuree"])
        self.assertIsNone(signal["valeur_limite"])
        self.assertIsNone(signal["unite"])


# ============================================================
# SEMELLE FILANTE — PRESSION SOL
# ============================================================

class TestPressionSolSmelleFilante(_BaseCoherenceTest):
    """Tests complémentaires pour semelle_filante."""

    def test_semelle_filante_condition_false(self):
        """Semelle filante : condition_respectee=False → CRITIQUE."""
        el = self._creer_element(
            "semelle_filante",
            resultat_valide={
                "condition_respectee": False,
                "pression_reelle_kn_m2": 220.0,
                "hypothese_sol": False,
            },
        )
        result = analyser_element_coherence(el)
        self.assertEqual(result["statut_analyse"], "CRITIQUE")
        signal = [s for s in result["signaux"]
                  if s["code"] == "PRESSION_SOL_DEPASSEE"][0]
        self.assertEqual(signal["valeur_mesuree"], 220.0)
        self.assertEqual(signal["unite"], "kN/m²")

    def test_semelle_filante_hypothese_sol(self):
        """Semelle filante : hypothese_sol=True → ATTENTION."""
        el = self._creer_element(
            "semelle_filante",
            resultat_valide={
                "condition_respectee": True,
                "hypothese_sol": True,
            },
        )
        result = analyser_element_coherence(el)
        codes = [s["code"] for s in result["signaux"]]
        self.assertIn("HYPOTHESE_SOL_NON_CONFIRMEE", codes)


# ============================================================
# POTEAUX — FRETTAGE
# ============================================================

class TestFrettagePoteau(_BaseCoherenceTest):
    """Tests 11–13 : règle FRETTAGE_ACIER_DEPASSE."""

    def test_11_frettage_necessaire_true(self):
        """frettage_necessaire=True → FRETTAGE_ACIER_DEPASSE / CRITIQUE."""
        el = self._creer_element(
            "poteau",
            resultat_valide={
                "frettage_necessaire": True,
                "section_acier_retenue_cm2": 8.5,
                "section_acier_max_cm2": 7.2,
            },
        )
        result = analyser_element_coherence(el)
        self.assertEqual(result["statut_analyse"], "CRITIQUE")
        codes = [s["code"] for s in result["signaux"]]
        self.assertIn("FRETTAGE_ACIER_DEPASSE", codes)

    def test_12_frettage_necessaire_false(self):
        """frettage_necessaire=False → pas de signal."""
        el = self._creer_element(
            "poteau",
            resultat_valide={
                "frettage_necessaire": False,
                "section_acier_retenue_cm2": 5.0,
                "section_acier_max_cm2": 7.2,
            },
        )
        result = analyser_element_coherence(el)
        codes = [s["code"] for s in result["signaux"]]
        self.assertNotIn("FRETTAGE_ACIER_DEPASSE", codes)

    def test_13_valeurs_acier_presentes(self):
        """Valeurs acier disponibles → cm² correct."""
        el = self._creer_element(
            "poteau",
            resultat_valide={
                "frettage_necessaire": True,
                "section_acier_retenue_cm2": 8.5,
                "section_acier_max_cm2": 7.2,
            },
        )
        result = analyser_element_coherence(el)
        signal = [s for s in result["signaux"]
                  if s["code"] == "FRETTAGE_ACIER_DEPASSE"][0]
        self.assertEqual(signal["valeur_mesuree"], 8.5)
        self.assertEqual(signal["valeur_limite"], 7.2)
        self.assertEqual(signal["unite"], "cm²")


# ============================================================
# POUTRES / LONGRINES — NON-FRAGILITÉ
# ============================================================

class TestNonFragilite(_BaseCoherenceTest):
    """Tests 14–15 : règle MINIMUM_NON_FRAGILITE_APPLIQUE."""

    def test_14_non_fragilite_false(self):
        """non_fragilite_respectee=False → INFORMATION."""
        el = self._creer_element(
            "poutre",
            resultat_valide={
                "non_fragilite_respectee": False,
                "section_acier_theorique_cm2": 0.8,
                "section_acier_min_cm2": 1.2,
            },
        )
        result = analyser_element_coherence(el)
        self.assertEqual(result["statut_analyse"], "INFORMATION")
        codes = [s["code"] for s in result["signaux"]]
        self.assertIn("MINIMUM_NON_FRAGILITE_APPLIQUE", codes)

    def test_15_non_fragilite_true(self):
        """non_fragilite_respectee=True → pas de signal."""
        el = self._creer_element(
            "poutre",
            resultat_valide={
                "non_fragilite_respectee": True,
                "section_acier_theorique_cm2": 1.5,
                "section_acier_min_cm2": 1.2,
            },
        )
        result = analyser_element_coherence(el)
        codes = [s["code"] for s in result["signaux"]]
        self.assertNotIn("MINIMUM_NON_FRAGILITE_APPLIQUE", codes)

    def test_longrine_non_fragilite_false(self):
        """Longrine : non_fragilite_respectee=False → INFORMATION."""
        el = self._creer_element(
            "longrine",
            resultat_valide={
                "non_fragilite_respectee": False,
                "section_acier_theorique_cm2": 0.5,
                "section_acier_min_cm2": 1.0,
            },
        )
        result = analyser_element_coherence(el)
        self.assertEqual(result["statut_analyse"], "INFORMATION")
        codes = [s["code"] for s in result["signaux"]]
        self.assertIn("MINIMUM_NON_FRAGILITE_APPLIQUE", codes)


# ============================================================
# SÉCURITÉ — VALIDATION DÉFENSIVE DES TYPES
# ============================================================

class TestValidationDefensive(_BaseCoherenceTest):
    """Tests 16–20 : validation stricte des types."""

    def test_16_booleen_string_false(self):
        """booléen sous forme \"false\" → ne déclenche rien."""
        el = self._creer_element(
            "poteau",
            resultat_valide={
                "frettage_necessaire": "false",
            },
        )
        result = analyser_element_coherence(el)
        codes = [s["code"] for s in result["signaux"]]
        self.assertNotIn("FRETTAGE_ACIER_DEPASSE", codes)

    def test_17_booleen_entier_0_1(self):
        """booléen sous forme 0/1 → ne déclenche rien."""
        el = self._creer_element(
            "poteau",
            resultat_valide={
                "frettage_necessaire": 1,
            },
        )
        result = analyser_element_coherence(el)
        codes = [s["code"] for s in result["signaux"]]
        self.assertNotIn("FRETTAGE_ACIER_DEPASSE", codes)

    def test_17b_booleen_entier_0(self):
        """booléen sous forme 0 → ne déclenche rien."""
        el = self._creer_element(
            "semelle",
            resultat_valide={
                "condition_respectee": 0,
                "hypothese_sol": 0,
            },
        )
        result = analyser_element_coherence(el)
        codes = [s["code"] for s in result["signaux"]]
        self.assertNotIn("PRESSION_SOL_DEPASSEE", codes)
        self.assertNotIn("HYPOTHESE_SOL_NON_CONFIRMEE", codes)

    def test_18_bool_python_natif(self):
        """bool Python → comportement attendu."""
        el = self._creer_element(
            "poteau",
            resultat_valide={
                "frettage_necessaire": True,
            },
        )
        result = analyser_element_coherence(el)
        codes = [s["code"] for s in result["signaux"]]
        self.assertIn("FRETTAGE_ACIER_DEPASSE", codes)

    def test_19_valeurs_numeriques_bool(self):
        """valeurs numériques bool → non utilisées comme nombres."""
        el = self._creer_element(
            "poteau",
            resultat_valide={
                "frettage_necessaire": True,
                "section_acier_retenue_cm2": True,
                "section_acier_max_cm2": False,
            },
        )
        result = analyser_element_coherence(el)
        signal = [s for s in result["signaux"]
                  if s["code"] == "FRETTAGE_ACIER_DEPASSE"][0]
        # True/False ne doivent pas être utilisés comme valeurs numériques
        self.assertIsNone(signal["valeur_mesuree"])
        self.assertIsNone(signal["valeur_limite"])

    def test_20_type_element_inconnu(self):
        """type élément inconnu → AUCUN_SIGNAL sans crash."""
        el = self._creer_element(
            "dalle",
            resultat_valide={"quelque_chose": True},
        )
        result = analyser_element_coherence(el)
        self.assertEqual(result["statut_analyse"], "AUCUN_SIGNAL")
        self.assertEqual(result["signaux"], [])


# ============================================================
# INVARIANCE DB ET ISOLATION MOTEUR
# ============================================================

class TestInvarianceDB(_BaseCoherenceTest):
    """Tests 21–24 : aucune écriture DB, isolation du moteur."""

    def test_21_aucune_ecriture_db(self):
        """Aucune écriture DB pendant l'analyse."""
        el = self._creer_element(
            "semelle",
            statut="valide",
            resultat_valide={
                "condition_respectee": False,
                "hypothese_sol": True,
            },
        )
        # Mémoriser l'état avant l'analyse
        initial_statut = el.statut
        initial_resultat_calcul = el.resultat_calcul
        initial_resultat_valide = el.resultat_valide

        analyser_element_coherence(el)

        # Recharger depuis la DB
        el.refresh_from_db()
        self.assertEqual(el.statut, initial_statut)
        self.assertEqual(el.resultat_calcul, initial_resultat_calcul)
        self.assertEqual(el.resultat_valide, initial_resultat_valide)

        # Vérifier que le nombre total d'éléments n'a pas changé
        self.assertEqual(
            ElementStructurel.objects.filter(projet=self.projet).count(),
            1,  # seul celui qu'on vient de créer
        )

    def test_22_aucune_fonction_moteur(self):
        """Aucune fonction moteur appelée pendant l'analyse."""
        # On vérifie que le module coherence n'importe rien du moteur
        import projets.services.assistant_ia.coherence as mod
        source_code = open(mod.__file__).read()
        self.assertNotIn("moteur_calcul", source_code)
        self.assertNotIn("dimensionner_", source_code)
        self.assertNotIn("calculer_element", source_code)

    def test_23_resultat_calcul_non_utilise_pour_propose(self):
        """resultat_calcul n'est jamais utilisé pour PROPOSE."""
        el = self._creer_element(
            "semelle",
            statut="propose",
            resultat_calcul={
                "condition_respectee": False,
                "hypothese_sol": True,
            },
        )
        result = analyser_element_coherence(el)
        # Ne doit PAS avoir de signaux métier
        self.assertEqual(result["statut_analyse"], "CALCUL_A_VALIDER")
        self.assertEqual(result["nombre_signaux"], 0)
        self.assertEqual(result["signaux"], [])

    def test_24_resultat_valide_non_utilise_pour_modifie(self):
        """resultat_valide n'est jamais utilisé pour MODIFIE."""
        el = self._creer_element(
            "poteau",
            statut="modifie",
            resultat_valide={
                "frettage_necessaire": True,
                "section_acier_retenue_cm2": 8.5,
                "section_acier_max_cm2": 7.2,
            },
        )
        result = analyser_element_coherence(el)
        # Ne doit PAS avoir de signaux métier
        self.assertEqual(result["statut_analyse"], "CALCUL_A_REFAIRE")
        self.assertEqual(result["nombre_signaux"], 0)
        self.assertEqual(result["signaux"], [])


# ============================================================
# STRUCTURE DE RÉPONSE
# ============================================================

class TestStructureReponse(_BaseCoherenceTest):
    """Vérifie la structure stable du dictionnaire retourné."""

    def test_cles_obligatoires(self):
        """Toutes les clés documentées sont présentes."""
        el = self._creer_element(
            "semelle",
            resultat_valide={"condition_respectee": True, "hypothese_sol": False},
        )
        result = analyser_element_coherence(el)
        cles_attendues = {
            "element_id", "identifiant", "type_element",
            "statut_element", "source_resultat", "statut_analyse",
            "nombre_signaux", "signaux", "explication_ia",
            "source_explication", "message_local",
            "validation_humaine_requise",
        }
        self.assertEqual(set(result.keys()), cles_attendues)

    def test_explication_ia_toujours_null(self):
        """explication_ia est toujours null en Partie 1."""
        el = self._creer_element(
            "poteau",
            resultat_valide={"frettage_necessaire": True},
        )
        result = analyser_element_coherence(el)
        self.assertIsNone(result["explication_ia"])
        self.assertEqual(result["source_explication"], "LOCAL")

    def test_structure_signal(self):
        """Chaque signal contient exactement les clés documentées."""
        el = self._creer_element(
            "semelle",
            resultat_valide={
                "condition_respectee": False,
                "hypothese_sol": True,
            },
        )
        result = analyser_element_coherence(el)
        cles_signal = {
            "code", "categorie", "champ_analyse",
            "valeur_mesuree", "valeur_limite", "unite",
            "source_regle", "origine_regle", "message_local",
        }
        for signal in result["signaux"]:
            self.assertEqual(set(signal.keys()), cles_signal)

    def test_nombre_signaux_coherent(self):
        """nombre_signaux correspond à len(signaux)."""
        el = self._creer_element(
            "semelle",
            resultat_valide={
                "condition_respectee": False,
                "hypothese_sol": True,
            },
        )
        result = analyser_element_coherence(el)
        self.assertEqual(result["nombre_signaux"], len(result["signaux"]))


# ============================================================
# PRIORITÉ DES CATÉGORIES
# ============================================================

class TestPrioriteCategories(_BaseCoherenceTest):
    """Vérifie la hiérarchie CRITIQUE > ATTENTION > INFORMATION."""

    def test_critique_prime_sur_attention(self):
        """CRITIQUE + ATTENTION → statut CRITIQUE."""
        el = self._creer_element(
            "semelle_filante",
            resultat_valide={
                "condition_respectee": False,
                "hypothese_sol": True,
            },
        )
        result = analyser_element_coherence(el)
        self.assertEqual(result["statut_analyse"], "CRITIQUE")

    def test_attention_seule(self):
        """ATTENTION seule → statut ATTENTION."""
        el = self._creer_element(
            "semelle",
            resultat_valide={
                "condition_respectee": True,
                "hypothese_sol": True,
            },
        )
        result = analyser_element_coherence(el)
        self.assertEqual(result["statut_analyse"], "ATTENTION")

    def test_information_seule(self):
        """INFORMATION seule → statut INFORMATION."""
        el = self._creer_element(
            "poutre",
            resultat_valide={
                "non_fragilite_respectee": False,
                "section_acier_theorique_cm2": 0.8,
                "section_acier_min_cm2": 1.2,
            },
        )
        result = analyser_element_coherence(el)
        self.assertEqual(result["statut_analyse"], "INFORMATION")

    def test_aucun_signal_dalle(self):
        """Dalle VALIDE → AUCUN_SIGNAL."""
        el = self._creer_element(
            "dalle",
            resultat_valide={"hauteur_cm": 20},
        )
        result = analyser_element_coherence(el)
        self.assertEqual(result["statut_analyse"], "AUCUN_SIGNAL")


# ============================================================
# CAS LIMITES
# ============================================================

class TestCasLimites(_BaseCoherenceTest):
    """Cas supplémentaires pour la robustesse."""

    def test_valide_sans_resultat_valide(self):
        """VALIDE mais resultat_valide=None → CALCUL_NON_DISPONIBLE."""
        el = self._creer_element(
            "poteau",
            statut="valide",
            resultat_valide=None,
        )
        result = analyser_element_coherence(el)
        self.assertEqual(result["statut_analyse"], "CALCUL_NON_DISPONIBLE")

    def test_resultat_valide_vide(self):
        """VALIDE + resultat_valide={} → CALCUL_NON_DISPONIBLE."""
        el = self._creer_element(
            "poteau",
            statut="valide",
            resultat_valide={},
        )
        result = analyser_element_coherence(el)
        self.assertEqual(result["statut_analyse"], "CALCUL_NON_DISPONIBLE")

    def test_chainage_aucun_signal(self):
        """Chainage VALIDE → AUCUN_SIGNAL (pas de contrôle V1)."""
        el = self._creer_element(
            "chainage",
            resultat_valide={"longueur_m": 5.0},
        )
        result = analyser_element_coherence(el)
        self.assertEqual(result["statut_analyse"], "AUCUN_SIGNAL")
        self.assertEqual(result["signaux"], [])

    def test_condition_respectee_absente(self):
        """condition_respectee absent du résultat → pas de PRESSION_SOL_DEPASSEE."""
        el = self._creer_element(
            "semelle",
            resultat_valide={
                "cote_cm": 80,
                "hypothese_sol": False,
            },
        )
        result = analyser_element_coherence(el)
        codes = [s["code"] for s in result["signaux"]]
        self.assertNotIn("PRESSION_SOL_DEPASSEE", codes)

    def test_unite_null_quand_valeurs_absentes_frettage(self):
        """Frettage sans valeurs numériques → unite=None."""
        el = self._creer_element(
            "poteau",
            resultat_valide={
                "frettage_necessaire": True,
            },
        )
        result = analyser_element_coherence(el)
        signal = [s for s in result["signaux"]
                  if s["code"] == "FRETTAGE_ACIER_DEPASSE"][0]
        self.assertIsNone(signal["valeur_mesuree"])
        self.assertIsNone(signal["valeur_limite"])
        self.assertIsNone(signal["unite"])


# ============================================================
# TEST D'INTÉGRATION — WORKFLOW RÉEL DU MOTEUR (calculer_element)
# ============================================================

class TestIntegrationCalculerElementReal(_BaseCoherenceTest):
    """Prouve de façon empirique la différence de dictionnaire retourné entre SEMELLE et SEMELLE_FILANTE via calculer_element()."""

    def test_workflow_reel_semelle_isolee_sans_condition_respectee(self):
        """calculer_element() pour une SEMELLE isolée ne produit PAS condition_respectee."""
        from projets.services.calculations import calculer_element

        el = self._creer_element(
            "semelle",
            statut="propose",
            resultat_calcul=None,
        )
        el.charge_calculee = 150.0  # kN
        el.taux_travail_sol = None
        el.save()

        res_calcul = calculer_element(el)

        # Vérification empirique : condition_respectee n'existe pas dans le dictionnaire réel
        self.assertNotIn("condition_respectee", res_calcul)
        self.assertIn("hypothese_sol", res_calcul)
        self.assertTrue(res_calcul["hypothese_sol"])

        # Analyse de cohérence sur cet élément validé avec le vrai résultat moteur
        el.statut = "valide"
        el.resultat_valide = res_calcul
        el.save()

        res_ai = analyser_element_coherence(el)
        codes = [s["code"] for s in res_ai["signaux"]]
        self.assertNotIn("PRESSION_SOL_DEPASSEE", codes)
        self.assertIn("HYPOTHESE_SOL_NON_CONFIRMEE", codes)

    def test_workflow_reel_semelle_filante_avec_condition_respectee(self):
        """calculer_element() pour une SEMELLE_FILANTE produit BIEN condition_respectee."""
        from projets.services.calculations import calculer_element

        el = self._creer_element(
            "semelle_filante",
            statut="propose",
            resultat_calcul=None,
        )
        el.charge_lineaire = 100.0  # kN/m
        el.taux_travail_sol = 150.0  # kN/m² (0.15 MPa)
        el.save()

        res_calcul = calculer_element(el)

        # Vérification empirique : condition_respectee existe dans le dictionnaire réel
        self.assertIn("condition_respectee", res_calcul)
        self.assertIn("pression_reelle_kn_m2", res_calcul)
