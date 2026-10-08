"""
Hypothèses explicites (G, poids propre, méthode des semelles), traçabilité,
DQE professionnel (formules, source/date des prix, sous-lots, marge, TVA),
plausibilité et variantes.
"""

from decimal import Decimal

from django.utils import timezone
from rest_framework import status
from rest_framework.test import APITestCase

from projets.models import ElementStructurel, Profil, Projet
from projets.services.dqe_calculator import calculer_projet_dqe

from .utils import BAREME_TEST, authentifier, creer_cabinet, creer_membre


def projet_grille(cabinet, **kw):
    d = dict(nom="Réf", entreprise=cabinet, usage_batiment="habitation", nb_niveaux=2, hauteur_etage=3.0,
             nb_travees_x=2, nb_travees_y=2, portee_x=4.0, portee_y=3.5, contrainte_sol_kn_m2=150)
    d.update(kw)
    return Projet.objects.create(**d)


class TestHypothesesTrame(APITestCase):
    def setUp(self):
        self.user, self.cabinet = authentifier(self, role=Profil.Role.ADMIN, bareme=BAREME_TEST)

    def generer(self, projet):
        r = self.client.post(f"/api/projets/{projet.id}/generer_trame/")
        self.assertEqual(r.status_code, status.HTTP_201_CREATED, r.data)
        return r

    def central(self, projet, type_el="poteau"):
        return projet.elements.get(identifiant=("P_1_1" if type_el == "poteau" else "S_1_1"))

    def test_forfait_g_signale_et_trace(self):
        # Poids propre de l'ossature explicitement exclu : on isole l'effet du forfait G.
        projet = projet_grille(self.cabinet, inclure_poids_propre_ossature=False)
        r = self.generer(projet)
        self.assertTrue(any(h.startswith("HYPOTHÈSE : charge permanente") for h in r.data["hypotheses"]))
        self.assertTrue(any(h.startswith("ALERTE : le forfait G") for h in r.data["hypotheses"]))
        p = self.central(projet)
        # Calcul manuel (R+1, S = 14 m²) : Nu = 1,35 × 140 + 1,5 × 42 = 252 kN ; Ns = 182 kN
        # (Q0 toiture = 1,5 × 14 = 21 kN = Q1 d'étage en habitation)
        self.assertAlmostEqual(p.charge_calculee, 252.0, places=2)
        self.assertAlmostEqual(p.charge_service, 182.0, places=2)
        self.assertEqual(p.resultat_calcul["hypotheses_calcul"]["origine_g"], "forfait")
        self.assertIn("Effort ELU", [e["etape"] for e in p.resultat_calcul["trace"]])
        self.assertEqual(p.nombre_identiques, 2)

    def test_poids_propre_ajoute_par_defaut(self):
        """Décision du technicien (07/10/2026) : poids propre poutres/poteaux AJOUTÉ par défaut.

        Calcul manuel, poteau central R+1 (portées 4,0 et 3,5 m, S = 14 m²) :
          G planchers / niveau = 14 × 5 = 70 kN
          poutres (b = 0,20, h = L/8) : 2 × (4/2 × 0,2 × 0,5 × 25) + 2 × (3,5/2 × 0,2 × 0,4375 × 25)
                                       = 10 + 7,65625 = 17,65625 kN
          poteau 20 × 20, h = 3 m : 0,2² × 3 × 25 = 3 kN
          G = 2 × (70 + 17,65625 + 3) = 181,3125 kN ; Q = 21 + 21 = 42 kN
          Nu = 1,35 × 181,3125 + 1,5 × 42 = 307,771875 kN ; Ns = 223,3125 kN
        """
        projet = projet_grille(self.cabinet)
        self.assertTrue(projet.inclure_poids_propre_ossature)
        r = self.generer(projet)
        p = self.central(projet)
        self.assertAlmostEqual(p.charge_calculee, 307.771875, places=4)
        self.assertAlmostEqual(p.charge_service, 223.3125, places=4)
        self.assertIn("Poids propre poutres / niveau", [e["etape"] for e in p.resultat_calcul["trace"]])
        self.assertFalse(any(h.startswith("ALERTE : le forfait G") for h in r.data["hypotheses"]))
        self.assertTrue(any("Q de toiture = 1,5 kN/m² (valeur validée" in h for h in r.data["hypotheses"]))

    def test_g_saisie_puis_couches_prioritaires(self):
        projet = projet_grille(self.cabinet, charge_permanente_kn_m2=6.0, inclure_poids_propre_ossature=False)
        self.generer(projet)
        self.assertEqual(self.central(projet).resultat_calcul["hypotheses_calcul"]["origine_g"], "saisie")
        # G = 6 : Nu = 1,35 × (2 × 84) + 1,5 × 42 = 289,8 kN
        self.assertAlmostEqual(self.central(projet).charge_calculee, 289.8, places=2)
        r = self.client.patch(f"/api/projets/{projet.id}/", {
            "couches_permanentes": [{"designation": "dalle", "epaisseur_m": 0.16, "poids_volumique_kn_m3": 25},
                                    {"type": "carrelage_colle"}]}, format="json")
        self.assertEqual(r.status_code, 200, r.data)
        self.generer(projet)
        h = self.central(projet).resultat_calcul["hypotheses_calcul"]
        self.assertEqual(h["origine_g"], "couches")
        self.assertAlmostEqual(h["g_plancher_kn_m2"], 4.5)

    def test_couches_invalides_refusees(self):
        projet = projet_grille(self.cabinet)
        r = self.client.patch(f"/api/projets/{projet.id}/", {"couches_permanentes": [{"designation": "x"}]},
                              format="json")
        self.assertEqual(r.status_code, 400)
        self.assertIn("couches_permanentes", r.data)

    def test_methode_els_semelles(self):
        projet = projet_grille(self.cabinet, methode_semelles="ELS", contrainte_sol_kn_m2=75,
                               inclure_poids_propre_ossature=False)
        self.generer(projet)
        s = self.central(projet, "semelle")
        # Ns = 182 kN, σ = 75 : √(182/75) = 1,558 m -> 160 cm (ELU aurait donné 185 cm)
        self.assertEqual(s.resultat_calcul["methode"], "ELS")
        self.assertEqual(s.resultat_calcul["cote_cm"], 160)
        # Recalcul isolé : même méthode, même résultat
        r = self.client.post(f"/api/elements/{s.id}/calculer/")
        self.assertEqual(r.status_code, 200, r.data)
        self.assertEqual(r.data["resultat_calcul"]["cote_cm"], 160)


class TestDQEProfessionnel(APITestCase):
    def setUp(self):
        self.user, self.cabinet = authentifier(self, role=Profil.Role.ADMIN, bareme=BAREME_TEST)
        self.projet = projet_grille(self.cabinet)
        self.client.post(f"/api/projets/{self.projet.id}/generer_trame/")
        for e in self.projet.elements.all():
            self.client.post(f"/api/elements/{e.id}/valider/")

    def dqe(self):
        self.cabinet.refresh_from_db()
        return calculer_projet_dqe(self.projet, prix_unitaires=self.cabinet.get_prix_unitaires())

    def test_niveaux_identiques_multiplies_et_formule(self):
        d = self.dqe()
        p = self.projet.elements.get(identifiant="P_1_1")
        a = p.resultat_valide["cote_cm"] / 100
        ligne = next(l for l in d["lignes"] if l["repere"] == "P_1_1" and l["categorie"] == "BETON")
        self.assertAlmostEqual(ligne["quantite"], round(a * a * 3.0 * 2, 3))
        self.assertIn("× 2 (niveaux identiques)", ligne["formule_quantite"])
        self.assertEqual(ligne["type_donnee"], "calculé")
        semelle_acier = next(l for l in d["lignes"] if l["repere"] == "S_1_1" and l["categorie"] == "ACIER")
        self.assertEqual(semelle_acier["source_quantite"], "calcul_moteur")

    def test_sous_lots_et_somme(self):
        d = self.dqe()
        for lot in d["lots"]:
            self.assertEqual(sum(sl["sous_total"] for sl in lot["sous_lots"]), lot["sous_total"])
        self.assertEqual(sum(l["sous_total"] for l in d["lots"]), d["total_general"])
        libelles = {sl["libelle"] for lot in d["lots"] for sl in lot["sous_lots"]}
        self.assertTrue({"Poteaux", "Poutres", "Fondations isolées"} <= libelles)

    def test_determinisme(self):
        self.assertEqual(self.dqe(), self.dqe())

    def test_source_et_date_des_prix(self):
        prix = dict(BAREME_TEST, beton_m3=95000)
        r = self.client.patch("/api/entreprise/", {"prix_unitaires": prix, "prix_origines": {"acier_kg": "reference"}},
                              format="json")
        self.assertEqual(r.status_code, 200, r.data)
        meta = r.data["prix_unitaires_meta"]
        self.assertEqual(meta["beton_m3"]["source"], "saisie")
        self.assertEqual(meta["beton_m3"]["date"], timezone.localdate().isoformat())
        self.assertNotIn("acier_kg", meta)  # valeur inchangée : pas de nouvelle trace
        ligne = next(l for l in self.dqe()["lignes"] if l["categorie"] == "BETON")
        self.assertEqual(ligne["prix_unitaire"], 95000)
        self.assertEqual(ligne["prix_source"], "barème du cabinet")
        self.assertEqual(ligne["prix_date"], timezone.localdate().isoformat())

    def test_tva_et_ttc(self):
        f = self.dqe()["finances"]
        self.assertIsNone(f["total_ttc"])
        self.assertTrue(any("TVA non renseigné" in m for m in f["messages"]))
        self.cabinet.taux_tva_pct = Decimal("18")
        self.cabinet.save()
        d = self.dqe()
        f = d["finances"]
        self.assertEqual(f["total_ht"], d["total_general"])
        self.assertEqual(f["montant_tva"], int((Decimal(d["total_general"]) * Decimal("0.18")).quantize(Decimal("1"),
                                                                                                    rounding="ROUND_HALF_UP")))
        self.assertEqual(f["total_ttc"], f["total_ht"] + f["montant_tva"])

    def test_debourse_sec_et_marge(self):
        self.cabinet.nature_prix = "debourse_sec"
        self.cabinet.save()
        f = self.dqe()["finances"]
        self.assertIsNone(f["total_ht"])
        self.assertTrue(any("marge non renseigné" in m for m in f["messages"]))
        self.cabinet.taux_marge_pct = Decimal("10")
        self.cabinet.save()
        d = self.dqe()
        self.assertEqual(d["finances"]["total_ht"], d["total_general"] + round(d["total_general"] * 0.10))

    def test_exports_avec_finances(self):
        self.cabinet.taux_tva_pct = Decimal("18")
        self.cabinet.save()
        for fmt in ("pdf", "excel"):
            r = self.client.get(f"/api/projets/{self.projet.id}/generer-dqe/?export={fmt}")
            self.assertEqual(r.status_code, 200, fmt)

    def test_nombre_identiques_invalide(self):
        e = self.projet.elements.first()
        r = self.client.patch(f"/api/elements/{e.id}/", {"nombre_identiques": 0}, format="json")
        self.assertEqual(r.status_code, 400)


class TestPlausibiliteEtVariantes(APITestCase):
    def setUp(self):
        self.user, self.cabinet = authentifier(self, bareme=BAREME_TEST)

    def test_alertes_plausibilite_dans_le_projet(self):
        projet = projet_grille(self.cabinet, portee_x=9.0, contrainte_sol_kn_m2=40)
        r = self.client.get(f"/api/projets/{projet.id}/")
        codes = {a["code"] for a in r.data["alertes_plausibilite"]}
        self.assertIn("PORTEE_X_INHABITUELLE", codes)
        self.assertIn("SOL_INHABITUEL", codes)
        projet.refresh_from_db()
        self.assertEqual(projet.portee_x, 9.0)  # jamais modifiée

    def test_variantes_recalculees_sans_rien_enregistrer(self):
        projet = projet_grille(self.cabinet)
        self.client.post(f"/api/projets/{projet.id}/generer_trame/")
        avant = {e.identifiant: e.resultat_calcul for e in projet.elements.all()}
        r = self.client.post(f"/api/projets/{projet.id}/variantes/", {"variantes": [
            {"nom": "Sol faible", "modifications": {"contrainte_sol_kn_m2": 75}},
            {"nom": "Semelles ELS", "modifications": {"methode_semelles": "ELS"}},
        ]}, format="json")
        self.assertEqual(r.status_code, 200, r.data)
        base, sol, els = r.data["variantes"]
        self.assertIsNone(base["erreur"])
        self.assertGreater(sol["semelle_cote_max_cm"], base["semelle_cote_max_cm"])
        self.assertGreater(sol["dqe"]["total_general"], base["dqe"]["total_general"])
        self.assertLess(els["dqe"]["total_general"], base["dqe"]["total_general"])
        self.assertIsNotNone(sol["ecart_pct"])
        # Rien n'a été enregistré
        projet.refresh_from_db()
        self.assertEqual(projet.contrainte_sol_kn_m2, 150)
        self.assertEqual({e.identifiant: e.resultat_calcul for e in projet.elements.all()}, avant)
        self.assertFalse(projet.elements.filter(statut=ElementStructurel.Statut.VALIDE).exists())

    def test_variante_champ_interdit_et_autre_cabinet(self):
        projet = projet_grille(self.cabinet)
        r = self.client.post(f"/api/projets/{projet.id}/variantes/",
                             {"variantes": [{"modifications": {"entreprise": 1}}]}, format="json")
        self.assertEqual(r.status_code, 400)
        autre = creer_cabinet("Autre")
        self.client.force_authenticate(creer_membre(autre, username="intrus"))
        r = self.client.post(f"/api/projets/{projet.id}/variantes/",
                             {"variantes": [{"modifications": {"contrainte_sol_kn_m2": 75}}]}, format="json")
        self.assertEqual(r.status_code, 404)


class TestAuditDonnees(APITestCase):
    def test_audit_lecture_seule(self):
        import io
        import json as _json

        from django.core.management import call_command

        cab = creer_cabinet("C", {"beton_m3": 1})
        p = projet_grille(cab, nb_niveaux=3, contrainte_sol_kn_m2=None)
        ElementStructurel.objects.create(projet=p, identifiant="P1", type_element="poteau", taux_travail_sol=0.2,
                                         resultat_calcul={"cote_cm": 20})
        Projet.objects.create(nom="Orphelin")
        avant = [(e.pk, e.taux_travail_sol, e.nombre_identiques, e.resultat_calcul) for e in ElementStructurel.objects.all()]
        sortie = io.StringIO()
        call_command("audit_donnees_production", "--json", stdout=sortie)
        r = _json.loads(sortie.getvalue())
        self.assertEqual(len(r["projets_orphelins"]), 1)
        self.assertEqual(len(r["sols_suspects"]["elements"]), 1)
        self.assertEqual(r["projets_multi_niveaux_a_regenerer"][0]["elements_a_1_niveau"], 1)
        self.assertEqual(avant, [(e.pk, e.taux_travail_sol, e.nombre_identiques, e.resultat_calcul)
                                 for e in ElementStructurel.objects.all()])
