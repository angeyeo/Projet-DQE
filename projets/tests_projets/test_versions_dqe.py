"""Historique et comparaison des versions du DQE (issue #82).

CAS DE RÉFÉRENCE (calculé à la main, prix DE TEST) :
  v1 : Porte 3 u × 85 000 = 255 000 ; Peinture 40 m² × 2 500 = 100 000  -> total 355 000
  v2 : Porte 4 u × 90 000 = 360 000 (quantité ET prix changent) ;
       Peinture supprimée ; Enduit 10 m² × 3 000 = 30 000 ajouté          -> total 390 000
  Porte : ΔM = 360 000 − 255 000 = 105 000
          effet quantité = (4 − 3) × 85 000 = 85 000
          effet prix     = 4 × (90 000 − 85 000) = 20 000   (85 000 + 20 000 = 105 000, arrondi 0)
  Total : Δ = 390 000 − 355 000 = 35 000
        = 85 000 (quantité) + 20 000 (prix) + 30 000 (ajouté) − 100 000 (supprimé) + 0 (arrondi)
"""
from rest_framework.test import APITestCase

from projets.models import PosteComplementaire, Profil, Projet, VersionDQE
from projets.services.versions_dqe import comparer
from projets.tests_projets.utils import authentifier


def poste(projet, designation, unite, quantite, pu, lot="lot_09_menuiserie_bois"):
    return PosteComplementaire.objects.create(projet=projet, lot=lot, mode="simple", designation=designation,
                                              unite=unite, quantite=quantite, prix_unitaire=pu)


class Versions(APITestCase):
    def setUp(self):
        self.user, self.cabinet = authentifier(self, role=Profil.Role.INGENIEUR)
        self.projet = Projet.objects.create(nom="Villa", entreprise=self.cabinet)
        self.url = f"/api/projets/{self.projet.id}/"

    def generer(self):
        r = self.client.post(f"{self.url}generer-dqe/", format="json")
        self.assertEqual(r.status_code, 200, r.data)
        return r.data

    def test_nouvelle_version_seulement_si_le_contenu_change(self):
        porte = poste(self.projet, "Porte", "u", 3, 85000)
        poste(self.projet, "Peinture", "m²", 40, 2500, lot="lot_12_peinture")
        d = self.generer()
        self.assertEqual(d["version"]["numero"], 1)
        self.assertEqual(self.generer()["version"]["numero"], 1)       # inchangé : pas de doublon
        self.assertEqual(VersionDQE.objects.count(), 1)
        porte.quantite = 4
        porte.save()
        self.assertEqual(self.generer()["version"]["numero"], 2)
        liste = self.client.get(f"{self.url}versions-dqe/").data
        self.assertEqual([v["numero"] for v in liste], [2, 1])
        liste_v1 = self.client.get(f"/api/v1/projets/{self.projet.id}/versions-dqe/")
        self.assertEqual(liste_v1.status_code, 200, liste_v1.data)
        self.assertEqual(liste_v1.data, liste)
        self.assertEqual(liste[1]["total_general"], 355000)
        self.assertEqual(liste[1]["auteur"], self.user.get_username())

    def test_comparaison_cas_de_reference(self):
        porte = poste(self.projet, "Porte", "u", 3, 85000)
        peinture = poste(self.projet, "Peinture", "m²", 40, 2500, lot="lot_12_peinture")
        self.generer()
        porte.quantite, porte.prix_unitaire = 4, 90000
        porte.save()
        peinture.delete()
        poste(self.projet, "Enduit", "m²", 10, 3000, lot="lot_12_peinture")
        self.generer()

        c = self.client.get(f"{self.url}versions-dqe/comparer/", {"de": 1, "a": 2}).data
        c_v1 = self.client.get(
            f"/api/v1/projets/{self.projet.id}/versions-dqe/comparer/", {"de": 1, "a": 2},
        )
        self.assertEqual(c_v1.status_code, 200, c_v1.data)
        self.assertEqual(c_v1.data, c)
        self.assertEqual((c["total_avant"], c["total_apres"], c["ecart"]), (355000, 390000, 35000))
        p = {x["designation"]: x for x in c["postes"]}
        self.assertEqual(p["Porte"]["statut"], "modifie")
        self.assertEqual((p["Porte"]["ecart"], p["Porte"]["effet_quantite"], p["Porte"]["effet_prix"],
                          p["Porte"]["arrondi"]), (105000, 85000, 20000, 0))
        self.assertEqual((p["Peinture"]["statut"], p["Peinture"]["ecart"]), ("supprime", -100000))
        self.assertEqual((p["Enduit"]["statut"], p["Enduit"]["ecart"]), ("ajoute", 30000))
        self.assertEqual(c["effet_quantite"] + c["effet_prix"] + c["ecart_postes_ajoutes"]
                         + c["ecart_postes_supprimes"] + c["arrondi"], c["ecart"])
        self.assertEqual(c["compte"], {"ajoute": 1, "supprime": 1, "modifie": 1, "identique": 0})

    def test_version_figee(self):
        poste(self.projet, "Porte", "u", 3, 85000)
        self.generer()
        v = VersionDQE.objects.get()
        v.total_general = 1
        with self.assertRaises(ValueError):
            v.save()
        r = self.client.get(f"{self.url}versions-dqe/1/")
        self.assertEqual((r.status_code, r.data["total_general"]), (200, 255000))
        v1 = self.client.get(f"/api/v1/projets/{self.projet.id}/versions-dqe/1/")
        self.assertEqual(v1.status_code, 200, v1.data)
        self.assertEqual(v1.data, r.data)
        # Réédition PDF d'une version : rien n'est recalculé ni créé.
        r = self.client.get(f"{self.url}versions-dqe/1/", {"export": "pdf"})
        self.assertEqual(r.status_code, 200)
        self.assertIn("_v1.pdf", r["Content-Disposition"])
        self.assertEqual(VersionDQE.objects.count(), 1)

    def test_erreurs_et_isolation(self):
        poste(self.projet, "Porte", "u", 3, 85000)
        self.generer()
        self.assertEqual(self.client.get(f"{self.url}versions-dqe/9/").status_code, 404)
        self.assertEqual(self.client.get(f"{self.url}versions-dqe/comparer/", {"de": 1}).status_code, 400)
        self.assertEqual(self.client.get(f"{self.url}versions-dqe/comparer/", {"de": 1, "a": 5}).status_code, 404)
        authentifier(self, nom_cabinet="Concurrent")
        self.assertEqual(self.client.get(f"{self.url}versions-dqe/").status_code, 404)
        self.assertEqual(self.client.get(f"{self.url}versions-dqe/1/").status_code, 404)


class Arrondi(APITestCase):
    def test_reliquat_d_arrondi_isole(self):
        """q × pu arrondi : 0,333 × 1 001 = 333,333 -> 333 ; 0,334 × 1 001 = 334,334 -> 334.
        ΔM = 1 ; effet quantité = round(0,001 × 1 001) = 1 ; effet prix = 0 ; arrondi = 0."""
        avant = {"total_general": 333, "lignes": [{"lot": "l", "designation": "x", "unite": "m³",
                                                   "quantite": 0.333, "montant": 333}]}
        apres = {"total_general": 334, "lignes": [{"lot": "l", "designation": "x", "unite": "m³",
                                                   "quantite": 0.334, "montant": 334}]}
        c = comparer(avant, apres)
        p = c["postes"][0]
        self.assertEqual(p["ecart"], 1)
        self.assertEqual(p["effet_quantite"] + p["effet_prix"] + p["arrondi"], p["ecart"])
