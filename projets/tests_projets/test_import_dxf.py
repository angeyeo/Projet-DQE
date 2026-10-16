"""
Import de plan DXF : lecture des poteaux et des murs, plans côte à côte,
doublons, unités, association des murs aux poutres, et parcours API
(aperçu -> choix du plan -> confirmation).

Fichier de test construit avec ezdxf (unités mm) :
  plan 1 (à gauche) : trame 2 × 2 travées de 4 m -> 9 poteaux carrés de
    20 cm, + 1 poteau dessiné deux fois (décalé de 2 cm) ;
    murs : façade basse de 8,2 m (y = 0) contenant une porte (bloc imbriqué
    dont l'arc déborde de 90 cm), mur intérieur x = 4 m sur 8 m,
    et un morceau de 20 cm ;
  plan 2 (30 m à droite) : 4 poteaux à 5 m.

Attendu pour le plan 1 :
  12 tronçons de poutre entre poteaux voisins ;
  murs rattachés : 2 tronçons de la façade y = 0 + 2 tronçons de x = 4 -> 4.
"""

import shutil
import tempfile

import ezdxf
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import SimpleTestCase, override_settings
from rest_framework.test import APITestCase

from moteur_calcul.formules.trame import cle_segment, troncons_adjacents
from moteur_calcul.import_dxf.lecture_dxf import (
    AucunPoteauDXF,
    FichierDXFInvalide,
    analyser_fichier_dxf,
    associer_murs_aux_poutres,
)
from projets.models import ElementStructurel, Projet
from projets.tests_projets.utils import authentifier


def construire_dxf(chemin, unites=4, avec_poteaux=True):
    doc = ezdxf.new("R2010")
    doc.header["$INSUNITS"] = unites
    msp = doc.modelspace()
    col = doc.blocks.new("Column")
    col.add_lwpolyline([(-100, -100), (100, -100), (100, 100), (-100, 100)], close=True)
    porte = doc.blocks.new("Door")
    porte.add_arc((0, 0), 900, 0, 90)
    if avec_poteaux:
        for x in (0, 4000, 8000):
            for y in (0, 4000, 8000):
                msp.add_blockref("Column", (x, y), dxfattribs={"layer": "Structural - Bearing"})
        msp.add_blockref("Column", (20, 0), dxfattribs={"layer": "Structural - Bearing"})   # doublon
        for x in (30000, 35000):
            for y in (0, 5000):
                msp.add_blockref("Column", (x, y), dxfattribs={"layer": "Structural - Bearing"})

    def mur(nom, x0, y0, x1, y1, avec_porte=False):
        b = doc.blocks.new(nom)
        b.add_lwpolyline([(x0, y0), (x1, y0), (x1, y1), (x0, y1)], close=True)
        if avec_porte:
            b.add_blockref("Door", ((x0 + x1) / 2, y1))
        msp.add_blockref(nom, (0, 0), dxfattribs={"layer": "Structural - Bearing"})

    mur("Wall_1", -100, -100, 8100, 100, avec_porte=True)
    mur("Wall_2", 3900, 0, 4100, 8000)
    mur("Wall_3", 6000, 3900, 6200, 4000)          # 20 cm : morceau ignoré
    msp.add_line((0, 0), (8000, 8000), dxfattribs={"layer": "Cotes"})
    doc.saveas(chemin)


class LectureDXF(SimpleTestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.dossier = tempfile.mkdtemp()
        cls.chemin = f"{cls.dossier}/plan.dxf"
        construire_dxf(cls.chemin)

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.dossier, ignore_errors=True)
        super().tearDownClass()

    def test_plans_cote_a_cote(self):
        r = analyser_fichier_dxf(self.chemin)
        self.assertEqual(r["unite"], "mm")
        self.assertEqual([p["id"] for p in r["plans"]], ["plan-1", "plan-2"])
        self.assertEqual((r["plans"][0]["nb_poteaux"], r["plans"][0]["nb_doublons"]), (9, 1))
        self.assertEqual(r["plans"][1]["nb_poteaux"], 4)
        self.assertIsNone(r["plan_retenu"])
        self.assertNotIn("poteaux", r)
        self.assertTrue(any("2 plans détectés" in a for a in r["avertissements"]))

    def test_plan_retenu_en_coordonnees_locales(self):
        r = analyser_fichier_dxf(self.chemin, plan="plan-1")
        positions = sorted((round(p["x"], 3), round(p["y"], 3)) for p in r["poteaux"])
        self.assertEqual(positions[0], (0.0, 0.0))
        self.assertEqual(positions[-1], (8.0, 8.0))
        self.assertEqual(len(r["poteaux"]), 9)
        self.assertTrue(any("deux fois" in a for a in r["avertissements"]))
        # La porte (arc de 90 cm) ne compte pas dans l'épaisseur du mur.
        facade = next(m for m in r["murs"] if m["nom"] == "Wall_1")
        self.assertEqual((facade["axe"], facade["epaisseur_m"]), ("x", 0.2))
        self.assertAlmostEqual(facade["debut"][1], 0.0)
        self.assertEqual(len(r["murs"]), 2)
        self.assertTrue(any("moins de 30 cm" in a for a in r["avertissements"]))

    def test_murs_rattaches_aux_poutres(self):
        r = analyser_fichier_dxf(self.chemin, plan="plan-1")
        troncons = troncons_adjacents(r["poteaux"])
        self.assertEqual(len(troncons), 12)
        cles = associer_murs_aux_poutres(r["murs"], troncons)
        attendues = sorted({cle_segment((0, 0), (4, 0)), cle_segment((4, 0), (8, 0)),
                            cle_segment((4, 0), (4, 4)), cle_segment((4, 4), (4, 8))})
        self.assertEqual(cles, attendues)

    def test_recouvrement_insuffisant(self):
        # Mur de 1,5 m sous une poutre de 4 m (37,5 % < 50 %) : non rattaché.
        mur = {"axe": "x", "debut": (0.0, 0.0), "fin": (1.5, 0.0)}
        self.assertEqual(associer_murs_aux_poutres([mur], [("k", (0, 0), (4, 0))]), [])
        # Deux murs bout à bout (2 + 1 m = 75 %) : rattaché.
        murs = [mur | {"fin": (2.0, 0.0)}, {"axe": "x", "debut": (2.5, 0.1), "fin": (3.5, 0.1)}]
        self.assertEqual(associer_murs_aux_poutres(murs, [("k", (0, 0), (4, 0))]), ["k"])

    def test_plan_inconnu(self):
        with self.assertRaises(FichierDXFInvalide):
            analyser_fichier_dxf(self.chemin, plan="plan-9")

    def test_sans_unites_refuse(self):
        chemin = f"{self.dossier}/sans_unite.dxf"
        construire_dxf(chemin, unites=0)
        with self.assertRaises(FichierDXFInvalide) as ctx:
            analyser_fichier_dxf(chemin)
        self.assertIn("Unités", str(ctx.exception))

    def test_sans_poteaux_message_utile(self):
        chemin = f"{self.dossier}/sans_poteau.dxf"
        construire_dxf(chemin, avec_poteaux=False)
        with self.assertRaises(AucunPoteauDXF) as ctx:
            analyser_fichier_dxf(chemin)
        self.assertIn("POTEAUX", str(ctx.exception))

    def test_fichier_qui_n_est_pas_un_dxf(self):
        chemin = f"{self.dossier}/faux.dxf"
        with open(chemin, "w") as f:
            f.write("ceci n'est pas un plan")
        with self.assertRaises(FichierDXFInvalide):
            analyser_fichier_dxf(chemin)


class APIImportDXF(APITestCase):
    def setUp(self):
        self.media = tempfile.mkdtemp()
        self.reglage = override_settings(MEDIA_ROOT=self.media)
        self.reglage.enable()
        self.user, self.cabinet = authentifier(self)
        self.projet = Projet.objects.create(
            nom="Duplex", entreprise=self.cabinet, usage_batiment="habitation", nb_niveaux=1, hauteur_etage=3.0)
        self.url = f"/api/projets/{self.projet.id}/importer_plan/"
        chemin = f"{self.media}/source.dxf"
        construire_dxf(chemin)
        with open(chemin, "rb") as f:
            self.contenu = f.read()

    def tearDown(self):
        self.reglage.disable()
        shutil.rmtree(self.media, ignore_errors=True)

    def deposer(self, nom="plan.dxf", contenu=None):
        fichier = SimpleUploadedFile(nom, contenu if contenu is not None else self.contenu)
        return self.client.post(self.url, {"fichier": fichier}, format="multipart")

    def test_parcours_complet(self):
        r = self.deposer()
        self.assertEqual(r.status_code, 200, r.data)
        self.assertEqual(len(r.data["plans"]), 2)
        self.assertIsNone(r.data["plan_retenu"])
        self.assertEqual(self.projet.elements.count(), 0)

        # Calcul refusé tant que le plan des fondations n'est pas choisi.
        r = self.client.post(self.url, {"confirmer": True}, format="json")
        self.assertEqual(r.status_code, 400)
        self.assertIn("choisissez", r.data["erreur"])

        r = self.client.post(self.url, {"plan": "plan-1"}, format="json")
        self.assertEqual(r.status_code, 200, r.data)
        self.assertEqual((r.data["nb_travees_x"], r.data["portee_x"]), (2, 4.0))
        self.assertEqual(len(r.data["murs_proposes"]), 4)
        self.assertNotIn("nb_niveaux", r.data)
        self.projet.refresh_from_db()
        self.assertEqual(self.projet.parametres_import, {"format": "dxf", "plan": "plan-1"})

        r = self.client.post(self.url, {"confirmer": True}, format="json")
        self.assertEqual(r.status_code, 201, r.data)
        types = [e.type_element for e in self.projet.elements.all()]
        self.assertEqual(types.count(ElementStructurel.TypeElement.POTEAU), 9)
        self.assertEqual(types.count(ElementStructurel.TypeElement.SEMELLE), 9)
        self.assertEqual(types.count(ElementStructurel.TypeElement.POUTRE), 12)

    def test_murs_proposes_appliques_au_calcul(self):
        self.deposer()
        murs = self.client.post(self.url, {"plan": "plan-1"}, format="json").data["murs_proposes"]
        r = self.client.patch(f"/api/projets/{self.projet.id}/", {"poids_murs_kn_m2": 3.3, "murs_rdc": murs},
                              format="json")
        self.assertEqual(r.status_code, 200, r.data)
        r = self.client.post(self.url, {"confirmer": True}, format="json")
        self.assertEqual(r.status_code, 201, r.data)
        portant = [e for e in self.projet.elements.filter(type_element="poutre") if e.resultat_calcul["mur_rdc"]]
        self.assertEqual(len(portant), 4)
        self.assertFalse(any("ne correspondent plus" in h for h in r.data["hypotheses"]))

    def test_formats_refuses_avec_conseil(self):
        for nom, attendu in (("plan.pln", "ArchiCAD"), ("plan.pdf", "PDF"), ("plan.dwg", "DXF"),
                             ("plan.txt", "IFC ou DXF")):
            with self.subTest(nom=nom):
                r = self.deposer(nom, b"x")
                self.assertEqual(r.status_code, 400)
                self.assertIn(attendu, r.data["erreur"])

    def test_dxf_invalide(self):
        r = self.deposer("plan.dxf", b"pas un dxf")
        self.assertEqual(r.status_code, 400)
        self.assertIn("DXF", r.data["erreur"])

    def test_choix_de_plan_reserve_au_dxf(self):
        r = self.client.post(self.url, {"plan": "plan-1"}, format="json")
        self.assertEqual(r.status_code, 400)

    def test_autre_cabinet_404(self):
        from projets.tests_projets.utils import creer_cabinet, creer_membre
        intrus = creer_membre(creer_cabinet("Autre"), username="intrus")
        self.client.force_authenticate(user=intrus)
        self.assertEqual(self.deposer().status_code, 404)


class ControlesPlanImporte(SimpleTestCase):
    """Contrôles sur les positions et portées RÉELLES (plans irréguliers)."""

    def test_chevauchement_exact(self):
        from moteur_calcul.plausibilite import controler_chevauchements
        # Entraxe 1,06 m : 110 + 60 cm -> demi-somme 0,85 m < 1,06 : pas de chevauchement.
        self.assertEqual(controler_chevauchements([("S1", 0, 0, 110), ("S2", 1.06, 0, 60)]), [])
        # 130 + 110 cm -> 1,20 m > 1,06 m : chevauchement signalé.
        alertes = controler_chevauchements([("S1", 0, 0, 130), ("S2", 1.06, 0, 110)])
        self.assertEqual(len(alertes), 1)
        self.assertIn("S1 (130 cm) et S2 (110 cm) se chevauchent", alertes[0]["message"])
        # Décalées en diagonale (dy = 2 m) : aucun recouvrement.
        self.assertEqual(controler_chevauchements([("S1", 0, 0, 130), ("S2", 1.06, 2.0, 110)]), [])

    def test_poutre_de_plus_de_8_m_signalee(self):
        from moteur_calcul.plausibilite import controler_resultats
        alertes = controler_resultats([("PX27", "poutre", {"portee_m": 13.33}), ("PX1", "poutre", {"portee_m": 4.0})])
        self.assertEqual([a["code"] for a in alertes], ["POUTRE_PORTEE_INHABITUELLE"])
        self.assertIn("Poteau intermédiaire manquant", alertes[0]["message"])

    def test_murs_sur_poutres_non_calculees(self):
        from moteur_calcul.hypotheses import HypothesesCalcul
        from projets.services.trame_service import murs_orphelins
        hyp = HypothesesCalcul(g_plancher_kn_m2=5, origine_g="saisie", q_kn_m2=1.5, origine_q="saisie",
                               poids_murs_kn_m2=3.3, murs_rdc=frozenset({"a", "b"}))
        messages = murs_orphelins(hyp, [], troncons_non_calcules=["a"])
        self.assertEqual(len(messages), 2)
        self.assertIn("1 mur(s) posé(s) sur des poutres non calculées", messages[0])
        self.assertIn("1 tronçon(s) de mur du plan des murs ne correspondent plus", messages[1])
