from django.db import models


class Projet(models.Model):
    nom = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    usage_batiment = models.CharField(max_length=100, default="habitation")
    nb_niveaux = models.PositiveIntegerField(default=1)

    # Extension Trame Structurelle (Jour 1)
    nb_travees_x = models.PositiveIntegerField(default=1)
    nb_travees_y = models.PositiveIntegerField(default=1)
    portee_x = models.FloatField(default=4.0, help_text="Portée en mètres, direction X")
    portee_y = models.FloatField(default=4.0, help_text="Portée en mètres, direction Y")
    hauteur_etage = models.FloatField(default=3.0, help_text="Hauteur d'étage en mètres")
    charge_exploitation = models.FloatField(
        null=True,
        blank=True,
        help_text="kN/m² -- si vide, déduit de usage_batiment",
    )

    # Validation du plan de fondation (Jour 3 pré-intégré)
    plan_fondation_valide = models.BooleanField(default=False)

    date_creation = models.DateTimeField(auto_now_add=True)
    date_modification = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.nom


class ElementStructurel(models.Model):
    class TypeElement(models.TextChoices):
        POTEAU = "poteau", "Poteau"
        POUTRE = "poutre", "Poutre"
        SEMELLE = "semelle", "Semelle Isolée"
        DALLE = "dalle", "Dalle Pleine"
        SEMELLE_FILANTE = "semelle_filante", "Semelle Filante"

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

    # Inputs techniques de dimensionnement
    hauteur_poteau = models.FloatField(null=True, blank=True)
    charge_calculee = models.FloatField(null=True, blank=True)
    portee = models.FloatField(null=True, blank=True)
    charge_lineaire = models.FloatField(null=True, blank=True)
    taux_travail_sol = models.FloatField(null=True, blank=True)
    longueur_m = models.FloatField("Longueur (m)", null=True, blank=True)
    surface_m2 = models.FloatField("Surface (m²)", null=True, blank=True)

    # Résultats stockés au format JSON
    resultat_calcul = models.JSONField(null=True, blank=True)
    resultat_valide = models.JSONField(null=True, blank=True)

    date_creation = models.DateTimeField(auto_now_add=True)
    date_modification = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.identifiant} ({self.get_type_element_display()})"

class CoucheCharge(models.Model):
    """Module 2 : Couches de charges permanentes composées (multi-couches)"""

    projet = models.ForeignKey(
        Projet, on_delete=models.CASCADE, related_name="couches_charges"
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

    class TypePoste(models.TextChoices):
        MACONNERIE_PLEINE = "maconnerie_pleine", "Maçonnerie agglos pleins"
        MACONNERIE_CREUSE = "maconnerie_creuse", "Maçonnerie agglos creux"
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