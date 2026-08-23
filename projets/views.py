import os
import logging
from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.parsers import MultiPartParser, FormParser, JSONParser
from rest_framework.permissions import IsAuthenticated, AllowAny
from rest_framework.response import Response
from rest_framework.throttling import ScopedRateThrottle
from rest_framework.views import APIView
from django.conf import settings
from django.http import HttpResponse
from django.shortcuts import get_object_or_404

from .models import Projet, ElementStructurel, CoucheCharge, PosteComplementaire, EntrepriseParametres
from .serializers import (
    ProjetSerializer,
    ElementStructurelSerializer,
    ElementValidationSerializer,
    CoucheChargeSerializer,
    PosteComplementaireSerializer,
    EntrepriseParametresSerializer,
)
from .services import calculer_element, recalculer_projet, CalculNonDisponible
from .services.dqe_calculator import calculer_projet_dqe
from .services.dqe_exporters import exporter_dqe_pdf, exporter_dqe_excel
from .services.assistant_ia.parser import structurer_description_projet
from .services.assistant_ia.explanations import expliquer_resultat_element
from .services.assistant_ia.postes import suggerer_poste_complementaire
from .services.assistant_ia.client import LLMServiceError
from .services.assistant_ia.vision import analyser_plan_2d
from moteur_calcul.validators import EntreeInvalide

logger = logging.getLogger(__name__)


def _semelles_pour_dxf(semelles) -> list:
    """
    Adapte le queryset ElementStructurel (type SEMELLE) vers le format
    plat attendu par generer_plan_fondation_dxf() (projets/services/plan_fondation.py) :
    {identifiant, position_x, position_y, cote_cm, hauteur_cm,
    poteau_associe: {identifiant, cote_cm}, [indice_i, indice_j]}.

    indice_i/indice_j sont extraits de l'identifiant "S_<i>_<j>" généré
    par ProjetViewSet.generer_trame -- absents pour toute semelle créée
    autrement (ex. saisie manuelle), auquel cas generer_plan_fondation_dxf
    retombe sur la méthode d'adjacence par position (voir sa docstring).
    """
    resultat = []
    for semelle in semelles:
        resultat_calcul = semelle.resultat_calcul or {}
        poteau = semelle.poteau_associe
        poteau_resultat = (poteau.resultat_calcul or {}) if poteau else {}

        item = {
            "identifiant": semelle.identifiant,
            "position_x": semelle.position_x,
            "position_y": semelle.position_y,
            "cote_cm": resultat_calcul.get("cote_cm"),
            "hauteur_cm": resultat_calcul.get("hauteur_cm"),
            "poteau_associe": (
                {"identifiant": poteau.identifiant, "cote_cm": poteau_resultat.get("cote_cm")}
                if poteau else None
            ),
        }

        parts = (semelle.identifiant or "").split("_")
        if len(parts) == 3 and parts[0] == "S" and parts[1].lstrip("-").isdigit() and parts[2].lstrip("-").isdigit():
            item["indice_i"] = int(parts[1])
            item["indice_j"] = int(parts[2])

        resultat.append(item)
    return resultat


def _empreinte_niveau_bas(poteaux: list) -> list:
    """
    Filtre extraire_poteaux()/analyser_fichier_ifc() sur le niveau de plus
    basse élévation (typiquement le RDC) : hypothèse simplificatrice du
    moteur de trame (voir moteur_calcul/formules/trame.py) selon laquelle
    tous les niveaux partagent la même empreinte -- la charge multi-niveaux
    est cumulée séparément via nb_niveaux (dégression, Module 1), pas en
    créant un jeu d'éléments par étage.
    """
    if not poteaux:
        return []
    elevation_min = min(p["niveau_elevation_m"] for p in poteaux)
    return [p for p in poteaux if p["niveau_elevation_m"] == elevation_min]


# Tolérance (mètres) pour considérer deux IfcColumn comme le même poteau
# physique. Constaté sur des exports ArchiCAD réels (ex. profil composite
# noyau/habillage, ou entité dupliquée par erreur d'export) : plusieurs
# IfcColumn peuvent coexister exactement à la même position (X,Y). Sans
# déduplication, chaque doublon produit un poteau ET une semelle en plus,
# superposés au même endroit -- illisible sur le plan (labels empilés) et
# compté en double dans le DQE (surcoût fictif).
TOLERANCE_DOUBLON_POTEAU_M = 0.10


def _dedupliquer_poteaux_par_position(poteaux: list, tolerance: float = TOLERANCE_DOUBLON_POTEAU_M) -> list:
    """
    Regroupe les poteaux (déjà filtrés sur un seul niveau par
    _empreinte_niveau_bas) quasi à la même position (X,Y) et n'en garde
    qu'un par groupe -- voir TOLERANCE_DOUBLON_POTEAU_M pour la cause.
    Algorithme volontairement simple (O(n^2)) : les empreintes réelles
    restent de taille modeste (quelques dizaines à centaines de poteaux).
    """
    if not poteaux:
        return []
    restants = list(poteaux)
    uniques = []
    while restants:
        base = restants.pop(0)
        reste = []
        for p in restants:
            dx = p["x"] - base["x"]
            dy = p["y"] - base["y"]
            if (dx * dx + dy * dy) ** 0.5 > tolerance:
                reste.append(p)
        restants = reste
        uniques.append(base)
    return uniques


def _grouper_par_classe_dimension(elements: list, tolerance_cm: float = 5.0) -> list:
    """
    Regroupe une liste d'ElementStructurel (poteaux ou semelles) par
    classe de dimension proche (cote_cm dans resultat_calcul), à
    tolerance_cm près, et renvoie les groupes triés du plus grand au
    plus petit -- convention des plans de coffrage professionnels
    (ex. S1 = la plus grande semelle, S2, S3... la plus petite ; même
    repère réutilisé à chaque emplacement de taille identique).
    Les éléments sans cote_cm exploitable (None) forment leur propre
    groupe à part, placé en dernier.
    """
    avec_cote = []
    sans_cote = []
    for el in elements:
        cote = (el.resultat_calcul or {}).get("cote_cm")
        if cote is None:
            sans_cote.append(el)
        else:
            avec_cote.append((el, float(cote)))

    avec_cote.sort(key=lambda t: t[1], reverse=True)
    groupes = []
    for el, cote in avec_cote:
        for groupe in groupes:
            if abs(groupe["cote"] - cote) <= tolerance_cm:
                groupe["elements"].append(el)
                break
        else:
            groupes.append({"cote": cote, "elements": [el]})

    resultat = [g["elements"] for g in groupes]
    if sans_cote:
        resultat.append(sans_cote)
    return resultat


def _renommer_par_classe_dimension(elements: list, prefixe: str) -> None:
    """
    Renomme en place (identifiant + save()) une liste d'ElementStructurel
    du même type (tous poteaux, ou toutes semelles) selon leur classe de
    dimension : prefixe+"1" pour la plus grande, prefixe+"2" la
    suivante, etc. -- voir _grouper_par_classe_dimension(). Remplace
    l'identifiant brut dérivé du GlobalId IFC (ex. "P_2izTjP2U",
    illisible et sans rapport avec la taille réelle de l'élément) par
    une convention proche des plans de coffrage professionnels.
    """
    for idx, groupe in enumerate(_grouper_par_classe_dimension(elements), start=1):
        nom = f"{prefixe}{idx}"
        for el in groupe:
            el.identifiant = nom
        ElementStructurel.objects.bulk_update(groupe, ["identifiant"])


_TYPES_OUVRAGES_LINEAIRES = {
    ElementStructurel.TypeElement.POUTRE: "poutres",
    ElementStructurel.TypeElement.LONGRINE: "longrines",
    ElementStructurel.TypeElement.CHAINAGE: "chainages_identifies",
}


def _ouvrages_lineaires_pour_dxf(elements) -> dict:
    """
    Adapte les ElementStructurel de type poutre/longrine/chaînage
    identifié (voir Phase C de la feuille de route) vers le format plat
    attendu par generer_plan_fondation_dxf() :
    {"poutres": [...], "longrines": [...], "chainages_identifies": [...]}
    où chaque item est {identifiant, x1, y1, x2, y2, largeur_cm, hauteur_cm}.

    Un ouvrage sans poteau_origine/poteau_destination renseigné (créé
    avant l'ajout de ces champs, ex. donnée historique) est ignoré ici
    plutôt que de faire planter tout l'export DXF -- il continue
    d'exister normalement partout ailleurs (DQE, validation...), juste
    absent du tracé linéaire du plan de coffrage.
    """
    resultat = {"poutres": [], "longrines": [], "chainages_identifies": []}
    for element in elements:
        cle = _TYPES_OUVRAGES_LINEAIRES.get(element.type_element)
        if cle is None:
            continue
        origine, destination = element.poteau_origine, element.poteau_destination
        if origine is None or destination is None:
            continue

        resultat_calcul = element.resultat_calcul or {}
        resultat[cle].append({
            "identifiant": element.identifiant,
            "x1": origine.position_x,
            "y1": origine.position_y,
            "x2": destination.position_x,
            "y2": destination.position_y,
            "largeur_cm": resultat_calcul.get("largeur_cm"),
            "hauteur_cm": resultat_calcul.get("hauteur_cm"),
        })
    return resultat


def _entreprise_export_dict(entreprise: "EntrepriseParametres") -> dict:
    """Convertit le modèle EntrepriseParametres en dict simple pour les
    exporters (découplés de Django), avec le chemin disque du logo."""
    logo_path = None
    if entreprise.logo and hasattr(entreprise.logo, "path"):
        try:
            if os.path.exists(entreprise.logo.path):
                logo_path = entreprise.logo.path
        except (ValueError, NotImplementedError):
            logo_path = None
    return {
        "logo_path": logo_path,
        "nom": entreprise.nom,
        "siege_social": entreprise.siege_social,
        "telephone": entreprise.telephone,
        "email": entreprise.email,
        "site_web": entreprise.site_web,
        "rccm": entreprise.rccm,
        "cc": entreprise.cc,
        "cb": entreprise.cb,
        "capital_social": entreprise.capital_social,
    }


class ProjetViewSet(viewsets.ModelViewSet):
    queryset = Projet.objects.all()
    serializer_class = ProjetSerializer

    def get_permissions(self):
        if self.action == "analyser_plan_image":
            if os.getenv("DEMO_MODE", "False").lower() == "true":
                return [AllowAny()]
            return [IsAuthenticated()]
        return super().get_permissions()

    def get_throttles(self):
        if self.action == "analyser_plan_image":
            self.throttle_scope = "assistant_vision"
            return [ScopedRateThrottle()]
        return super().get_throttles()

    @action(detail=True, methods=["post"])
    def recalculer(self, request, pk=None):
        projet = self.get_object()
        resultats = recalculer_projet(projet)
        return Response(resultats, status=status.HTTP_200_OK)

    @action(detail=True, methods=["get"])
    def chainage_suggere(self, request, pk=None):
        projet = self.get_object()
        try:
            from moteur_calcul.formules.postes_ratio import calculer_longueur_chainage

            longueur = calculer_longueur_chainage(
                projet.nb_travees_x,
                projet.nb_travees_y,
                projet.portee_x,
                projet.portee_y,
            )
        except (ImportError, ModuleNotFoundError, AttributeError):
            longueur = 2 * (
                projet.nb_travees_x * projet.portee_x
                + projet.nb_travees_y * projet.portee_y
            )
        return Response({"longueur_m": longueur}, status=status.HTTP_200_OK)

    @action(detail=True, methods=["post"])
    def generer_trame(self, request, pk=None):
        """
        Génère la grille complète de l'ouvrage (poteaux + semelles à
        chaque nœud, poutres entre nœuds adjacents) à partir de
        projet.nb_travees_x/y, portee_x/y et hauteur_etage -- toutes déjà
        calculées (resultat_calcul rempli), en un seul appel.

        Idempotent : régénérer la trame (ex. après modification des
        paramètres à l'Étape 1) repart d'une grille vierge pour ce
        projet, plutôt que d'empiler les éléments à chaque appel.
        """
        projet = self.get_object()
        projet.elements.all().delete()

        elements_crees = []

        try:
            from moteur_calcul.formules.trame import (
                generer_poteau_sur_grille,
                generer_poutre_sur_grille,
            )
        except (ImportError, ModuleNotFoundError):
            generer_poteau_sur_grille = None
            generer_poutre_sur_grille = None

        charge_exp = projet.charge_exploitation or 1.5
        nb_x, nb_y = projet.nb_travees_x, projet.nb_travees_y
        portee_x, portee_y = projet.portee_x, projet.portee_y

        poteaux_par_noeud = {}

        # 1. Poteaux + semelles à chaque nœud (i, j) de la grille.
        for i in range(nb_x + 1):
            for j in range(nb_y + 1):
                x = i * portee_x
                y = j * portee_y

                if generer_poteau_sur_grille:
                    donnees = generer_poteau_sur_grille(
                        i, j, portee_x, portee_y, nb_x, nb_y, charge_exp, projet.hauteur_etage,
                        nb_niveaux=projet.nb_niveaux, usage_batiment=projet.usage_batiment,
                    )
                    charge_elu = donnees.get("charge_elu_kn", 100.0)
                    res_poteau = donnees.get("resultat_poteau")
                    res_semelle = donnees.get("resultat_semelle")
                else:
                    charge_elu = 150.0
                    res_poteau = {"cote_cm": 25, "acier_cm2": 4.5}
                    res_semelle = {"cote_cm": 120, "hauteur_cm": 30}

                poteau = ElementStructurel.objects.create(
                    projet=projet,
                    identifiant=f"P_{i}_{j}",
                    type_element=ElementStructurel.TypeElement.POTEAU,
                    position=ElementStructurel.Position.SUPERSTRUCTURE,
                    position_x=x,
                    position_y=y,
                    hauteur_poteau=projet.hauteur_etage,
                    charge_calculee=charge_elu,
                    resultat_calcul=res_poteau,
                )
                elements_crees.append(poteau)
                poteaux_par_noeud[(i, j)] = poteau

                semelle = ElementStructurel.objects.create(
                    projet=projet,
                    identifiant=f"S_{i}_{j}",
                    type_element=ElementStructurel.TypeElement.SEMELLE,
                    position=ElementStructurel.Position.INFRASTRUCTURE,
                    position_x=x,
                    position_y=y,
                    poteau_associe=poteau,
                    charge_calculee=charge_elu,
                    taux_travail_sol=0.2,
                    resultat_calcul=res_semelle,
                )
                elements_crees.append(semelle)

        # 2. Poutres entre nœuds adjacents (méthode des largeurs
        #    d'influence : une poutre "intérieure", encadrée par une
        #    dalle de chaque côté, reprend la portée perpendiculaire
        #    complète ; une poutre de rive n'en reprend que la moitié).
        for j in range(nb_y + 1):
            for i in range(nb_x):
                largeur_influence = portee_y if 0 < j < nb_y else portee_y / 2
                if generer_poutre_sur_grille:
                    donnees = generer_poutre_sur_grille(portee_x, largeur_influence, charge_exp)
                    charge_lineaire = donnees["charge_lineaire_kn_m"]
                    res_poutre = donnees["resultat_poutre"]
                else:
                    charge_lineaire = 20.0
                    res_poutre = {"largeur_cm": 20, "hauteur_cm": 40}

                poutre = ElementStructurel.objects.create(
                    projet=projet,
                    identifiant=f"PX_{i}_{j}",
                    type_element=ElementStructurel.TypeElement.POUTRE,
                    position=ElementStructurel.Position.SUPERSTRUCTURE,
                    position_x=(i + 0.5) * portee_x,
                    position_y=j * portee_y,
                    portee=portee_x,
                    charge_lineaire=charge_lineaire,
                    resultat_calcul=res_poutre,
                    poteau_origine=poteaux_par_noeud[(i, j)],
                    poteau_destination=poteaux_par_noeud[(i + 1, j)],
                )
                elements_crees.append(poutre)

        for i in range(nb_x + 1):
            for j in range(nb_y):
                largeur_influence = portee_x if 0 < i < nb_x else portee_x / 2
                if generer_poutre_sur_grille:
                    donnees = generer_poutre_sur_grille(portee_y, largeur_influence, charge_exp)
                    charge_lineaire = donnees["charge_lineaire_kn_m"]
                    res_poutre = donnees["resultat_poutre"]
                else:
                    charge_lineaire = 20.0
                    res_poutre = {"largeur_cm": 20, "hauteur_cm": 40}

                poutre = ElementStructurel.objects.create(
                    projet=projet,
                    identifiant=f"PY_{i}_{j}",
                    type_element=ElementStructurel.TypeElement.POUTRE,
                    position=ElementStructurel.Position.SUPERSTRUCTURE,
                    position_x=i * portee_x,
                    position_y=(j + 0.5) * portee_y,
                    portee=portee_y,
                    charge_lineaire=charge_lineaire,
                    resultat_calcul=res_poutre,
                    poteau_origine=poteaux_par_noeud[(i, j)],
                    poteau_destination=poteaux_par_noeud[(i, j + 1)],
                )
                elements_crees.append(poutre)

        serializer = ElementStructurelSerializer(elements_crees, many=True)
        return Response(serializer.data, status=status.HTTP_201_CREATED)

    @action(detail=True, methods=["post"], parser_classes=[MultiPartParser, FormParser, JSONParser])
    def importer_plan(self, request, pk=None):
        """
        Import de plan (Phases A + B -- voir Feuille_de_route_Import_Plan_Automatique.md).

        Deux usages du même endpoint, distingués par le contenu de la requête :

        1) Aperçu (Phase A) -- multipart avec un fichier "fichier" (IFC) :
           analyse le fichier via Genius (moteur_calcul.import_ifc), stocke le
           fichier sur le projet (audit + réutilisation en Phase B) et renvoie
           les paramètres de trame détectés SANS créer aucun ElementStructurel.
           C'est le frontend (Yves) qui affiche ces valeurs, pré-remplies mais
           modifiables, dans le formulaire de l'Étape 1.

        2) Confirmation (Phase B) -- JSON {"confirmer": true}, sans fichier :
           relit le fichier IFC déjà déposé à l'étape 1) et crée les VRAIS
           éléments (poteaux + semelles + poutres) à leurs positions réelles
           détectées, en réutilisant projet.hauteur_etage/nb_niveaux/
           usage_batiment/charge_exploitation tels que corrigés entre-temps
           par l'utilisateur. Remplace generer_trame/ pour ce chemin --
           idempotent comme lui (vide les éléments existants avant de
           recréer).
        """
        projet = self.get_object()
        fichier = request.FILES.get("fichier")
        confirmer = str(request.data.get("confirmer", "")).strip().lower() in (
            "1", "true", "vrai", "oui", "yes",
        )

        if fichier is None and not confirmer:
            return Response(
                {
                    "erreur": "Fournissez un fichier IFC (champ \"fichier\") pour "
                    "un aperçu, ou confirmer=true pour créer les éléments à "
                    "partir d'un aperçu déjà réalisé."
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            from moteur_calcul.import_ifc.lecture_ifc import (
                analyser_fichier_ifc,
                FichierIFCInvalide,
                AucunPoteauDetecte,
            )
        except ImportError as exc:
            return Response(
                {"erreur": f"Moteur d'import IFC indisponible sur ce serveur : {exc}"},
                status=status.HTTP_503_SERVICE_UNAVAILABLE,
            )

        if fichier is not None:
            # --- Phase A : aperçu, aucun élément créé --------------------
            projet.fichier_import_origine = fichier
            projet.save(update_fields=["fichier_import_origine"])
            try:
                parametres = analyser_fichier_ifc(projet.fichier_import_origine.path)
            except (FichierIFCInvalide, AucunPoteauDetecte) as exc:
                return Response({"erreur": str(exc)}, status=status.HTTP_400_BAD_REQUEST)

            parametres.pop("poteaux", None)  # détail interne, pas utile côté aperçu
            return Response(parametres, status=status.HTTP_200_OK)

        # --- Phase B : confirmation, création réelle ---------------------
        if not projet.fichier_import_origine:
            return Response(
                {"erreur": "Aucun plan importé au préalable pour ce projet : "
                 "envoyez d'abord un fichier IFC à cet endpoint."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        try:
            resultat = analyser_fichier_ifc(projet.fichier_import_origine.path)
        except (FichierIFCInvalide, AucunPoteauDetecte) as exc:
            return Response({"erreur": str(exc)}, status=status.HTTP_400_BAD_REQUEST)

        try:
            from moteur_calcul.formules.trame import (
                generer_poteau_depuis_position_reelle,
                detecter_poutres_adjacentes,
            )
        except ImportError as exc:
            return Response(
                {"erreur": f"Moteur de trame indisponible sur ce serveur : {exc}"},
                status=status.HTTP_503_SERVICE_UNAVAILABLE,
            )

        empreinte = _empreinte_niveau_bas(resultat["poteaux"])
        if not empreinte:
            return Response(
                {"erreur": "Aucun poteau exploitable au niveau bas détecté dans ce plan."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        nb_avant_dedup = len(empreinte)
        empreinte = _dedupliquer_poteaux_par_position(empreinte)
        avertissements = list(resultat.get("avertissements", []))
        nb_doublons = nb_avant_dedup - len(empreinte)
        if nb_doublons:
            avertissements.append(
                f"{nb_doublons} poteau(x) ignoré(s) car quasi superposé(s) "
                f"(< {TOLERANCE_DOUBLON_POTEAU_M * 100:.0f} cm) à un autre poteau déjà "
                f"détecté -- export IFC contenant probablement des colonnes "
                f"dupliquées (profil composite ou entité en double)."
            )

        projet.elements.all().delete()

        charge_exp = projet.charge_exploitation or 1.5
        elements_crees = []
        poteau_par_guid = {}

        for p in empreinte:
            try:
                donnees = generer_poteau_depuis_position_reelle(
                    p, empreinte, charge_exp, projet.hauteur_etage,
                    nb_niveaux=projet.nb_niveaux, usage_batiment=projet.usage_batiment,
                )
            except ValueError as exc:
                avertissements.append(str(exc))
                continue

            identifiant_poteau = f"P_{p.get('guid', '')[:8] or len(poteau_par_guid)}"
            poteau = ElementStructurel.objects.create(
                projet=projet,
                identifiant=identifiant_poteau,
                type_element=ElementStructurel.TypeElement.POTEAU,
                position=ElementStructurel.Position.SUPERSTRUCTURE,
                position_x=donnees["x"],
                position_y=donnees["y"],
                hauteur_poteau=projet.hauteur_etage,
                charge_calculee=donnees["charge_elu_kn"],
                resultat_calcul=donnees["resultat_poteau"],
            )
            elements_crees.append(poteau)
            poteau_par_guid[p.get("guid")] = poteau

            semelle = ElementStructurel.objects.create(
                projet=projet,
                identifiant=f"S_{identifiant_poteau}",
                type_element=ElementStructurel.TypeElement.SEMELLE,
                position=ElementStructurel.Position.INFRASTRUCTURE,
                position_x=donnees["x"],
                position_y=donnees["y"],
                poteau_associe=poteau,
                charge_calculee=donnees["charge_elu_kn"],
                taux_travail_sol=0.2,
                resultat_calcul=donnees["resultat_semelle"],
            )
            elements_crees.append(semelle)

        # Renommage par classe de dimension (S1 = plus grande semelle, S2...,
        # idem P1... pour les poteaux) -- remplace les identifiants bruts
        # dérivés du GlobalId IFC par une convention proche des plans de
        # coffrage professionnels. Fait ici, avant la génération des
        # poutres, pour que leurs noms (ex. "PX_P1_P3") reflètent déjà les
        # nouveaux repères plutôt que les GUID tronqués.
        poteaux_crees = [poteau_par_guid[guid] for guid in poteau_par_guid]
        semelles_crees = [el for el in elements_crees if el.type_element == ElementStructurel.TypeElement.SEMELLE]
        _renommer_par_classe_dimension(poteaux_crees, "P")
        _renommer_par_classe_dimension(semelles_crees, "S")

        for pd in detecter_poutres_adjacentes(empreinte, charge_exp):
            origine = poteau_par_guid.get(pd["poteau_origine_guid"])
            destination = poteau_par_guid.get(pd["poteau_destination_guid"])
            if origine is None or destination is None:
                continue  # un des deux poteaux a été écarté ci-dessus (surface invalide)

            prefixe = "PX" if pd["axe"] == "x" else "PY"
            poutre = ElementStructurel.objects.create(
                projet=projet,
                identifiant=f"{prefixe}_{origine.identifiant}_{destination.identifiant}",
                type_element=ElementStructurel.TypeElement.POUTRE,
                position=ElementStructurel.Position.SUPERSTRUCTURE,
                position_x=(origine.position_x + destination.position_x) / 2,
                position_y=(origine.position_y + destination.position_y) / 2,
                portee=pd["portee_m"],
                charge_lineaire=pd["charge_lineaire_kn_m"],
                resultat_calcul=pd["resultat_poutre"],
                poteau_origine=origine,
                poteau_destination=destination,
            )
            elements_crees.append(poutre)

        serializer = ElementStructurelSerializer(elements_crees, many=True)
        return Response(
            {"elements": serializer.data, "avertissements": avertissements},
            status=status.HTTP_201_CREATED,
        )

    @action(detail=True, methods=["post"], parser_classes=[MultiPartParser, FormParser])
    def analyser_plan_image(self, request, pk=None):
        """
        POST /api/projets/{id}/analyser_plan_image/
        Analyse de plan 2D au format image (JPEG/PNG) en mode APERÇU uniquement (Phase A).
        """
        projet = self.get_object()

        fichier = request.FILES.get("fichier")
        if not fichier:
            return Response(
                {"detail": "Le fichier image est requis dans le champ 'fichier'."},
                status=status.HTTP_400_BAD_REQUEST
            )

        # Validation de la taille maximale du fichier avant lecture en mémoire
        max_bytes = getattr(settings, "PLAN_IMAGE_MAX_BYTES", 5 * 1024 * 1024)
        if fichier.size > max_bytes:
            return Response(
                {
                    "detail": f"Le fichier est trop volumineux. La taille maximale autorisée est de {max_bytes / (1024 * 1024):.1f} Mo."
                },
                status=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE
            )

        try:
            image_bytes = fichier.read()
            mime_type = fichier.content_type

            resultat = analyser_plan_2d(image_bytes, mime_type)
            resultat["mode_import"] = "VISION"
            return Response(resultat, status=status.HTTP_200_OK)
        except ValueError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        except Exception as exc:
            logger.exception("Erreur inattendue lors de l'analyse de l'image du plan")
            return Response(
                {"detail": "Une erreur interne est survenue lors du traitement de l'image."},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

    @action(detail=True, methods=["get"])
    def plan_fondation(self, request, pk=None):
        """
        GET /api/projets/{id}/plan_fondation/[?export=dxf]

        Note : le paramètre s'appelle "export" (et non "format") --
        "format" est réservé par la négociation de contenu de DRF : une
        valeur ne correspondant à aucun renderer enregistré (json, api)
        y déclenche un Http404 avant même d'atteindre ce code (bug
        pré-existant, découvert en testant l'endpoint réel plutôt que la
        seule fonction generer_plan_fondation_dxf() -- voir test_dqe.py
        pour generer_dqe/, qui utilisait déjà "export" et n'avait donc
        pas le problème).
        """
        projet = self.get_object()
        export_format = request.query_params.get("export")

        semelles = projet.elements.filter(
            type_element=ElementStructurel.TypeElement.SEMELLE
        )

        if export_format == "dxf":
            if not semelles.exists():
                return Response(
                    {"erreur": "Aucune semelle disponible : impossible de générer le plan de fondation."},
                    status=status.HTTP_400_BAD_REQUEST,
                )
            try:
                from projets.services.plan_fondation import generer_plan_fondation_dxf

                ouvrages = _ouvrages_lineaires_pour_dxf(projet.elements.all())
                content = generer_plan_fondation_dxf(
                    _semelles_pour_dxf(semelles),
                    poutres=ouvrages["poutres"],
                    longrines=ouvrages["longrines"],
                    chainages_identifies=ouvrages["chainages_identifies"],
                )
            except (ImportError, ModuleNotFoundError):
                content = b"0\nSECTION\n2\nHEADER\n0\nENDSEC\n0\nEOF\n"
            except ValueError as err:
                return Response({"erreur": str(err)}, status=status.HTTP_400_BAD_REQUEST)

            response = HttpResponse(content, content_type="application/dxf")
            response["Content-Disposition"] = (
                f'attachment; filename="Plan_fondation_{projet.id}.dxf"'
            )
            return response

        serializer = ElementStructurelSerializer(semelles, many=True)
        return Response({"semelles": serializer.data}, status=status.HTTP_200_OK)

    @action(detail=True, methods=["post"])
    def valider_plan_fondation(self, request, pk=None):
        projet = self.get_object()
        projet.plan_fondation_valide = True
        projet.save(update_fields=["plan_fondation_valide"])
        return Response(
            {"status": "Plan de fondation validé."}, status=status.HTTP_200_OK
        )

    @action(
        detail=True,
        methods=["get", "post"],
        url_path="generer-dqe",
        url_name="generer-dqe",
    )
    def generer_dqe(self, request, pk=None):
        projet = self.get_object()

        if not projet.elements.exists():
            return Response(
                {"erreur": "Le projet ne contient aucun élément structurel."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        elements_non_valides = projet.elements.exclude(
            statut=ElementStructurel.Statut.VALIDE
        )
        if elements_non_valides.exists():
            return Response(
                {
                    "erreur": "Tous les éléments doivent être validés.",
                    "elements_en_attente": list(
                        elements_non_valides.values_list("identifiant", flat=True)
                    ),
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        export_format = request.query_params.get("export") or (
            request.data.get("export") if isinstance(request.data, dict) else None
        )
        dqe_data = calculer_projet_dqe(projet)

        if export_format is None:
            return Response(dqe_data, status=status.HTTP_200_OK)

        nom_fichier_base = f"DQE_{projet.nom.replace(' ', '_')}_{projet.id}"
        if export_format == "pdf":
            entreprise = _entreprise_export_dict(EntrepriseParametres.get_solo())
            buffer = exporter_dqe_pdf(dqe_data, entreprise=entreprise)
            response = HttpResponse(buffer.getvalue(), content_type="application/pdf")
            response["Content-Disposition"] = (
                f'attachment; filename="{nom_fichier_base}.pdf"'
            )
        elif export_format == "excel":
            entreprise = _entreprise_export_dict(EntrepriseParametres.get_solo())
            buffer = exporter_dqe_excel(dqe_data, entreprise=entreprise)
            response = HttpResponse(
                buffer.getvalue(),
                content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            )
            response["Content-Disposition"] = (
                f'attachment; filename="{nom_fichier_base}.xlsx"'
            )
        else:
            return Response(
                {"erreur": f"Format d'export invalide: {export_format}"},
                status=status.HTTP_400_BAD_REQUEST,
            )
        return response


class ElementStructurelViewSet(viewsets.ModelViewSet):
    queryset = ElementStructurel.objects.all()
    serializer_class = ElementStructurelSerializer

    @action(detail=True, methods=["post"])
    def calculer(self, request, pk=None):
        element = self.get_object()
        try:
            resultat = calculer_element(element)
        except CalculNonDisponible as exc:
            return Response(
                {"erreur": "Moteur indisponible", "detail": str(exc)},
                status=status.HTTP_503_SERVICE_UNAVAILABLE,
            )
        except EntreeInvalide as exc:
            return Response({"erreur": str(exc)}, status=status.HTTP_400_BAD_REQUEST)

        element.resultat_calcul = resultat
        element.save(update_fields=["resultat_calcul", "date_modification"])
        return Response(ElementStructurelSerializer(element).data)

    @action(detail=True, methods=["post"])
    def valider(self, request, pk=None):
        element = self.get_object()
        serializer = ElementValidationSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        resultat_valide = serializer.validated_data.get(
            "resultat_valide", element.resultat_calcul
        )
        if resultat_valide is None:
            return Response(
                {"erreur": "Aucun résultat de calcul disponible à valider."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        element.resultat_valide = resultat_valide
        element.statut = ElementStructurel.Statut.VALIDE
        element.save(update_fields=["resultat_valide", "statut", "date_modification"])
        return Response(ElementStructurelSerializer(element).data)

    def perform_update(self, serializer):
        instance = serializer.instance
        if instance.statut == ElementStructurel.Statut.VALIDE:
            serializer.save(statut=ElementStructurel.Statut.MODIFIE)
        else:
            serializer.save()


class CoucheChargeViewSet(viewsets.ModelViewSet):
    queryset = CoucheCharge.objects.all()
    serializer_class = CoucheChargeSerializer


class PosteComplementaireViewSet(viewsets.ModelViewSet):
    queryset = PosteComplementaire.objects.all()
    serializer_class = PosteComplementaireSerializer

    def perform_create(self, serializer):
        mode = serializer.validated_data.get("mode")
        type_poste = serializer.validated_data.get("type_poste")
        geometrie = serializer.validated_data.get("geometrie")

        lignes = None
        if mode == PosteComplementaire.Mode.RATIO and type_poste and geometrie:
            try:
                from moteur_calcul.formules.postes_ratio import calculer_poste_ratio

                lignes = calculer_poste_ratio(type_poste, geometrie)
            except (ImportError, ModuleNotFoundError):
                lignes = [
                    {"designation": f"Ratio {type_poste}", "quantite": 1, "pu": 1000}
                ]

        serializer.save(lignes_calculees=lignes)


class EntrepriseParametresView(APIView):
    """
    Paramètres d'en-tête (logo + coordonnées) utilisés sur les exports DQE.
    Un seul jeu de paramètres par installation (singleton) : GET le crée
    à la volée s'il n'existe pas encore, PUT/PATCH le met à jour.
    Envoyer en multipart/form-data pour inclure un fichier "logo".
    """

    parser_classes = [MultiPartParser, FormParser, JSONParser]

    def get(self, request):
        entreprise = EntrepriseParametres.get_solo()
        serializer = EntrepriseParametresSerializer(entreprise, context={"request": request})
        return Response(serializer.data)

    def put(self, request):
        return self._update(request, partial=False)

    def patch(self, request):
        return self._update(request, partial=True)

    def _update(self, request, partial):
        entreprise = EntrepriseParametres.get_solo()
        serializer = EntrepriseParametresSerializer(
            entreprise, data=request.data, partial=partial, context={"request": request}
        )
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(serializer.data)


class AssistantStructurerView(APIView):
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "assistant_structurer"

    def get_permissions(self):
        if os.getenv("DEMO_MODE", "False").lower() == "true":
            return [AllowAny()]
        return [IsAuthenticated()]

    def post(self, request):
        description = request.data.get("description", "").strip()
        if not description:
            return Response(
                {"detail": "La description du projet est requise."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        if len(description) > 1000:
            return Response(
                {"detail": "La description ne doit pas dépasser 1000 caractères."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        try:
            res = structurer_description_projet(description)
            return Response(res, status=status.HTTP_200_OK)
        except LLMServiceError as exc:
            return Response(
                {"detail": str(exc), "code": exc.code},
                status=exc.status_code,
            )
        except Exception as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)


class AssistantExpliquerView(APIView):
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "assistant_expliquer"

    def get_permissions(self):
        if os.getenv("DEMO_MODE", "False").lower() == "true":
            return [AllowAny()]
        return [IsAuthenticated()]

    def post(self, request):
        element_id = request.data.get("element_id")
        if not element_id:
            return Response(
                {"detail": "Le champ element_id est requis."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        element = get_object_or_404(ElementStructurel, id=element_id)
        if element.resultat_calcul is None:
            return Response(
                {"detail": "Cet élément n'a aucun calcul disponible à expliquer."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        try:
            elem_payload = {
                "repere": element.identifiant,
                "type_element": element.type_element,
                "parametres": {
                    "hauteur_poteau": element.hauteur_poteau,
                    "charge_calculee": element.charge_calculee,
                    "portee": element.portee,
                    "charge_lineaire": element.charge_lineaire,
                    "taux_travail_sol": element.taux_travail_sol,
                },
                "resultats": element.resultat_calcul or {},
            }
            res = expliquer_resultat_element(elem_payload)
            return Response(res, status=status.HTTP_200_OK)
        except LLMServiceError as exc:
            return Response(
                {"detail": str(exc), "code": exc.code},
                status=exc.status_code,
            )
        except Exception as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)


class AssistantSuggererPosteView(APIView):
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "assistant_suggerer_poste"

    def get_permissions(self):
        if os.getenv("DEMO_MODE", "False").lower() == "true":
            return [AllowAny()]
        return [IsAuthenticated()]

    def post(self, request):
        description = request.data.get("description", "").strip()
        if not description:
            return Response(
                {"detail": "La description du poste est requise."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        if len(description) > 500:
            return Response(
                {"detail": "La description ne doit pas dépasser 500 caractères."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        try:
            res = suggerer_poste_complementaire(description)
            return Response(res, status=status.HTTP_200_OK)
        except LLMServiceError as exc:
            return Response(
                {"detail": str(exc), "code": exc.code},
                status=exc.status_code,
            )
        except ValueError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        except Exception as exc:
            logger.exception("Erreur inattendue dans AssistantSuggererPosteView")
            return Response(
                {"detail": "Erreur interne du service d'assistance IA."},
                status=status.HTTP_502_BAD_GATEWAY,
            )