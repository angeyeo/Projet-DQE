"""Hypothèse isostatique des poutres écrite partout (issue #68, audit A-05).

Règle B3 confirmée par le technicien BTP le 21/10/2026 : poutres calculées
travée par travée, Mu = pu L² / 8, sans continuité (Caquot non raccordé).
"""
import io

import openpyxl
from rest_framework.test import APITestCase

from moteur_calcul.hypotheses import HYPOTHESE_POUTRES_ISOSTATIQUES
from projets.models import Profil, Projet
from projets.services.dqe_calculator import calculer_projet_dqe
from projets.services.dqe_exporters import exporter_dqe_excel
from projets.tests_projets.utils import BAREME_TEST, authentifier


class HypotheseIsostatique(APITestCase):
    def setUp(self):
        self.user, self.cabinet = authentifier(self, role=Profil.Role.ADMIN, bareme=BAREME_TEST)
        self.projet = Projet.objects.create(
            nom="Réf", entreprise=self.cabinet, usage_batiment="habitation", nb_niveaux=2, hauteur_etage=3.0,
            nb_travees_x=2, nb_travees_y=2, portee_x=4.0, portee_y=3.5, contrainte_sol_kn_m2=150)
        self.reponse = self.client.post(f"/api/projets/{self.projet.id}/generer_trame/")
        for e in self.projet.elements.all():
            self.client.post(f"/api/elements/{e.id}/valider/")

    def test_hypothese_dans_les_resultats_et_le_dqe(self):
        self.assertIn(HYPOTHESE_POUTRES_ISOSTATIQUES, self.reponse.data["hypotheses"])
        self.assertIn("règle B3", HYPOTHESE_POUTRES_ISOSTATIQUES)
        poutre = self.projet.elements.filter(type_element="poutre").first()
        moment = next(t for t in poutre.resultat_calcul["trace"] if t["etape"] == "Moment ELU")
        self.assertIn("isostatique", moment["formule"])
        d = calculer_projet_dqe(self.projet, prix_unitaires=self.cabinet.get_prix_unitaires())
        self.assertIn(HYPOTHESE_POUTRES_ISOSTATIQUES, d["hypotheses_projet"])
        wb = openpyxl.load_workbook(io.BytesIO(exporter_dqe_excel(d).getvalue()))
        textes = [c for row in wb.worksheets[0].iter_rows(values_only=True) for c in row if isinstance(c, str)]
        self.assertTrue(any("isostatiques" in t for t in textes))
