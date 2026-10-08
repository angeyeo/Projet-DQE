from django.conf import settings
from django.db import models

from moteur_calcul.constantes import CHARGES_EXPLOITATION


# Nomenclature canonique des usages : les clés de
# moteur_calcul.constantes.CHARGES_EXPLOITATION (source de vérité unique,
# partagée par le moteur, l'API, le frontend via /api/referentiel/ et les
# tests). Avant : le frontend envoyait "commercial" alors que le moteur
# attend "commerce" -- la charge d'exploitation retombait silencieusement
# sur celle de l'habitation.
USAGES_BATIMENT = [(cle, cle.replace("_", " ").capitalize()) for cle in CHARGES_EXPLOITATION]


class Entreprise(models.Model):
    """
    DÉPRÉCIÉ -- NE PLUS UTILISER.

    Le cabinet canonique est EntrepriseParametres : c'est lui que
    référencent Projet.entreprise et Profil.entreprise depuis la
    migration 0015. Ce modèle n'est plus référencé par aucune clé
    étrangère ; il est conservé uniquement pour ne pas supprimer sa table
    (et les lignes éventuellement présentes en production) sans
    validation explicite. Sa suppression fera l'objet d'une migration
    dédiée après vérification du contenu de la table en production.
    """

    nom = models.CharField(max_length=255)
    code_cabinet = models.CharField(max_length=50, blank=True, null=True, unique=True)
    adresse = models.TextField(blank=True, null=True)
    telephone = models.CharField(max_length=50, blank=True, null=True)
    email = models.EmailField(blank=True, null=True)
    date_creation = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.nom
    

class Projet(models.Model):
    nom = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    # Plus de valeur par défaut inventée ("habitation", 1 niveau, 4 m de
    # portée, 3 m d'étage) : une donnée non saisie reste NULL/vide et les
    # services qui en ont besoin (generer_trame, importer_plan) renvoient
    # une erreur explicite listant ce qui manque.
    usage_batiment = models.CharField(max_length=100, blank=True, choices=USAGES_BATIMENT)
    nb_niveaux = models.PositiveIntegerField(null=True, blank=True)

    # Numéro de devis affiché sur les exports DQE (ex. "0017-2026").
    # Laissé vide, on retombe sur "DQE-PROJET-<id>" à l'export.
    numero_devis = models.CharField(max_length=50, blank=True)

    # Extension Trame Structurelle (Jour 1)
    nb_travees_x = models.PositiveIntegerField(null=True, blank=True)
    nb_travees_y = models.PositiveIntegerField(null=True, blank=True)
    portee_x = models.FloatField(null=True, blank=True, help_text="Portée en mètres, direction X")
    portee_y = models.FloatField(null=True, blank=True, help_text="Portée en mètres, direction Y")
    hauteur_etage = models.FloatField(null=True, blank=True, help_text="Hauteur d'étage en mètres")
    charge_exploitation = models.FloatField(
        null=True,
        blank=True,
        help_text="kN/m² -- si vide, déduit de usage_batiment (constantes.CHARGES_EXPLOITATION)",
    )
    # Contrainte admissible du sol, en kN/m² (1 bar = 100 kN/m²), issue
    # de l'étude géotechnique. Vide = hypothèse par défaut du moteur
    # (CONTRAINTE_SOL_DEFAUT), signalée par "hypothese_sol": true dans
    # chaque résultat de semelle.
    contrainte_sol_kn_m2 = models.FloatField(
        null=True,
        blank=True,
        help_text="kN/m² (1 bar = 100 kN/m²) -- vide = hypothèse par défaut signalée",
    )

    # --- Hypothèses de calcul explicites (moteur_calcul/hypotheses.py) ---
    # G des planchers : composition (prioritaire) > valeur saisie > forfait
    # du moteur signalé comme HYPOTHÈSE. Jamais de valeur silencieuse.
    charge_permanente_kn_m2 = models.FloatField(
        null=True, blank=True,
        help_text="G des planchers en kN/m² (hors poids propre poutres/poteaux si ajouté séparément)",
    )
    couches_permanentes = models.JSONField(
        default=list, blank=True,
        help_text="Composition du plancher : [{designation, type | poids_surfacique_kn_m2 | epaisseur_m + poids_volumique_kn_m3}]",
    )
    class MethodeSemelles(models.TextChoices):
        ELU = "ELU", "ELU : A² ≥ Nu / σsol (prudent)"
        ELS = "ELS", "ELS : A² ≥ Ns / σsol (usage courant)"

    methode_semelles = models.CharField(
        max_length=3, choices=MethodeSemelles.choices, default=MethodeSemelles.ELU,
        help_text="Choix métier explicite ; ELU = méthode validée par le technicien BTP (07/10/2026)",
    )
    # Défaut True pour les NOUVEAUX projets (le forfait G = 5 kN/m² ne
    # couvre pas poutres et poteaux -- technicien BTP, 07/10/2026). Les
    # projets existants gardent leur valeur enregistrée : les basculer est
    # une décision de production (voir audit_donnees_production).
    inclure_poids_propre_ossature = models.BooleanField(
        default=True,
        help_text="Ajouter le poids propre des poutres, poteaux et semelles à G (False = G l'inclut déjà)",
    )

    # Validation du plan de fondation (Jour 3 pré-intégré)
    plan_fondation_valide = models.BooleanField(default=False)

    # Import de plan (Phase A/B -- voir ProjetViewSet.importer_plan) : trace
    # le fichier IFC déposé par l'utilisateur. Conservé pour audit et pour
    # que la confirmation (Phase B) puisse relire les positions réelles
    # sans redemander le fichier au technicien.
    fichier_import_origine = models.FileField(
        upload_to="imports_ifc/", null=True, blank=True
    )

    date_creation = models.DateTimeField(auto_now_add=True)
    date_modification = models.DateTimeField(auto_now=True)

    # Rattachement multi-cabinet (sprint Permissions & Comptes). Nullable
    # tant que la migration de données (0014_...) n'a pas rattaché les
    # projets déjà existants à l'entreprise "legacy". Ne pas rendre
    # obligatoire avant que cette migration ait tourné en production.
    entreprise = models.ForeignKey(
        "EntrepriseParametres",
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="projets",
        help_text="Cabinet (entreprise) propriétaire de ce projet.",
    )
    cree_par = models.ForeignKey(
        "auth.User",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="projets_crees",
    )

    def __str__(self):
        return self.nom


class ElementStructurel(models.Model):
    class TypeElement(models.TextChoices):
        POTEAU = "poteau", "Poteau"
        POUTRE = "poutre", "Poutre"
        SEMELLE = "semelle", "Semelle Isolée"
        DALLE = "dalle", "Dalle Pleine"
        SEMELLE_FILANTE = "semelle_filante", "Semelle Filante"
        # AJOUTÉ (Phase C) : longrine -- même physique qu'une poutre
        # (flexion simple BAEL), juste à un autre niveau (liaison entre
        # semelles) -- pas de nouvelle formule, réutilise dimensionner_poutre().
        LONGRINE = "longrine", "Longrine"
        # AJOUTÉ (Phase C) : chaînage promu en élément identifié (repère
        # CH1 individuel, ligne DQE dédiée) -- avant, uniquement un poste
        # ratio global (voir postes_ratio.calculer_poste_ratio("chainage", ...),
        # qui reste disponible pour un usage en lot forfaitaire non identifié).
        CHAINAGE = "chainage", "Chaînage"

    class Statut(models.TextChoices):
        PROPOSE = "propose", "Proposé"
        MODIFIE = "modifie", "Modifié"
        VALIDE = "valide", "Validé"

    class Position(models.TextChoices):
        INFRASTRUCTURE = "infrastructure", "Infrastructure"
        SUPERSTRUCTURE = "superstructure", "Superstructure"

    projet = models.ForeignKey(
        Projet, on_delete=models.CASCADE, related_name="elements"
    )
    identifiant = models.CharField(max_length=50)  # ex: "P1", "N1_S1"
    type_element = models.CharField(max_length=20, choices=TypeElement.choices)
    statut = models.CharField(
        max_length=10, choices=Statut.choices, default=Statut.PROPOSE
    )

    # Position relative & coordonnées réelles sur la trame
    position = models.CharField(
        max_length=20, choices=Position.choices, null=True, blank=True
    )
    position_x = models.FloatField(
        null=True, blank=True, help_text="mètres, origine (0,0) = coin de la trame"
    )
    position_y = models.FloatField(null=True, blank=True, help_text="mètres")

    # Lien Semelle -> Poteau supporté
    poteau_associe = models.ForeignKey(
        "self",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="semelles_associees",
    )

    # Extrémités d'un ouvrage linéaire (poutre, longrine, chaînage
    # identifié) -- Phase C de la feuille de route "Import plan
    # automatique". Sans ça, une poutre n'était connue que par son
    # centre (position_x/y) et sa portée : impossible de tracer le bon
    # segment dans le plan de coffrage DXF (voir
    # projets/services/plan_fondation.py, generer_plan_fondation_dxf).
    # Renseignés par ProjetViewSet.generer_trame et .importer_plan ;
    # None pour un poteau/une semelle (non concernés) ou un ouvrage créé
    # avant ce champ (donnée historique, tracé alors omis du DXF plutôt
    # que de planter -- voir _ouvrages_lineaires_pour_dxf).
    poteau_origine = models.ForeignKey(
        "self",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="ouvrages_origine",
    )
    poteau_destination = models.ForeignKey(
        "self",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="ouvrages_destination",
    )

    # Inputs techniques de dimensionnement
    hauteur_poteau = models.FloatField(null=True, blank=True)
    charge_calculee = models.FloatField(null=True, blank=True)
    # Effort de service ELS (G + Q, kN) -- requis pour les semelles à l'ELS.
    charge_service = models.FloatField(null=True, blank=True, help_text="kN, ELS G + Q")
    # Nombre d'ouvrages identiques représentés par cet élément (ex. le même
    # poteau ou la même poutre répété à chaque niveau). Le DQE multiplie les
    # quantités unitaires par ce nombre et l'affiche dans la formule.
    nombre_identiques = models.PositiveIntegerField(default=1)
    portee = models.FloatField(null=True, blank=True)
    charge_lineaire = models.FloatField(null=True, blank=True)
    # Contrainte admissible du sol en kN/m² (unité attendue par
    # dimensionner_semelle). Avant : les vues écrivaient 0.2 (des MPa),
    # soit une valeur 1000 fois trop faible pour le moteur.
    taux_travail_sol = models.FloatField(null=True, blank=True, help_text="kN/m²")
    longueur_m = models.FloatField("Longueur (m)", null=True, blank=True)
    surface_m2 = models.FloatField("Surface (m²)", null=True, blank=True)

    # AJOUTÉ (Module 1 -- descente de charges complète, voir
    # projets/services/calculations.py: degression_renseignee() et
    # calculer_element()) : trame autour d'un POTEAU, nécessaire pour
    # déclencher calculer_descente_charges_complete() (moteur_calcul/
    # formules/descente_charges.py) au lieu de la charge_calculee brute
    # historique. Sans objet pour les autres types d'éléments -- restent
    # à None, jamais lus par calculer_element() en dehors du cas POTEAU.
    portee_gauche = models.FloatField(
        null=True, blank=True, help_text="mètres -- portée de la travée à gauche de ce poteau"
    )
    portee_droite = models.FloatField(
        null=True, blank=True, help_text="mètres -- portée de la travée à droite de ce poteau"
    )
    portee_avant = models.FloatField(
        null=True, blank=True, help_text="mètres -- portée de la travée à l'avant de ce poteau"
    )
    portee_arriere = models.FloatField(
        null=True, blank=True, help_text="mètres -- portée de la travée à l'arrière de ce poteau"
    )
    epaisseur_dalle = models.FloatField(
        null=True, blank=True,
        help_text="mètres -- ignoré si des CoucheCharge sont liées à cet élément (Module 2)",
    )
    nb_niveaux_charges = models.PositiveIntegerField(
        null=True, blank=True,
        help_text="Nombre de niveaux (toiture comprise) dont la charge descend sur ce poteau",
    )
    avec_degression = models.BooleanField(
        default=True,
        help_text="Applique la loi de dégression NF P06-001 sur les charges d'exploitation cumulées",
    )
    usage_toiture = models.CharField(
        max_length=100, null=True, blank=True,
        help_text="Usage du niveau le plus haut si différent des étages courants "
                   "(ex. 'toiture_terrasse') -- vide = même usage que le projet",
    )

    # Résultats stockés au format JSON
    resultat_calcul = models.JSONField(null=True, blank=True)
    resultat_valide = models.JSONField(null=True, blank=True)

    date_creation = models.DateTimeField(auto_now_add=True)
    date_modification = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.identifiant} ({self.get_type_element_display()})"

class CoucheCharge(models.Model):
    """Module 2 : Couches de charges permanentes composées (multi-couches)"""

    # AJOUTÉ (Module 1, câblage dégression) : rendu optionnel. Une
    # CoucheCharge liée à un `element` peut retrouver son projet via
    # element.projet -- exiger `projet` en plus était redondant et
    # empêchait de créer une couche uniquement avec `element` (cas
    # d'usage réel : composition du plancher d'un poteau précis, voir
    # projets/services/calculations.py: _couches_permanentes_pour_descente()).
    projet = models.ForeignKey(
        Projet, on_delete=models.CASCADE, related_name="couches_charges",
        null=True, blank=True,
    )
    element = models.ForeignKey(
        ElementStructurel,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="couches_charges",
    )
    designation = models.CharField(max_length=150)
    epaisseur_cm = models.FloatField(help_text="Épaisseur en cm")
    poids_volumique_kn_m3 = models.FloatField(help_text="Poids volumique en kN/m³")

    @property
    def poids_surfacique_kn_m2(self) -> float:
        return (self.epaisseur_cm / 100.0) * self.poids_volumique_kn_m3

    def __str__(self):
        return f"{self.designation} ({self.epaisseur_cm} cm)"


class PosteComplementaire(models.Model):
    """Remplace l'ancien PosteMainDoeuvre par la gestion par Lots BTP et Mode Simple/Ratio"""

    class Lot(models.TextChoices):
        GENERALITES = "lot_00_generalites", "Généralités"
        TERRASSEMENT = "lot_01_terrassement", "Terrassement"
        GROS_OEUVRE_INFRA = (
            "lot_02_gros_oeuvre_infrastructure",
            "Gros Œuvre - Infrastructure",
        )
        GROS_OEUVRE_SUPER = (
            "lot_02_gros_oeuvre_superstructure",
            "Gros Œuvre - Superstructure",
        )
        ETANCHEITE = "lot_03_etancheite", "Étanchéité"
        PLOMBERIE = "lot_04_plomberie", "Plomberie"
        ASSAINISSEMENT = "lot_05_assainissement", "Assainissement"
        ELECTRICITE = "lot_06_electricite", "Électricité"
        CHARPENTE = "lot_07_charpente", "Charpente"
        COUVERTURE = "lot_08_couverture", "Couverture"

    class Mode(models.TextChoices):
        SIMPLE = "simple", "Poste simple"
        RATIO = "ratio", "Poste à ratio"

    # Nomenclature canonique = clés de moteur_calcul.formules.postes_ratio
    # .TYPES_POSTES. Avant : "maconnerie_pleine"/"maconnerie_creuse" ici,
    # "maconnerie" dans le moteur -> aucun poste maçonnerie n'était
    # calculable (voir migration 0018).
    class TypePoste(models.TextChoices):
        MACONNERIE = "maconnerie", "Maçonnerie (agglos pleins en soubassement + creux en élévation)"
        ENDUIT = "enduit", "Enduit"
        CHAINAGE = "chainage", "Chaînage"
        RAIDISSEUR = "raidisseur", "Raidisseur"
        ACROTERE = "acrotere", "Acrotère"

    projet = models.ForeignKey(
        Projet, on_delete=models.CASCADE, related_name="postes_complementaires"
    )
    lot = models.CharField(max_length=50, choices=Lot.choices)
    mode = models.CharField(
        max_length=10, choices=Mode.choices, default=Mode.SIMPLE
    )
    designation = models.CharField(max_length=200, blank=True)
    unite = models.CharField(max_length=20, blank=True)
    quantite = models.FloatField(null=True, blank=True)
    prix_unitaire = models.FloatField(null=True, blank=True)
    type_poste = models.CharField(
        max_length=30, choices=TypePoste.choices, blank=True
    )
    geometrie = models.JSONField(null=True, blank=True)
    lignes_calculees = models.JSONField(null=True, blank=True)

    date_creation = models.DateTimeField(auto_now_add=True)
    date_modification = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.get_lot_display()} - {self.designation or self.type_poste}"


class EntrepriseParametres(models.Model):
    """
    Cabinet (entreprise) : en-tête personnalisable pour les exports DQE
    (PDF/Excel) -- logo et coordonnées -- ET tenant du système multi-
    cabinet (sprint Comptes & Permissions) : un Profil et des Projets
    peuvent être rattachés à chaque ligne.

    C'est LE modèle canonique du cabinet (tenant). L'ancien repli
    get_solo() (entreprise pk=1 partagée par tous les utilisateurs sans
    profil) a été supprimé : il mélangeait les données de cabinets
    différents.
    """

    logo = models.ImageField(upload_to="logos/", null=True, blank=True)
    nom = models.CharField(max_length=200, blank=True)
    siege_social = models.CharField(max_length=255, blank=True)
    telephone = models.CharField(max_length=100, blank=True)
    email = models.EmailField(blank=True)
    site_web = models.CharField(max_length=200, blank=True)
    rccm = models.CharField("N° R.C.C.M", max_length=100, blank=True)
    cc = models.CharField("CC N°", max_length=100, blank=True)
    cb = models.CharField("CB N°", max_length=100, blank=True)
    capital_social = models.CharField(max_length=100, blank=True)

    # Barème de prix unitaires propre à ce cabinet (FCFA), ex.
    # {"beton_m3": 95000, "acier_kg": 800}. C'est la SEULE source de prix
    # du DQE : une clé absente bloque la génération du DQE avec un message
    # explicite (plus de repli silencieux sur un barème par défaut). Le
    # barème de référence (dqe_calculator.PRIX_UNITAIRES_REFERENCE) peut
    # être proposé à l'admin comme point de départ, jamais appliqué à son
    # insu.
    prix_unitaires = models.JSONField(
        default=dict,
        blank=True,
        help_text=(
            "Barème de prix unitaires du cabinet (FCFA), ex. "
            '{"beton_m3": 95000, "acier_kg": 800}. Toute clé nécessaire au '
            "DQE et absente ici bloque la génération avec un message explicite."
        ),
    )

    # Traçabilité des prix : {clé: {"date", "auteur", "source"}} mise à jour
    # par le serveur à chaque changement de valeur (jamais par le client).
    prix_unitaires_meta = models.JSONField(default=dict, blank=True)

    class NaturePrix(models.TextChoices):
        VENTE_HT = "vente_ht", "Prix de vente HT (fourni-posé)"
        DEBOURSE_SEC = "debourse_sec", "Déboursé sec (coût de revient)"

    # Nature des prix du barème : décide si une marge s'applique. Défaut =
    # sémantique historique (prix de vente fourni-posé, aucune marge).
    nature_prix = models.CharField(max_length=20, choices=NaturePrix.choices, default=NaturePrix.VENTE_HT)
    taux_marge_pct = models.DecimalField(
        max_digits=5, decimal_places=2, null=True, blank=True,
        help_text="% appliqué au déboursé sec (frais généraux + bénéfice) -- seulement si nature = déboursé sec",
    )
    taux_tva_pct = models.DecimalField(
        max_digits=5, decimal_places=2, null=True, blank=True,
        help_text="% de TVA du cabinet -- vide = TTC non calculé (jamais de taux supposé)",
    )

    date_modification = models.DateTimeField(auto_now=True)

    def get_prix_unitaires(self) -> dict:
        """Barème de CE cabinet uniquement -- jamais complété en silence."""
        return dict(self.prix_unitaires or {})

    def __str__(self):
        return self.nom or "Paramètres entreprise"


class JournalAppelIA(models.Model):
    """
    Journal de traçabilité des appels aux services IA (Gemini, Mock, Fallback Local).
    """

    class Source(models.TextChoices):
        MOCK = "MOCK", "Mock Client"
        GEMINI = "GEMINI", "Gemini AI"
        FALLBACK_LOCAL = "FALLBACK_LOCAL", "Fallback Local"

    utilisateur = models.ForeignKey(
        "auth.User",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="appels_ia",
    )
    endpoint = models.CharField(max_length=255)
    source = models.CharField(max_length=30, choices=Source.choices)
    duree_ms = models.IntegerField(null=True, blank=True)
    date_appel = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Journal d'appel IA"
        verbose_name_plural = "Journaux d'appels IA"
        ordering = ["-date_appel"]

    def __str__(self):
        user_str = self.utilisateur.username if self.utilisateur else "Anonyme"
        return f"[{self.source}] {self.endpoint} par {user_str} le {self.date_appel:%Y-%m-%d %H:%M:%S}"


class Profil(models.Model):
    """
    Extension de auth.User (sprint Permissions & Comptes) : rattache un
    utilisateur à une entreprise (cabinet) et lui donne un rôle. Le
    verrou d'ingénieur (Étape 3 validation) et l'accès à la gestion des
    comptes du cabinet dépendent de ce rôle -- voir la matrice de
    permissions du sprint (technicien / ingenieur / admin).
    """

    class Role(models.TextChoices):
        TECHNICIEN = "technicien", "Technicien"
        INGENIEUR = "ingenieur", "Ingénieur"
        ADMIN = "admin", "Admin (Gérant du cabinet)"

    utilisateur = models.OneToOneField(
        "auth.User",
        on_delete=models.CASCADE,
        related_name="profil",
    )
    entreprise = models.ForeignKey(
        "EntrepriseParametres",
        on_delete=models.CASCADE,
        related_name="profils",
    )
    role = models.CharField(
        max_length=20,
        choices=Role.choices,
        default=Role.TECHNICIEN,
    )
    date_creation = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Profil"
        verbose_name_plural = "Profils"

    def __str__(self):
        return f"{self.utilisateur.username} ({self.get_role_display()}) -- {self.entreprise.nom or self.entreprise_id}"

    @property
    def peut_valider(self) -> bool:
        """Seul un ingénieur ou un admin peut verrouiller/valider (Étape 3)."""
        return self.role in (self.Role.INGENIEUR, self.Role.ADMIN)

    @property
    def est_admin(self) -> bool:
        return self.role == self.Role.ADMIN

class EvenementProduit(models.Model):
    """
    Journal des événements produit (analytics). Source UNIQUE des
    statistiques d'adoption : aucune statistique n'est reconstruite par
    estimation à partir des autres tables. Les chiffres ne sont donc
    fiables qu'à partir de la date du premier événement enregistré
    (voir analytics.date_debut_fiabilite()).
    """

    class Type(models.TextChoices):
        INSCRIPTION = "inscription", "Inscription d'un cabinet"
        CONNEXION = "connexion", "Connexion"
        PROJET_CREE = "projet_cree", "Projet créé"
        IMPORT_IFC = "import_ifc", "Import IFC confirmé"
        TRAME_GENEREE = "trame_generee", "Trame générée"
        ELEMENT_VALIDE = "element_valide", "Élément validé"
        ELEMENT_DEVERROUILLE = "element_deverrouille", "Élément déverrouillé"
        DQE_GENERE = "dqe_genere", "DQE généré"
        DQE_EXPORTE = "dqe_exporte", "DQE exporté"
        APPEL_IA = "appel_ia", "Appel assistant IA"

    type = models.CharField(max_length=40, choices=Type.choices, db_index=True)
    date = models.DateTimeField(auto_now_add=True, db_index=True)
    entreprise = models.ForeignKey(
        "EntrepriseParametres",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="evenements",
    )
    utilisateur = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="evenements_produit",
    )
    projet = models.ForeignKey(
        "Projet",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="evenements",
    )
    # Valeurs réellement mesurées au moment de l'événement (ex. montant
    # total du DQE généré, format d'export, source IA). Jamais estimées.
    donnees = models.JSONField(default=dict, blank=True)

    class Meta:
        ordering = ["-date"]
        verbose_name = "Événement produit"
        verbose_name_plural = "Événements produit"

    def __str__(self):
        return f"{self.get_type_display()} -- {self.date:%Y-%m-%d %H:%M}"
