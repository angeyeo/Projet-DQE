"""
Matrice de sécurité : chaque endpoint métier × chaque profil.

Profils : anonyme, technicien / ingénieur / admin du cabinet A (propriétaire
des objets), ingénieur du cabinet B (autre cabinet), membre staff (équipe
interne, rattaché à un troisième cabinet).

Politique attendue :
  - anonyme                    -> 401 partout ;
  - autre cabinet (B, staff)   -> 404 sur tout objet du cabinet A (l'objet
                                  « n'existe pas » pour lui : aucune fuite) ;
  - validation / déverrouillage / suppression de projet / plan de fondation
                               -> ingénieur ou admin (technicien : 403) ;
  - paramètres du cabinet (écriture), équipe -> admin (sinon 403) ;
  - analytics staff            -> is_staff uniquement (sinon 403).
"""

from django.contrib.auth.models import User
from rest_framework.test import APITestCase

from projets.models import ElementStructurel, Profil, Projet, PosteComplementaire

from .utils import BAREME_TEST, creer_cabinet, creer_membre

ANON, TECH, ING, ADM, AUTRE, STAFF = "anonyme", "technicien A", "ingénieur A", "admin A", "ingénieur B", "staff"
PROFILS = (ANON, TECH, ING, ADM, AUTRE, STAFF)
OK = {200, 201, 204, 400, 409}  # autorisé (400/409 = refus MÉTIER, pas d'accès)


class MatriceSecurite(APITestCase):
    @classmethod
    def setUpTestData(cls):
        cls.a = creer_cabinet("A", BAREME_TEST)
        cls.b = creer_cabinet("B", BAREME_TEST)
        cls.s = creer_cabinet("S")
        cls.users = {
            TECH: creer_membre(cls.a, "tech_a", Profil.Role.TECHNICIEN),
            ING: creer_membre(cls.a, "ing_a", Profil.Role.INGENIEUR),
            ADM: creer_membre(cls.a, "adm_a", Profil.Role.ADMIN),
            AUTRE: creer_membre(cls.b, "ing_b", Profil.Role.INGENIEUR),
            STAFF: creer_membre(cls.s, "staff", Profil.Role.ADMIN, is_staff=True),
        }

    def setUp(self):
        self.projet = Projet.objects.create(
            nom="A1", entreprise=self.a, usage_batiment="habitation", nb_niveaux=1, hauteur_etage=3,
            nb_travees_x=1, nb_travees_y=1, portee_x=4, portee_y=4)
        self.el = ElementStructurel.objects.create(
            projet=self.projet, identifiant="P1", type_element="poteau", charge_calculee=200, hauteur_poteau=3,
            resultat_calcul={"cote_cm": 20})
        self.poste = PosteComplementaire.objects.create(
            projet=self.projet, lot=PosteComplementaire.Lot.GENERALITES, mode="simple",
            designation="Installation", unite="forfait", quantite=1, prix_unitaire=1000)

    def appeler(self, profil, methode, url, data=None):
        self.client.force_authenticate(None if profil == ANON else self.users[profil])
        return getattr(self.client, methode)(url, data or {}, format="json").status_code

    def verifier(self, methode, url_fn, attendu, data=None):
        """attendu : {profil: ensemble de codes acceptés}."""
        ecarts = []
        for profil in PROFILS:
            self.setUp_si_supprime()
            code = self.appeler(profil, methode, url_fn(), data)
            if code not in attendu[profil]:
                ecarts.append(f"{profil}: {code} (attendu {sorted(attendu[profil])})")
        self.assertEqual(ecarts, [], f"{methode.upper()} {url_fn()}")

    def setUp_si_supprime(self):
        if not Projet.objects.filter(pk=self.projet.pk).exists() or \
                not ElementStructurel.objects.filter(pk=self.el.pk).exists():
            Projet.objects.filter(pk=self.projet.pk).delete()
            self.setUp()

    # -- politiques ---------------------------------------------------------
    MEMBRES_A = {ANON: {401}, TECH: OK, ING: OK, ADM: OK, AUTRE: {404}, STAFF: {404}}
    INGENIEURS_A = {ANON: {401}, TECH: {403}, ING: OK, ADM: OK, AUTRE: {403, 404}, STAFF: {403, 404}}

    def test_projet_lecture_et_ecriture(self):
        p = lambda: f"/api/projets/{self.projet.pk}/"  # noqa: E731
        for m, d in (("get", None), ("patch", {"nom": "x"})):
            self.verifier(m, p, self.MEMBRES_A, d)
        for action in ("generer_trame/", "plan_fondation/", "analyse-coherence/", "generer-dqe/", "chainage_suggere/"):
            meth = "post" if action in ("generer_trame/", "generer-dqe/") else "get"
            self.verifier(meth, lambda a=action: f"/api/projets/{self.projet.pk}/{a}", self.MEMBRES_A)
        self.verifier("post", lambda: f"/api/projets/{self.projet.pk}/variantes/", self.MEMBRES_A,
                      {"variantes": [{"modifications": {"contrainte_sol_kn_m2": 100}}]})
        self.verifier("get", lambda: f"/api/analytics/projets/{self.projet.pk}/", self.MEMBRES_A)

    def test_actions_reservees_ingenieur(self):
        self.verifier("post", lambda: f"/api/projets/{self.projet.pk}/valider_plan_fondation/", self.INGENIEURS_A)
        self.verifier("post", lambda: f"/api/elements/{self.el.pk}/valider/", self.INGENIEURS_A)
        self.verifier("post", lambda: f"/api/elements/{self.el.pk}/deverrouiller/", self.INGENIEURS_A)
        self.verifier("delete", lambda: f"/api/projets/{self.projet.pk}/", self.INGENIEURS_A)

    def test_elements_et_postes(self):
        self.verifier("get", lambda: f"/api/elements/{self.el.pk}/", self.MEMBRES_A)
        self.verifier("post", lambda: f"/api/elements/{self.el.pk}/calculer/", self.MEMBRES_A)
        self.verifier("post", lambda: f"/api/elements/{self.el.pk}/expliquer-coherence/", self.MEMBRES_A)
        self.verifier("get", lambda: f"/api/postes-complementaires/{self.poste.pk}/", self.MEMBRES_A)
        # Création d'un élément dans le projet d'un AUTRE cabinet : refusée (400 côté B : projet invalide)
        self.client.force_authenticate(self.users[AUTRE])
        r = self.client.post("/api/elements/", {"projet": self.projet.pk, "identifiant": "X", "type_element": "poteau"},
                             format="json")
        self.assertIn(r.status_code, (400, 403, 404))
        self.assertFalse(ElementStructurel.objects.filter(identifiant="X").exists())

    def test_listes_filtrees_par_cabinet(self):
        for url in ("/api/projets/", "/api/elements/", "/api/postes-complementaires/"):
            self.client.force_authenticate(self.users[AUTRE])
            r = self.client.get(url)
            self.assertEqual(r.status_code, 200)
            donnees = r.data["results"] if isinstance(r.data, dict) else r.data
            self.assertEqual(donnees, [], url)

    def test_parametres_cabinet_et_equipe(self):
        lecture = {ANON: {401}, TECH: {200}, ING: {200}, ADM: {200}, AUTRE: {200}, STAFF: {200}}
        self.verifier("get", lambda: "/api/entreprise/", lecture)
        ecriture = {ANON: {401}, TECH: {403}, ING: {403}, ADM: {200}, AUTRE: {403}, STAFF: {200}}
        self.verifier("patch", lambda: "/api/entreprise/", ecriture, {"telephone": "01"})
        # Chacun ne modifie QUE son propre cabinet
        self.a.refresh_from_db()
        self.assertEqual(self.a.telephone, "01")
        self.assertEqual(self.b.telephone, "")
        equipe = {ANON: {401}, TECH: {403}, ING: {403}, ADM: {200}, AUTRE: {403}, STAFF: {200}}
        self.verifier("get", lambda: "/api/auth/membres/", equipe)
        cible = lambda: f"/api/auth/membres/{self.users[TECH].pk}/desactiver/"  # noqa: E731
        desact = {ANON: {401}, TECH: {403}, ING: {403}, ADM: {200}, AUTRE: {403, 404}, STAFF: {403, 404}}
        self.verifier("post", cible, desact)

    def test_analytics(self):
        cab = {ANON: {401}, TECH: {200}, ING: {200}, ADM: {200}, AUTRE: {200}, STAFF: {200}}
        self.verifier("get", lambda: "/api/analytics/cabinet/", cab)
        staff = {ANON: {401}, TECH: {403}, ING: {403}, ADM: {403}, AUTRE: {403}, STAFF: {200}}
        self.verifier("get", lambda: "/api/analytics/staff/", staff)

    def test_utilisateur_sans_cabinet(self):
        orphelin = User.objects.create_user("orphelin", password="MotDePasse-Test-2026!")
        self.client.force_authenticate(orphelin)
        for url in ("/api/projets/", f"/api/projets/{self.projet.pk}/", "/api/entreprise/", "/api/analytics/cabinet/"):
            self.assertIn(self.client.get(url).status_code, (403, 404), url)
