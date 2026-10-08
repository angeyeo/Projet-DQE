"""
python manage.py audit_donnees_production [--json]

AUDIT EN LECTURE SEULE des données existantes face aux corrections du
moteur. Aucune écriture, aucune migration de données : la commande
IDENTIFIE et CHIFFRE ; chaque correction reste une décision humaine
(voir docs du projet, « Plan de reprise des données »).

Contrôles :
  1. projets sans cabinet (orphelins) ;
  2. lignes de l'ancien modèle Entreprise (déprécié) ;
  3. contraintes de sol suspectes d'être en MPa ou en bar (< 25 kN/m²) ;
  4. projets multi-niveaux générés avant le comptage des niveaux
     (poteaux/poutres avec nombre_identiques = 1 alors que nb_niveaux > 1)
     -> DQE sous-estimé tant que la trame n'est pas régénérée ;
  5. semelles calculées avec l'ancienne formule (hauteur sans enrobage,
     côté non arrondi) : résultat sans « cote_theorique_cm » ;
  6. résultats sans trace de calcul (antérieurs à la traçabilité) ;
  7. cabinets au barème incomplet, et prix sans date de saisie tracée ;
  8. agglos pleins : ancien prix au m³ -- l'unité validée est le m² ;
     le DQE refuse ce prix tant que le prix au m² n'est pas saisi ;
  9. projets SANS poids propre de l'ossature (valeur enregistrée avant la
     décision du technicien du 07/10/2026) : efforts calculés sans le
     poids des poutres et poteaux -- à décider projet par projet ;
 10. projets à 6 niveaux ou plus : dégression au-delà du 4e étage non
     validée par le technicien.
"""

import json

from django.core.management.base import BaseCommand

from projets.models import ElementStructurel, Entreprise, EntrepriseParametres, Projet
from projets.services.dqe_calculator import LIBELLES_PRIX

T = ElementStructurel.TypeElement


class Command(BaseCommand):
    help = "Audit en lecture seule des données de production (aucune écriture)."

    def add_arguments(self, parser):
        parser.add_argument("--json", action="store_true", help="Sortie JSON (pour archivage).")

    def handle(self, *args, **opts):
        rapport = {}

        orphelins = Projet.objects.filter(entreprise__isnull=True)
        rapport["projets_orphelins"] = list(orphelins.values("id", "nom", "cree_par__username"))

        rapport["entreprise_deprecie_lignes"] = Entreprise.objects.count()

        rapport["sols_suspects"] = {
            "projets": list(Projet.objects.filter(contrainte_sol_kn_m2__lt=25)
                            .values("id", "nom", "contrainte_sol_kn_m2")),
            "elements": list(ElementStructurel.objects.filter(taux_travail_sol__lt=25)
                             .values("id", "projet_id", "identifiant", "taux_travail_sol")),
            "note": "Valeur < 25 : probablement saisie en MPa (0,2 = 200 kN/m²) ou en bar (2 = 200 kN/m²). "
                    "Conversion à DÉCIDER projet par projet, jamais automatique.",
        }

        a_regenerer = []
        for p in Projet.objects.filter(nb_niveaux__gt=1):
            n = p.elements.filter(type_element__in=(T.POTEAU, T.POUTRE), nombre_identiques=1).count()
            if n:
                a_regenerer.append({"id": p.id, "nom": p.nom, "nb_niveaux": p.nb_niveaux, "elements_a_1_niveau": n})
        rapport["projets_multi_niveaux_a_regenerer"] = a_regenerer

        anciennes_semelles = [
            {"id": e.id, "projet_id": e.projet_id, "identifiant": e.identifiant, "statut": e.statut}
            for e in ElementStructurel.objects.filter(type_element=T.SEMELLE)
            if (e.resultat_valide or e.resultat_calcul) and
            "cote_theorique_cm" not in (e.resultat_valide or e.resultat_calcul)
        ]
        rapport["semelles_ancienne_formule"] = {"nombre": len(anciennes_semelles), "elements": anciennes_semelles[:200]}

        rapport["resultats_sans_trace"] = sum(
            1 for e in ElementStructurel.objects.filter(type_element__in=(T.POTEAU, T.SEMELLE, T.POUTRE))
            if (e.resultat_valide or e.resultat_calcul) and "trace" not in (e.resultat_valide or e.resultat_calcul)
        )

        cabinets = []
        for c in EntrepriseParametres.objects.all():
            prix = c.prix_unitaires or {}
            meta = c.prix_unitaires_meta or {}
            manquants = [k for k in LIBELLES_PRIX if prix.get(k) in (None, "")]
            sans_date = [k for k in prix if k not in meta]
            if manquants or sans_date:
                cabinets.append({"id": c.id, "nom": c.nom, "prix_manquants": manquants, "prix_sans_date": sans_date})
        rapport["baremes"] = cabinets
        rapport["agglos_pleins_m3_renseignes"] = [
            {"id": c.id, "nom": c.nom, "prix": (c.prix_unitaires or {}).get("agglos_pleins_m3")}
            for c in EntrepriseParametres.objects.all()
            if (c.prix_unitaires or {}).get("agglos_pleins_m3") not in (None, "")
        ]

        rapport["projets_sans_poids_propre"] = [
            {"id": p.id, "nom": p.nom, "valide_ou_dqe": p.elements.filter(statut=ElementStructurel.Statut.VALIDE).exists()}
            for p in Projet.objects.filter(inclure_poids_propre_ossature=False).order_by("id")
        ]
        rapport["projets_degression_non_validee"] = list(
            Projet.objects.filter(nb_niveaux__gte=6).order_by("id").values("id", "nom", "nb_niveaux"))

        if opts["json"]:
            self.stdout.write(json.dumps(rapport, ensure_ascii=False, indent=2, default=str))
            return
        self.stdout.write("AUDIT EN LECTURE SEULE -- aucune donnée n'a été modifiée.\n")
        self.stdout.write(f"1. Projets sans cabinet : {len(rapport['projets_orphelins'])}")
        self.stdout.write(f"2. Lignes de l'ancien modèle Entreprise : {rapport['entreprise_deprecie_lignes']}")
        self.stdout.write(f"3. Sols < 25 kN/m² : {len(rapport['sols_suspects']['projets'])} projet(s), "
                          f"{len(rapport['sols_suspects']['elements'])} élément(s)")
        self.stdout.write(f"4. Projets multi-niveaux à régénérer (DQE sous-estimé) : {len(a_regenerer)}")
        for p in a_regenerer:
            self.stdout.write(f"     #{p['id']} {p['nom']} : {p['nb_niveaux']} niveaux, "
                              f"{p['elements_a_1_niveau']} poteaux/poutres comptés une seule fois")
        self.stdout.write(f"5. Semelles calculées avec l'ancienne formule : {len(anciennes_semelles)}")
        self.stdout.write(f"6. Résultats sans trace de calcul : {rapport['resultats_sans_trace']}")
        self.stdout.write(f"7. Cabinets au barème incomplet ou non daté : {len(cabinets)}")
        self.stdout.write(f"8. Cabinets avec un prix « agglos pleins au m³ » : {len(rapport['agglos_pleins_m3_renseignes'])}")
        self.stdout.write(f"9. Projets sans poids propre de l'ossature : {len(rapport['projets_sans_poids_propre'])} "
                          f"(dont {sum(1 for p in rapport['projets_sans_poids_propre'] if p['valide_ou_dqe'])} "
                          f"avec éléments validés)")
        self.stdout.write(f"10. Projets de 6 niveaux ou plus (dégression non validée) : "
                          f"{len(rapport['projets_degression_non_validee'])}")
