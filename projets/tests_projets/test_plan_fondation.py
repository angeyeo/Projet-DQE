"""
Tests d'isolation de projets/services/plan_fondation.py -- feuille de
route "Ma partie -- Backend", Jour 3 (fin de journée).

Comme trame.py, ces fonctions ne touchent pas la base -- testées ici en
isolation complète. On construit à la main des listes de dicts au format
attendu (celui de GET /api/projets/{id}/plan_fondation/, Samuel Jour 2.4)
plutôt que des ElementStructurel réels, pour ne dépendre ni du modèle ni
de la base de données.

Régression clé : les segments dessinés doivent correspondre exactement
à calculer_longueur_chainage() (Jour 2 §2.3) sur la même trame -- "mêmes
segments... mais dessinés plutôt que sommés" (doc Jour 3).
"""

from django.test import SimpleTestCase

from moteur_calcul.formules.trame import calculer_longueur_chainage
from projets.services.plan_fondation import (
    generer_plan_fondation_dxf,
    _calculer_segments_chainage,
)


def _semelle(identifiant, x, y, i=None, j=None, cote_semelle_cm=100.0, cote_poteau_cm=25.0):
    semelle = {
        "identifiant": identifiant,
        "position_x": x,
        "position_y": y,
        "cote_cm": cote_semelle_cm,
        "hauteur_cm": 40.0,
        "poteau_associe": {"identifiant": f"P-{identifiant}", "cote_cm": cote_poteau_cm},
    }
    if i is not None:
        semelle["indice_i"] = i
    if j is not None:
        semelle["indice_j"] = j
    return semelle


def _grille_2x1(avec_indices):
    """Trame 2x1, portées 5,0 x 4,0 m -- même exemple que test_trame.py."""
    portee_x, portee_y = 5.0, 4.0
    semelles = []
    for i in range(3):  # 0, 1, 2 (nb_travees_x=2 -> 3 files de poteaux)
        for j in range(2):  # 0, 1 (nb_travees_y=1 -> 2 files)
            semelles.append(_semelle(
                f"S{i}{j}", i * portee_x, j * portee_y,
                i=i if avec_indices else None, j=j if avec_indices else None,
            ))
    return semelles


class TestSegmentsChainage(SimpleTestCase):
    def test_correspond_a_calculer_longueur_chainage_avec_indices(self):
        semelles = _grille_2x1(avec_indices=True)
        segments = _calculer_segments_chainage(semelles, tolerance_position_m=0.01)
        longueur = sum(
            ((x2 - x1) ** 2 + (y2 - y1) ** 2) ** 0.5 for (x1, y1), (x2, y2) in segments
        )
        attendu = calculer_longueur_chainage(nb_travees_x=2, nb_travees_y=1, portee_x=5.0, portee_y=4.0)
        self.assertAlmostEqual(longueur, attendu, places=2)

    def test_correspond_a_calculer_longueur_chainage_sans_indices(self):
        """Méthode de secours (positions) : doit donner le même total."""
        semelles = _grille_2x1(avec_indices=False)
        segments = _calculer_segments_chainage(semelles, tolerance_position_m=0.01)
        longueur = sum(
            ((x2 - x1) ** 2 + (y2 - y1) ** 2) ** 0.5 for (x1, y1), (x2, y2) in segments
        )
        attendu = calculer_longueur_chainage(nb_travees_x=2, nb_travees_y=1, portee_x=5.0, portee_y=4.0)
        self.assertAlmostEqual(longueur, attendu, places=2)

    def test_pas_de_segment_diagonal(self):
        """Un poteau ne doit être relié qu'à ses voisins directs (i±1 ou j±1), jamais en diagonale."""
        semelles = _grille_2x1(avec_indices=True)
        segments = _calculer_segments_chainage(semelles, tolerance_position_m=0.01)
        for (x1, y1), (x2, y2) in segments:
            self.assertTrue(x1 == x2 or y1 == y2, f"Segment diagonal détecté : ({x1},{y1})-({x2},{y2})")

    def test_trame_1x1_quatre_segments_perimetre(self):
        """1x1 : un seul carré, 4 poteaux, 4 segments de périmètre (pas de diagonale)."""
        semelles = [
            _semelle("S00", 0.0, 0.0, i=0, j=0),
            _semelle("S10", 5.0, 0.0, i=1, j=0),
            _semelle("S01", 0.0, 4.0, i=0, j=1),
            _semelle("S11", 5.0, 4.0, i=1, j=1),
        ]
        segments = _calculer_segments_chainage(semelles, tolerance_position_m=0.01)
        self.assertEqual(len(segments), 4)


class TestGenererPlanFondationDxf(SimpleTestCase):
    def test_retourne_des_bytes_dxf_valides(self):
        semelles = _grille_2x1(avec_indices=True)
        data = generer_plan_fondation_dxf(semelles)
        self.assertIsInstance(data, bytes)
        # Un fichier DXF ASCII commence toujours par ce marqueur d'entête.
        self.assertIn(b"SECTION", data)
        self.assertIn(b"ENTITIES", data)

    def test_longueur_chainage_annotee_dans_le_dxf(self):
        semelles = _grille_2x1(avec_indices=True)
        data = generer_plan_fondation_dxf(semelles)
        # L'annotation textuelle doit contenir la longueur attendue (32.00 ml).
        self.assertIn(b"32.00", data)

    def test_semelle_sans_poteau_leve_une_erreur_explicite(self):
        semelles = _grille_2x1(avec_indices=True)
        del semelles[0]["poteau_associe"]
        with self.assertRaises(ValueError):
            generer_plan_fondation_dxf(semelles)

    def test_liste_vide_leve_une_erreur(self):
        with self.assertRaises(ValueError):
            generer_plan_fondation_dxf([])