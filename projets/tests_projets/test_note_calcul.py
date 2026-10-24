"""Note de calcul (issue #96).

CAS DE RÉFÉRENCE recalculé à la main : trame 2 × 2 travées de 4 m, R+1
(2 niveaux), hauteur d'étage 3 m, habitation (G = 5 kN/m² par défaut,
Q = 1,5 kN/m², toiture-terrasse Q0 = 1,5 kN/m²), sol 150 kN/m²,
poids propre de l'ossature inclus, fc28 = 25 MPa, fe = 500 MPa.

Poteau d'angle P_0_0 :
  S  = (0/2 + 4/2) × (0/2 + 4/2)                  = 4 m²
  G planchers / niveau = 4 × 5                     = 20 kN
  poids propre de 2 poutres (h = max(4/8 ; 0,25) = 0,50 m) : 2 × (4/2) × 0,20 × 0,50 × 25 = 10 kN
  poids propre du poteau : 0,20² × 3 × 25          = 3 kN
  G  = 2 × (20 + 10 + 3)                           = 66 kN
  Q  = Q0 + Q1 = 4 × 1,5 + 4 × 1,5                 = 12 kN
  Nu = 1,35 × 66 + 1,5 × 12                        = 107,1 kN
  Ns = 66 + 12                                     = 78 kN
  B  = 1,3 × 0,1071 / (0,7 × 25) = 79,56 cm²  → a = 20 cm (minimum)
  λ  = 3 / (0,20 / √12) = 51,96 > 50  → α = 0,6 × (50 / 51,96)² = 0,556
Semelle S_0_0 : A = √(107,1 / 150) = 0,845 m → 84,5 cm.
Poutre de rive PX_0_0 (largeur reprise 2 m, L = 4 m) :
  g = 5 × 2 + 0,20 × 0,50 × 25 = 12,5 kN/m ; q = 1,5 × 2 = 3 kN/m
  pu = 1,35 × 12,5 + 1,5 × 3 = 21,375 kN/m ; Mu = 21,375 × 4² / 8 = 42,75 kN·m
  µ  = 0,04275 / (0,20 × 0,45² × 14,1667) = 0,0745
  α  = 1,25 (1 − √(1 − 2µ)) ; z = 0,45 (1 − 0,4 α) ; As = Mu / (z × 434,78) = 2,27 cm²
Quantités du poteau P_0_0 (× 2 niveaux) : béton 0,20² × 3 × 2 = 0,24 m³,
acier estimé 0,24 × 100 kg/m³ = 24 kg.
"""
import json
import math
import shutil
import subprocess
import tempfile
import unittest

from rest_framework.test import APITestCase

from projets.models import ElementStructurel, Projet
from projets.tests_projets.utils import BAREME_TEST, authentifier

PDFTOTEXT = shutil.which("pdftotext")


def etape(fiche, nom):
    return next(t for t in fiche["trace"] if t["etape"] == nom)


def resultat(fiche, libelle):
    return next(r for r in fiche["resultats"] if r["libelle"] == libelle)


class NoteDeCalcul(APITestCase):
    def setUp(self):
        self.user, self.cabinet = authentifier(self, bareme=BAREME_TEST)
        self.projet = Projet.objects.create(
            nom="Villa référence", entreprise=self.cabinet, usage_batiment="habitation", nb_niveaux=2,
            hauteur_etage=3.0, contrainte_sol_kn_m2=150, nb_travees_x=2, nb_travees_y=2, portee_x=4.0, portee_y=4.0)
        self.assertEqual(self.client.post(f"/api/projets/{self.projet.id}/generer_trame/").status_code, 201)
        self.url = f"/api/projets/{self.projet.id}/note-calcul/"

    def note(self):
        r = self.client.get(self.url, {"format": "json"})
        self.assertEqual(r.status_code, 200, r.data)
        return r.data

    def fiche(self, note, identifiant):
        return next(f for g in note["groupes"] for f in g["elements"] if f["identifiant"] == identifiant)

    def test_cas_de_reference_poteau_recalcule_a_la_main(self):
        note_legacy = self.note()
        f = self.fiche(note_legacy, "P_0_0")
        note_v1 = self.client.get(
            f"/api/v1/projets/{self.projet.id}/note-calcul/", {"format": "json"},
        )
        self.assertEqual(note_v1.status_code, 200, note_v1.data)
        self.assertEqual(note_v1.data, note_legacy)
        s = (0 / 2 + 4 / 2) * (0 / 2 + 4 / 2)
        g = 2 * (s * 5 + 2 * (4 / 2) * 0.20 * 0.50 * 25 + 0.20 ** 2 * 3 * 25)
        q = s * 1.5 + s * 1.5
        nu, ns = 1.35 * g + 1.5 * q, g + q
        self.assertEqual((s, g, q), (4.0, 66.0, 12.0))
        self.assertAlmostEqual(etape(f, "Surface d'influence")["resultat"], s)
        self.assertAlmostEqual(etape(f, "G cumulée")["resultat"], g)
        self.assertAlmostEqual(etape(f, "Q cumulée")["resultat"], q)
        self.assertAlmostEqual(etape(f, "Effort ELU")["resultat"], round(nu, 2))
        self.assertAlmostEqual(etape(f, "Effort ELS")["resultat"], round(ns, 2))
        self.assertEqual(etape(f, "Effort ELU")["calcul"], "1.35 × 66.0 + 1.5 × 12.0")
        self.assertIn("79.6 cm²", etape(f, "Section du poteau")["calcul"])
        lam = 3.0 / (0.20 / math.sqrt(12))
        self.assertAlmostEqual(etape(f, "Flambement")["resultat"], round(0.6 * (50 / lam) ** 2, 3))
        self.assertIn("0,6 (50/λ)²", etape(f, "Flambement")["formule"])  # branche réellement appliquée
        self.assertEqual(resultat(f, "Côté a")["valeur"], 20)
        self.assertEqual(resultat(f, "Effort ultime Nu")["origine"], "calculé")
        q_ = f["quantites"]
        self.assertAlmostEqual(q_["beton_m3"], 0.20 ** 2 * 3 * 2)
        self.assertAlmostEqual(q_["acier_kg"], 0.20 ** 2 * 3 * 2 * 100)
        self.assertEqual(q_["origine_acier"], "estimé")

    def test_cas_de_reference_semelle_et_poutre(self):
        note = self.note()
        s = self.fiche(note, "S_0_0")
        self.assertAlmostEqual(etape(s, "Côté théorique")["resultat"], round(math.sqrt(107.1 / 150) * 100, 1))
        self.assertEqual(s["quantites"]["origine_acier"], "calculé")
        p = self.fiche(note, "PX_0_0")
        g_lin, q_lin = 5 * 2 + 0.20 * 0.50 * 25, 1.5 * 2
        pu = 1.35 * g_lin + 1.5 * q_lin
        mu = pu * 4 ** 2 / 8
        mu_red = (mu / 1000) / (0.20 * 0.45 ** 2 * (0.85 * 25 / 1.5))
        alpha = 1.25 * (1 - math.sqrt(1 - 2 * mu_red))
        z = 0.45 * (1 - 0.4 * alpha)
        as_cm2 = (mu / 1000) / (z * 500 / 1.15) * 1e4
        self.assertAlmostEqual(etape(p, "Charge ELU")["resultat"], round(pu, 2))
        self.assertAlmostEqual(etape(p, "Moment ELU")["resultat"], round(mu, 2))
        self.assertAlmostEqual(etape(p, "Moment réduit")["resultat"], round(mu_red, 4))
        self.assertAlmostEqual(etape(p, "Acier tendu")["resultat"], round(as_cm2, 2))
        self.assertIn("14.17 MPa", etape(p, "Moment réduit")["calcul"])  # valeurs écrites dans la formule

    def test_origines_des_donnees(self):
        note = self.note()
        d = {x["libelle"]: x for x in note["donnees_entree"]}
        self.assertEqual(d["Charge permanente des planchers G"]["origine"], "estimé")
        self.assertEqual(d["Charge d'exploitation Q"]["origine"], "estimé")
        self.assertEqual(d["Contrainte admissible du sol"]["origine"], "saisi")
        self.assertEqual(d["Hauteur d'étage"]["origine"], "saisi")
        m = {x["libelle"]: x for x in note["materiaux"]}
        self.assertEqual((m["Résistance du béton fc28"]["valeur"], m["Résistance du béton fc28"]["origine"]),
                         (25.0, "estimé"))
        self.assertEqual(m["Limite élastique de l'acier fe"]["valeur"], 500.0)
        self.assertEqual(note["combinaisons"][0], "ELU (état limite ultime) : 1,35 G + 1,5 Q")
        self.assertEqual(note["projet"]["source_structure"], "Trame régulière saisie (travées et portées).")

    def test_valeur_modifiee_a_la_validation_est_saisie(self):
        el = self.projet.elements.get(identifiant="P_0_0")
        r = self.client.post(f"/api/elements/{el.id}/valider/",
                             {"resultat_valide": {**el.resultat_calcul, "cote_cm": 25}}, format="json")
        self.assertIn(r.status_code, (200, 201), r.data)
        f = self.fiche(self.note(), "P_0_0")
        cote = resultat(f, "Côté a")
        self.assertEqual((cote["valeur"], cote["origine"]), (25, "saisi"))
        self.assertIn("moteur : 20", cote["detail"])
        self.assertAlmostEqual(f["quantites"]["beton_m3"], 0.25 ** 2 * 3 * 2)

    def test_entete_statut_version_mention_et_pas_d_ia(self):
        note = self.note()
        self.assertTrue(note["statut"]["provisoire"])
        self.assertEqual(note["statut"]["elements"], 30)
        self.assertTrue(note["edition"]["version_moteur"].startswith("2026."))
        self.assertEqual(note["edition"]["norme"], "BAEL 91 modifié 99")
        self.assertIn("seul la responsabilité", note["mention"])
        texte = json.dumps(note, ensure_ascii=False)
        for marque in ("GEMINI", "MOCK", "explication"):
            self.assertNotIn(marque, texte)

    @unittest.skipUnless(PDFTOTEXT, "pdftotext indisponible")
    def test_pdf_reprend_les_chiffres(self):
        r = self.client.get(self.url)
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r["Content-Type"], "application/pdf")
        self.assertIn("Note_de_calcul_", r["Content-Disposition"])
        with tempfile.NamedTemporaryFile(suffix=".pdf") as f:
            f.write(r.content)
            f.flush()
            t = subprocess.run([PDFTOTEXT, f.name, "-"], capture_output=True, text=True).stdout
        t = " ".join(t.split())
        for attendu in ("NOTE DE CALCUL", "Villa référence", "BAEL 91 modifié 99", "107,1 kN", "42,75 kN·m",
                        "0,0745", "1,35 × 66,0 + 1,5 × 12,0", "PROVISOIRE", "seul responsable de l'ouvrage",
                        "VÉRIFIÉ PAR"):
            self.assertIn(attendu, t)

    def test_refus_et_droits(self):
        vide = Projet.objects.create(nom="Vide", entreprise=self.cabinet, usage_batiment="habitation")
        r = self.client.get(f"/api/projets/{vide.id}/note-calcul/")
        self.assertEqual(r.status_code, 400)
        self.assertIn("Aucun élément", r.data["erreur"])
        self.projet.hauteur_etage = None
        self.projet.save()
        r = self.client.get(self.url)
        self.assertEqual(r.status_code, 400)
        self.assertTrue(r.data["champs_manquants"])
        authentifier(self, nom_cabinet="Concurrent")
        self.assertEqual(self.client.get(self.url).status_code, 404)
        self.client.force_authenticate(user=None)
        self.assertEqual(self.client.get(self.url).status_code, 401)
        self.assertTrue(ElementStructurel.objects.filter(projet=self.projet).exists())
