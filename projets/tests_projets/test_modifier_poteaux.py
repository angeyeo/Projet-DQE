"""Étape 2 : ajouter, déplacer, supprimer des poteaux puis recalculer (issue #94).

Trame de départ : 2 × 2 travées de 4 m (poteaux en x, y ∈ {0, 4, 8}),
générée par le moteur (origine « trame »).
"""
from rest_framework.test import APITestCase

from projets.models import ElementStructurel, Projet
from projets.tests_projets.utils import BAREME_TEST, authentifier

T = ElementStructurel.TypeElement
O = ElementStructurel.OrigineGeometrie
TRAME = [{"x": 4.0 * i, "y": 4.0 * j} for i in range(3) for j in range(3)]


class ModifierPoteaux(APITestCase):
    def setUp(self):
        self.user, self.cabinet = authentifier(self, bareme=BAREME_TEST)
        self.projet = Projet.objects.create(
            nom="Villa", entreprise=self.cabinet, usage_batiment="habitation", nb_niveaux=2, hauteur_etage=3.0,
            contrainte_sol_kn_m2=150, nb_travees_x=2, nb_travees_y=2, portee_x=4.0, portee_y=4.0)
        self.assertEqual(self.client.post(f"/api/projets/{self.projet.id}/generer_trame/").status_code, 201)

    def modifier(self, poteaux):
        return self.client.post(f"/api/projets/{self.projet.id}/modifier_poteaux/", {"poteaux": poteaux},
                                format="json")

    def poteaux(self):
        return {(round(e.position_x, 3), round(e.position_y, 3)): e
                for e in self.projet.elements.filter(type_element=T.POTEAU)}

    def test_ajout_d_une_rangee_recalcule_poutres_et_charges(self):
        avant = self.poteaux()[(4.0, 8.0)].charge_calculee  # poteau de rive
        r = self.modifier(TRAME + [{"x": 4.0 * i, "y": 12.0} for i in range(3)])
        self.assertEqual(r.status_code, 201, r.data)
        self.assertEqual(r.data["poteaux"], {"total": 12, "saisis": 3, "conserves": 9})
        p = self.poteaux()
        self.assertEqual(len(p), 12)
        # 12 poteaux en 3 × 4 : 4 rangées × 2 poutres en X + 3 files × 3 poutres en Y = 17 poutres.
        self.assertEqual(self.projet.elements.filter(type_element=T.POUTRE).count(), 17)
        self.assertEqual({p[(4.0 * i, 12.0)].origine_geometrie for i in range(3)}, {O.SAISI})
        self.assertEqual({p[(t["x"], t["y"])].origine_geometrie for t in TRAME}, {O.TRAME})
        # (4, 8) n'est plus en rive : surface d'influence 4 × 4 au lieu de 4 × 2, charge plus forte,
        # et égale à celle de (4, 4), son symétrique dans la nouvelle trame.
        self.assertGreater(p[(4.0, 8.0)].charge_calculee, avant)
        self.assertAlmostEqual(p[(4.0, 8.0)].charge_calculee, p[(4.0, 4.0)].charge_calculee, places=6)
        # Poutres entre poteaux saisis et poteaux de trame : origine « saisi ».
        poutres = self.projet.elements.filter(type_element=T.POUTRE)
        self.assertEqual(sum(1 for e in poutres if e.origine_geometrie == O.SAISI), 5)
        self.projet.refresh_from_db()
        self.assertEqual(self.projet.source_structure, Projet.SourceStructure.MIXTE)
        self.assertTrue(any(h.startswith("Structure modifiée par l'utilisateur : 3 poteau(x)") for h in r.data["hypotheses"]))

    def test_modifier_poteaux_v1_persiste_les_nouveaux_poteaux(self):
        projet_v1 = Projet.objects.create(
            nom="Villa API v1", entreprise=self.cabinet, usage_batiment="habitation", nb_niveaux=2,
            hauteur_etage=3.0, contrainte_sol_kn_m2=150, nb_travees_x=2, nb_travees_y=2,
            portee_x=4.0, portee_y=4.0,
        )
        self.assertEqual(
            self.client.post(f"/api/v1/projets/{projet_v1.id}/generer_trame/").status_code, 201,
        )
        response = self.client.post(
            f"/api/v1/projets/{projet_v1.id}/modifier_poteaux/",
            {"poteaux": TRAME + [{"x": 0, "y": 12}, {"x": 4, "y": 12}, {"x": 8, "y": 12}]},
            format="json",
        )
        self.assertEqual(response.status_code, 201, response.data)
        self.assertEqual(response.data["poteaux"], {"total": 12, "saisis": 3, "conserves": 9})
        projet_v1.refresh_from_db()
        self.assertEqual(projet_v1.source_structure, Projet.SourceStructure.MIXTE)
        self.assertEqual(projet_v1.elements.filter(type_element=T.POTEAU).count(), 12)

    def test_deplacement_et_suppression(self):
        # La file x = 8 est déplacée en x = 9 : seconde travée de 5 m, poteaux déplacés « saisi ».
        deplaces = [t if t["x"] < 8 else {"x": 9.0, "y": t["y"]} for t in TRAME]
        r = self.modifier(deplaces)
        self.assertEqual(r.status_code, 201, r.data)
        p = self.poteaux()
        self.assertEqual({p[(9.0, y)].origine_geometrie for y in (0.0, 4.0, 8.0)}, {O.SAISI})
        self.assertIn(5.0, {e.portee for e in self.projet.elements.filter(type_element=T.POUTRE)})
        # Suppression de cette file : 2 × 3 poteaux, 3 poutres en X + 4 en Y.
        r = self.modifier([t for t in deplaces if t["x"] < 8])
        self.assertEqual(r.status_code, 201, r.data)
        self.assertEqual(len(self.poteaux()), 6)
        self.assertEqual(self.projet.elements.filter(type_element=T.POUTRE).count(), 7)
        self.assertEqual(self.projet.elements.filter(type_element=T.SEMELLE).count(), 6)

    def test_annulation_retour_a_la_trame(self):
        self.modifier(TRAME + [{"x": 4.0 * i, "y": 12.0} for i in range(3)])
        r = self.modifier(TRAME)  # annule l'ajout
        self.assertEqual(r.status_code, 201, r.data)
        self.projet.refresh_from_db()
        self.assertEqual((self.projet.source_structure, self.projet.poteaux_saisis), (Projet.SourceStructure.TRAME, []))
        self.assertEqual({e.origine_geometrie for e in self.projet.elements.all()}, {O.TRAME})
        self.assertFalse(any(h.startswith("Structure modifiée") for h in r.data["hypotheses"]))

    def test_regeneration_conserve_les_poteaux_et_leur_origine(self):
        self.modifier(TRAME + [{"x": 4.0 * i, "y": 12.0} for i in range(3)])
        self.client.patch(f"/api/projets/{self.projet.id}/", {"hauteur_etage": 3.2}, format="json")
        r = self.client.post(f"/api/projets/{self.projet.id}/placer_poteaux/", {}, format="json")
        self.assertEqual(r.status_code, 201, r.data)
        p = self.poteaux()
        self.assertEqual(len(p), 12)
        self.assertEqual(sum(1 for e in p.values() if e.origine_geometrie == O.SAISI), 3)
        self.projet.refresh_from_db()
        self.assertEqual(self.projet.source_structure, Projet.SourceStructure.MIXTE)
        # Revenir à la trame d'origine efface la liste modifiée, et le rappel disparaît.
        r = self.client.post(f"/api/projets/{self.projet.id}/generer_trame/")
        self.assertFalse(any(h.startswith("Structure modifiée") for h in r.data["hypotheses"]))
        self.projet.refresh_from_db()
        self.assertEqual((self.projet.source_structure, self.projet.poteaux_saisis), (Projet.SourceStructure.TRAME, []))

    def test_le_client_ne_choisit_pas_l_origine(self):
        r = self.modifier(TRAME + [{"x": 4.0 * i, "y": 12.0, "origine": "plan"} for i in range(3)])
        self.assertEqual(r.status_code, 201, r.data)
        self.assertEqual({self.poteaux()[(4.0 * i, 12.0)].origine_geometrie for i in range(3)}, {O.SAISI})

    def test_refus_sans_modification(self):
        avant = sorted(self.poteaux())
        self.assertEqual(self.client.post(f"/api/projets/{self.projet.id}/modifier_poteaux/", {}, format="json").status_code, 400)
        r = self.modifier(TRAME + [{"x": 0.1, "y": 0.0}])
        self.assertEqual(r.status_code, 400)
        self.assertIn("doublon", r.data["erreur"])
        self.assertEqual(sorted(self.poteaux()), avant)

    def test_autre_cabinet(self):
        authentifier(self, nom_cabinet="Concurrent")
        self.assertEqual(self.modifier(TRAME).status_code, 404)
