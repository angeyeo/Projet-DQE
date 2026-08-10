"""
Modèles du domaine.

Un Projet regroupe plusieurs ElementStructurel (poteaux, poutres,
semelles). Chaque élément a un statut qui sert de verrou logiciel :
tant qu'il n'est pas VALIDE, il n'entre pas dans le calcul du DQE.
"""

from django.db import models


class Projet(models.Model):
    nom = models.CharField(max_length=255)
    usage_batiment = models.CharField(
        max_length=50,
        choices=[
            ("habitation", "Habitation"),
            ("commerce", "Commerce"),
            ("bureau", "Bureau"),
            ("industriel", "Industriel"),
        ],
    )
    nb_niveaux = models.PositiveIntegerField()
    date_creation = models.DateTimeField(auto_now_add=True)
    date_modification = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.nom


class ElementStructurel(models.Model):
    class TypeElement(models.TextChoices):
        POTEAU = "poteau", "Poteau"
        POUTRE = "poutre", "Poutre"
        SEMELLE = "semelle", "Semelle"

    class Statut(models.TextChoices):
        PROPOSE = "propose", "Proposé"
        MODIFIE = "modifie", "Modifié"
        VALIDE = "valide", "Validé"

    projet = models.ForeignKey(Projet, on_delete=models.CASCADE, related_name="elements")
    type_element = models.CharField(max_length=20, choices=TypeElement.choices)
    identifiant = models.CharField(
        max_length=50, help_text="Ex. 'P1', 'PT-RDC-2' -- repère de l'élément dans le plan"
    )

    # Paramètres d'entrée (dépendent du type d'élément -- tous optionnels
    # au niveau du modèle, la validation métier se fait dans le serializer/moteur)
    portee = models.FloatField(null=True, blank=True, help_text="mètres, pour une poutre")
    charge_lineaire = models.FloatField(null=True, blank=True, help_text="kN/m, pour une poutre")
    charge_calculee = models.FloatField(
        null=True, blank=True, help_text="kN, charge reprise par l'élément (poteau/semelle)"
    )
    hauteur_poteau = models.FloatField(null=True, blank=True, help_text="mètres")
    taux_travail_sol = models.FloatField(null=True, blank=True, help_text="bars, pour une semelle")

    # Résultat proposé par le moteur de calcul (rempli automatiquement)
    resultat_calcul = models.JSONField(
        null=True, blank=True, help_text="Dict retourné par le moteur de calcul"
    )

    # Valeurs éventuellement ajustées manuellement par l'ingénieur
    resultat_valide = models.JSONField(
        null=True, blank=True, help_text="Valeurs finales après validation/ajustement humain"
    )

    statut = models.CharField(
        max_length=20, choices=Statut.choices, default=Statut.PROPOSE
    )

    date_creation = models.DateTimeField(auto_now_add=True)
    date_modification = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.get_type_element_display()} {self.identifiant} ({self.projet.nom})"


class PosteMainDoeuvre(models.Model):
    """
    Poste de main d'œuvre saisi manuellement par l'ingénieur -- distinct
    des éléments structurels calculés automatiquement. Le montant n'est
    jamais stocké : il est toujours recalculé à partir de la quantité et
    du prix unitaire actuels (propriété `montant`), pour éviter toute
    désynchronisation si l'un des deux est modifié après coup.
    """

    projet = models.ForeignKey(
        Projet, on_delete=models.CASCADE, related_name="postes_main_doeuvre"
    )
    designation = models.CharField(
        max_length=255, help_text="Ex. 'Main d'œuvre coffrage', 'Terrassement/fouilles'"
    )
    unite = models.CharField(max_length=20, help_text="Ex. 'm²', 'kg', 'forfait', 'm³'")
    quantite = models.FloatField()
    prix_unitaire = models.FloatField(help_text="FCFA")

    date_creation = models.DateTimeField(auto_now_add=True)
    date_modification = models.DateTimeField(auto_now=True)

    @property
    def montant(self):
        return self.quantite * self.prix_unitaire

    def __str__(self):
        return f"{self.designation} ({self.projet.nom})"