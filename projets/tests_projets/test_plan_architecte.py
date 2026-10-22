"""Plan d'architecte : fond de plan + poteaux placés par l'utilisateur (issue #93).

Règles vérifiées :
  - un DXF sans poteau est accepté en mode architecte et ne crée RIEN ;
  - aucun poteau n'est déduit des traits du dessin ;
  - les éléments créés depuis des poteaux placés portent l'origine « saisi » ;
  - l'avertissement « Structure placée par l'utilisateur » est permanent ;
  - mêmes positions, même moteur : résultats identiques à un plan importé.
"""
import shutil
import tempfile

import ezdxf
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import SimpleTestCase, override_settings
from rest_framework.test import APITestCase

from moteur_calcul.import_dxf.fond_plan import FondPlanVide, lire_fond_plan
from projets.models import ElementStructurel, Projet
from projets.tests_projets.utils import BAREME_TEST, authentifier

T = ElementStructurel.TypeElement
GRILLE_3X3 = [{"x": 4.0 * i, "y": 4.0 * j} for i in range(3) for j in range(3)]


def dxf_architecte(chemin, unites=6):
    """Murs en polylignes, une porte en arc, un WC en bloc : aucun poteau."""
    d = ezdxf.new()
    d.header["$INSUNITS"] = unites
    m = d.modelspace()
    k = 1000 if unites == 4 else 1
    m.add_lwpolyline([(0, 0), (8 * k, 0), (8 * k, 8 * k), (0, 8 * k)], close=True, dxfattribs={"layer": "MURS_ARCHI"})
    m.add_arc((2 * k, 0), radius=0.9 * k, start_angle=0, end_angle=90)
    wc = d.blocks.new("WC")
    wc.add_lwpolyline([(0, 0), (0.4 * k, 0), (0.4 * k, 0.6 * k), (0, 0.6 * k)], close=True)
    m.add_blockref("WC", (6 * k, 6 * k), dxfattribs={"layer": "New_Interior - Furniture"})
    m.add_text("CUISINE").set_placement((3 * k, 3 * k))
    d.saveas(chemin)


def dxf_structure(chemin):
    d = ezdxf.new()
    d.header["$INSUNITS"] = 6
    b = d.blocks.new("Column_1")
    b.add_lwpolyline([(-0.1, -0.1), (0.1, -0.1), (0.1, 0.1), (-0.1, 0.1)], close=True)
    m = d.modelspace()
    for p in GRILLE_3X3:
        m.add_blockref("Column_1", (p["x"], p["y"]), dxfattribs={"layer": "POTEAUX"})
    d.saveas(chemin)


class FondPlan(SimpleTestCase):
    def setUp(self):
        self.dossier = tempfile.mkdtemp()

    def tearDown(self):
        shutil.rmtree(self.dossier, ignore_errors=True)

    def test_traits_en_metres_dans_le_repere_local(self):
        chemin = f"{self.dossier}/a.dxf"
        dxf_architecte(chemin)
        r = lire_fond_plan(chemin)
        self.assertEqual((r["largeur_m"], r["profondeur_m"]), (8.0, 8.0))
        self.assertIn([0.0, 0.0, 8.0, 0.0], r["segments"])
        self.assertFalse(r["tronque"])
        # 4 côtés de mur + 4 côtés du WC (bloc déplié) + l'arc découpé en segments ; le texte est ignoré.
        self.assertGreater(r["nb_segments"], 8)

    def test_millimetres_convertis(self):
        chemin = f"{self.dossier}/mm.dxf"
        dxf_architecte(chemin, unites=4)
        r = lire_fond_plan(chemin)
        self.assertEqual((r["unite"], r["largeur_m"]), ("mm", 8.0))

    def test_dessin_vide_refuse(self):
        chemin = f"{self.dossier}/vide.dxf"
        d = ezdxf.new()
        d.header["$INSUNITS"] = 6
        d.modelspace().add_text("RIEN")
        d.saveas(chemin)
        with self.assertRaises(FondPlanVide):
            lire_fond_plan(chemin)


class APIPlanArchitecte(APITestCase):
    def setUp(self):
        self.media = tempfile.mkdtemp()
        self.reglage = override_settings(MEDIA_ROOT=self.media)
        self.reglage.enable()
        self.user, self.cabinet = authentifier(self, bareme=BAREME_TEST)
        self.projet = self.nouveau_projet("Villa")
        dxf_architecte(f"{self.media}/archi.dxf")
        dxf_structure(f"{self.media}/structure.dxf")

    def tearDown(self):
        self.reglage.disable()
        shutil.rmtree(self.media, ignore_errors=True)

    def nouveau_projet(self, nom):
        return Projet.objects.create(nom=nom, entreprise=self.cabinet, usage_batiment="habitation", nb_niveaux=2,
                                     hauteur_etage=3.0, contrainte_sol_kn_m2=150)

    def deposer(self, projet, fichier, **extra):
        with open(f"{self.media}/{fichier}", "rb") as f:
            contenu = f.read()
        return self.client.post(f"/api/projets/{projet.id}/importer_plan/",
                                {"fichier": SimpleUploadedFile(fichier, contenu), **extra}, format="multipart")

    def placer(self, projet, poteaux=None):
        corps = {} if poteaux is None else {"poteaux": poteaux}
        return self.client.post(f"/api/projets/{projet.id}/placer_poteaux/", corps, format="json")

    def test_dxf_sans_poteau_accepte_en_mode_architecte_sans_rien_creer(self):
        r = self.deposer(self.projet, "archi.dxf", mode="architecte")
        self.assertEqual(r.status_code, 200, r.data)
        self.assertEqual(r.data["mode"], "architecte")
        self.assertEqual(r.data["largeur_m"], 8.0)
        self.assertEqual(self.projet.elements.count(), 0)
        # Le même fichier reste refusé en mode « plan avec structure » : rien n'est deviné.
        self.assertEqual(self.deposer(self.nouveau_projet("Autre"), "archi.dxf").status_code, 400)
        # Le fond est relu plus tard (réouverture du projet).
        r = self.client.get(f"/api/projets/{self.projet.id}/fond_plan/")
        self.assertEqual((r.status_code, r.data["nb_segments"] > 8), (200, True))

    def test_mode_architecte_refuse_un_ifc(self):
        r = self.client.post(f"/api/projets/{self.projet.id}/importer_plan/",
                             {"fichier": SimpleUploadedFile("plan.ifc", b"ISO-10303-21;"), "mode": "architecte"},
                             format="multipart")
        self.assertEqual(r.status_code, 400)
        self.assertIn("DXF", r.data["erreur"])

    def test_placement_cree_la_structure_d_origine_saisie(self):
        self.deposer(self.projet, "archi.dxf", mode="architecte")
        r = self.placer(self.projet, GRILLE_3X3)
        self.assertEqual(r.status_code, 201, r.data)
        els = list(self.projet.elements.all())
        compte = {t: sum(1 for e in els if e.type_element == t) for t in (T.POTEAU, T.SEMELLE, T.POUTRE)}
        self.assertEqual(compte, {T.POTEAU: 9, T.SEMELLE: 9, T.POUTRE: 12})
        self.assertEqual({e.origine_geometrie for e in els}, {ElementStructurel.OrigineGeometrie.SAISI})
        self.assertIn("Structure placée par l'utilisateur, non lue dans le plan.", r.data["hypotheses"])
        self.projet.refresh_from_db()
        self.assertEqual(self.projet.source_structure, Projet.SourceStructure.SAISIE)
        self.assertEqual(self.projet.poteaux_saisis, [{**p, "origine": "saisi"} for p in GRILLE_3X3])
        # Avertissement permanent : repris dans les hypothèses du projet (résultats et DQE).
        r = self.client.get(f"/api/projets/{self.projet.id}/")
        self.assertIn("Structure placée par l'utilisateur, non lue dans le plan.",
                      r.data["hypotheses_calcul"]["hypotheses"])
        # Le calcul « confirmer » d'un plan importé est refusé en mode architecte.
        r = self.client.post(f"/api/projets/{self.projet.id}/importer_plan/", {"confirmer": True}, format="json")
        self.assertEqual(r.status_code, 400)

    def test_regeneration_sans_liste_reprend_les_poteaux_enregistres(self):
        self.placer(self.projet, GRILLE_3X3)
        # Modification par l'API, comme l'interface (les poteaux saisis ne sont pas modifiables ainsi).
        self.client.patch(f"/api/projets/{self.projet.id}/", {"hauteur_etage": 3.2}, format="json")
        r = self.placer(self.projet)
        self.assertEqual(r.status_code, 201, r.data)
        poteaux = self.projet.elements.filter(type_element=T.POTEAU)
        self.assertEqual(poteaux.count(), 9)
        self.assertEqual({p.hauteur_poteau for p in poteaux}, {3.2})

    def test_memes_positions_memes_resultats_qu_un_plan_importe(self):
        """Seule l'origine change : sections et charges identiques."""
        importe = self.nouveau_projet("Importé")
        self.deposer(importe, "structure.dxf")
        self.assertEqual(self.client.post(f"/api/projets/{importe.id}/importer_plan/", {"confirmer": True},
                                          format="json").status_code, 201)
        self.assertEqual(self.placer(self.projet, GRILLE_3X3).status_code, 201)

        def signature(projet):
            return sorted((e.type_element, round(e.position_x, 3), round(e.position_y, 3), e.charge_calculee,
                           e.portee, (e.resultat_calcul or {}).get("cote_cm"),
                           (e.resultat_calcul or {}).get("hauteur_cm"), (e.resultat_calcul or {}).get("largeur_cm"))
                          for e in projet.elements.all())

        self.assertEqual(signature(self.projet), signature(importe))
        self.assertEqual({e.origine_geometrie for e in importe.elements.all()},
                         {ElementStructurel.OrigineGeometrie.PLAN})

    def test_poteau_isole_signale_jamais_invente(self):
        poteaux = GRILLE_3X3 + [{"x": 20.0, "y": 21.5}]
        r = self.placer(self.projet, poteaux)
        self.assertEqual(r.status_code, 201, r.data)
        self.assertEqual(self.projet.elements.filter(type_element=T.POTEAU).count(), 9)
        self.assertTrue(any("surface d'influence" in a for a in r.data["avertissements"]))

    def test_aucun_poteau_calculable_rien_n_est_modifie(self):
        self.placer(self.projet, GRILLE_3X3)
        r = self.placer(self.projet, [{"x": 0, "y": 0}, {"x": 4, "y": 0}])  # une seule direction
        self.assertEqual(r.status_code, 400)
        self.assertIn("aucun poteau n'a pu être calculé", r.data["erreur"])
        self.assertEqual(self.projet.elements.filter(type_element=T.POTEAU).count(), 9)
        self.projet.refresh_from_db()
        self.assertEqual(self.projet.poteaux_saisis, [{**p, "origine": "saisi"} for p in GRILLE_3X3])

    def test_validations(self):
        cas = [
            ([], "au moins un poteau"),
            ([{"x": 0}], "coordonnées x et y"),
            ([{"x": "abc", "y": 1}], "non numériques"),
            ([{"x": 1e6, "y": 0}], "hors limites"),
            ([{"x": 0, "y": 0}, {"x": 0.1, "y": 0}], "doublon"),
            ([{"x": i, "y": 0} for i in range(501)], "500 au maximum"),
        ]
        for poteaux, attendu in cas:
            with self.subTest(attendu=attendu):
                r = self.placer(self.projet, poteaux)
                self.assertEqual(r.status_code, 400)
                self.assertIn(attendu, r.data["erreur"])
        self.assertEqual(self.projet.elements.count(), 0)

    def test_parametres_manquants(self):
        self.projet.hauteur_etage = None
        self.projet.save()
        r = self.placer(self.projet, GRILLE_3X3)
        self.assertEqual(r.status_code, 400)

    def test_autre_cabinet_et_non_connecte(self):
        self.client.force_authenticate(user=None)
        self.assertEqual(self.placer(self.projet, GRILLE_3X3).status_code, 401)
        authentifier(self, nom_cabinet="Concurrent")
        self.assertEqual(self.placer(self.projet, GRILLE_3X3).status_code, 404)
        self.assertEqual(self.client.get(f"/api/projets/{self.projet.id}/fond_plan/").status_code, 404)

    def test_trame_et_plan_marquent_leur_origine(self):
        p = self.nouveau_projet("Trame")
        p.nb_travees_x, p.nb_travees_y, p.portee_x, p.portee_y = 2, 2, 4.0, 4.0
        p.save()
        self.assertEqual(self.client.post(f"/api/projets/{p.id}/generer_trame/").status_code, 201)
        self.assertEqual({e.origine_geometrie for e in p.elements.all()}, {ElementStructurel.OrigineGeometrie.TRAME})
        p.refresh_from_db()
        self.assertEqual(p.source_structure, Projet.SourceStructure.TRAME)
        # Le client ne peut pas forcer l'origine.
        r = self.client.patch(f"/api/projets/{p.id}/", {"source_structure": "saisie", "poteaux_saisis": [{"x": 1, "y": 1}]},
                              format="json")
        p.refresh_from_db()
        self.assertEqual((p.source_structure, p.poteaux_saisis), (Projet.SourceStructure.TRAME, []))
