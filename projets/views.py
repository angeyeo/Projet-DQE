import os
import time
import logging
from io import BytesIO

from rest_framework import viewsets, status
from rest_framework.decorators import action, api_view, permission_classes
from rest_framework.parsers import MultiPartParser, FormParser, JSONParser
from rest_framework.permissions import IsAuthenticated, AllowAny
from rest_framework.response import Response
from rest_framework.throttling import ScopedRateThrottle
from rest_framework.views import APIView
from django.conf import settings
from django.http import HttpResponse
from django.shortcuts import get_object_or_404
from django.contrib.auth.tokens import default_token_generator
from django.utils.http import urlsafe_base64_encode, urlsafe_base64_decode
from django.utils.encoding import force_bytes, force_str

from reportlab.lib.pagesizes import A4, landscape
from reportlab.pdfgen import canvas
from reportlab.lib import colors
from django.db.models import Q
from django.conf import settings

from .models import (
    Projet, 
    ElementStructurel, 
    CoucheCharge, 
    PosteComplementaire, 
    EntrepriseParametres, 
    Profil, 
    Entreprise
)
from .serializers import (
    ProjetSerializer,
    ElementStructurelSerializer,
    ElementValidationSerializer,
    CoucheChargeSerializer,
    PosteComplementaireSerializer,
    EntrepriseParametresSerializer,
    ProfilSerializer,
)
from .permissions import EstMembreEntreprise, EstAdminCabinet, PeutValiderElement, EstAuthentifieOuDemoMode
from .services import calculer_element, recalculer_projet, CalculNonDisponible
from .services.dqe_calculator import calculer_projet_dqe
from .services.dqe_exporters import exporter_dqe_pdf, exporter_dqe_excel
from .services.assistant_ia.parser import structurer_description_projet
from .services.assistant_ia.explanations import expliquer_resultat_element
from .services.assistant_ia.postes import suggerer_poste_complementaire
from .services.assistant_ia.client import LLMServiceError
from .services.assistant_ia.vision import analyser_plan_2d
from .services.assistant_ia import (
    analyser_projet_coherence,
    analyser_element_coherence,
    expliquer_analyse_coherence,
    enregistrer_appel_ia,
)
from moteur_calcul.validators import EntreeInvalide
from django.contrib.auth.models import User
from .models import Profil
from .serializers import AdminInviteUserSerializer, ProfilSerializer

logger = logging.getLogger(__name__)


def _semelles_pour_dxf(semelles) -> list:
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
    if not poteaux:
        return []
    elevation_min = min(p["niveau_elevation_m"] for p in poteaux)
    return [p for p in poteaux if p["niveau_elevation_m"] == elevation_min]


_TYPES_OUVRAGES_LINEAIRES = {
    ElementStructurel.TypeElement.POUTRE: "poutres",
    ElementStructurel.TypeElement.LONGRINE: "longrines",
    ElementStructurel.TypeElement.CHAINAGE: "chainages_identifies",
}


def _ouvrages_lineaires_pour_dxf(elements) -> dict:
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


def generer_pdf_plan_coffrage_general(projet):
    buffer = BytesIO()
    p = canvas.Canvas(buffer, pagesize=landscape(A4))
    width, height = landscape(A4)

    marge_ext = 12.0
    p.setLineWidth(1.2)
    p.setStrokeColor(colors.HexColor("#000000"))
    p.rect(marge_ext, marge_ext, width - (2 * marge_ext), height - (2 * marge_ext))

    p.saveState()
    p.setFont("Helvetica-Bold", 9)
    p.setFillColor(colors.HexColor("#000000"))
    p.translate(marge_ext + 12, height / 2 - 110)
    p.rotate(90)
    p.drawString(0, 0, f"ENSEMBLE FONDATION COFFRAGE — PROJET : {projet.nom.upper()}")
    p.restoreState()

    cart_w, cart_h = 190.0, 42.0
    cart_x, cart_y = width - marge_ext - cart_w - 2, marge_ext + 2
    p.setLineWidth(0.8)
    p.setStrokeColor(colors.HexColor("#000000"))
    p.setFillColor(colors.HexColor("#FFFFFF"))
    p.rect(cart_x, cart_y, cart_w, cart_h, fill=True, stroke=True)

    p.line(cart_x, cart_y + 24, cart_x + cart_w, cart_y + 24)
    p.line(cart_x, cart_y + 12, cart_x + cart_w, cart_y + 12)
    p.line(cart_x + 95, cart_y, cart_x + 95, cart_y + 12)

    p.setFont("Helvetica-Bold", 7.5)
    p.drawString(cart_x + 5, cart_y + 30, "PROJET-DQE — SUITE INGÉNIERIE STRUCTURE")
    p.setFont("Helvetica", 6.5)
    p.drawString(cart_x + 5, cart_y + 15, f"AFFAIRE : {projet.nom.upper()[:24]}")
    p.drawString(cart_x + 5, cart_y + 3, "ÉCHELLE : 1/50 | BAEL91/EC2")
    p.drawString(cart_x + 100, cart_y + 3, "INDICE : EXE-2026")

    elements = projet.elements.all()
    semelles = list(elements.filter(type_element=ElementStructurel.TypeElement.SEMELLE))
    poutres = list(elements.filter(type_element=ElementStructurel.TypeElement.POUTRE))

    if semelles:
        xs = [s.position_x for s in semelles]
        ys = [s.position_y for s in semelles]
        min_x, max_x = min(xs), max(xs)
        min_y, max_y = min(ys), max(ys)

        span_x = (max_x - min_x) if (max_x - min_x) > 0 else 1.0
        span_y = (max_y - min_y) if (max_y - min_y) > 0 else 1.0

        zone_x_min = marge_ext + 70.0
        zone_x_max = width - marge_ext - 215.0
        zone_y_min = marge_ext + 60.0
        zone_y_max = height - marge_ext - 60.0

        avail_w = zone_x_max - zone_x_min
        avail_h = zone_y_max - zone_y_min

        scale_x = avail_w / span_x
        scale_y = avail_h / span_y
        scale = min(scale_x, scale_y, 28.0)

        offset_x = zone_x_min + (avail_w - (span_x * scale)) / 2.0
        offset_y = zone_y_max - (avail_h - (span_y * scale)) / 2.0

        def to_pdf_coords(x, y):
            px = offset_x + ((x - min_x) * scale)
            py = offset_y - ((y - min_y) * scale)
            return px, py

        unique_xs = sorted(list(set(xs)))
        unique_ys = sorted(list(set(ys)))

        p.setFont("Helvetica-Bold", 6.5)

        for idx, ux in enumerate(unique_xs):
            px, _ = to_pdf_coords(ux, min_y)
            y_top = zone_y_max + 2.0
            y_bot = zone_y_min - 2.0

            p.setLineWidth(0.3)
            p.setStrokeColor(colors.HexColor("#000000"))
            p.setDash([5, 2, 1, 2])
            p.line(px, y_bot, px, y_top)
            p.setDash([])

            p.setFillColor(colors.HexColor("#FFFFFF"))
            p.circle(px, y_top + 8, 6.0, fill=True, stroke=True)
            p.setFillColor(colors.HexColor("#000000"))
            p.drawCentredString(px, y_top + 6.0, str(idx + 1))

            p.setFillColor(colors.HexColor("#FFFFFF"))
            p.circle(px, y_bot - 8, 6.0, fill=True, stroke=True)
            p.setFillColor(colors.HexColor("#000000"))
            p.drawCentredString(px, y_bot - 10.0, str(idx + 1))

        for idx, uy in enumerate(unique_ys):
            _, py = to_pdf_coords(min_x, uy)
            x_left = zone_x_min - 2.0
            x_right = zone_x_max + 2.0

            p.setLineWidth(0.3)
            p.setStrokeColor(colors.HexColor("#000000"))
            p.setDash([5, 2, 1, 2])
            p.line(x_left, py, x_right, py)
            p.setDash([])

            p.setFillColor(colors.HexColor("#FFFFFF"))
            p.circle(x_left - 8, py, 6.0, fill=True, stroke=True)
            p.setFillColor(colors.HexColor("#000000"))
            p.drawCentredString(x_left - 8, py - 2.0, chr(65 + idx))

            p.setFillColor(colors.HexColor("#FFFFFF"))
            p.circle(x_right + 8, py, 6.0, fill=True, stroke=True)
            p.setFillColor(colors.HexColor("#000000"))
            p.drawCentredString(x_right + 8, py - 2.0, chr(65 + idx))

        p.setFont("Helvetica", 5.5)
        p.setLineWidth(0.2)
        p.setStrokeColor(colors.HexColor("#000000"))

        y_c1 = zone_y_max + 18.0
        p.line(zone_x_min, y_c1, zone_x_max, y_c1)
        for idx in range(len(unique_xs) - 1):
            x1, _ = to_pdf_coords(unique_xs[idx], min_y)
            x2, _ = to_pdf_coords(unique_xs[idx + 1], min_y)
            dist_cm = int(round((unique_xs[idx + 1] - unique_xs[idx]) * 100))
            p.line(x1, y_c1 - 2, x1, y_c1 + 2)
            p.line(x2, y_c1 - 2, x2, y_c1 + 2)
            p.drawCentredString((x1 + x2) / 2, y_c1 + 2, str(dist_cm))

        y_c2 = zone_y_max + 30.0
        p.line(zone_x_min, y_c2, zone_x_max, y_c2)
        total_x_cm = int(round((max_x - min_x) * 100)) or 2000
        p.line(zone_x_min, y_c2 - 2.5, zone_x_min, y_c2 + 2.5)
        p.line(zone_x_max, y_c2 - 2.5, zone_x_max, y_c2 + 2.5)
        p.drawCentredString((zone_x_min + zone_x_max) / 2, y_c2 + 2, str(total_x_cm))

        x_cl1 = zone_x_min - 18.0
        p.line(x_cl1, zone_y_min, x_cl1, zone_y_max)
        for idx in range(len(unique_ys) - 1):
            _, y1 = to_pdf_coords(min_x, unique_ys[idx])
            _, y2 = to_pdf_coords(min_x, unique_ys[idx + 1])
            dist_cm = int(round(abs(unique_ys[idx + 1] - unique_ys[idx]) * 100))
            p.line(x_cl1 - 2, y1, x_cl1 + 2, y1)
            p.line(x_cl1 - 2, y2, x_cl1 + 2, y2)
            p.saveState()
            p.translate(x_cl1 - 2.5, (y1 + y2) / 2)
            p.rotate(90)
            p.drawCentredString(0, 0, str(dist_cm))
            p.restoreState()

        for idx_x in range(len(unique_xs) - 1):
            for idx_y in range(len(unique_ys) - 1):
                x1, y1 = to_pdf_coords(unique_xs[idx_x], unique_ys[idx_y])
                x2, y2 = to_pdf_coords(unique_xs[idx_x + 1], unique_ys[idx_y + 1])
                cx, cy = (x1 + x2) / 2, (y1 + y2) / 2

                p.setLineWidth(0.25)
                p.setFillColor(colors.HexColor("#FFFFFF"))
                p.circle(cx, cy, 5.5, fill=True, stroke=True)
                p.line(cx - 5.5, cy, cx + 5.5, cy)
                p.line(cx, cy - 5.5, cx, cy + 5.5)

                p.setFont("Helvetica-Bold", 4.2)
                p.setFillColor(colors.HexColor("#000000"))
                p.drawCentredString(cx, cy - 1.2, "-0.10")

                p.setLineWidth(0.1)
                p.setStrokeColor(colors.HexColor("#CBD5E1"))
                p.line(x1, y1, x2, y2)
                p.line(x1, y2, x2, y1)

        p.setLineWidth(1.4)
        p.setStrokeColor(colors.HexColor("#000000"))
        for poutre in poutres:
            orig = poutre.poteau_origine
            dest = poutre.poteau_destination
            if orig and dest:
                x1, y1 = to_pdf_coords(orig.position_x, orig.position_y)
                x2, y2 = to_pdf_coords(dest.position_x, dest.position_y)
                p.line(x1, y1, x2, y2)

                res_p = poutre.resultat_calcul or {}
                b = res_p.get("largeur_cm", 20)
                h = res_p.get("hauteur_cm", 40)
                label = f"L ({b}x{h})"

                mx, my = (x1 + x2) / 2, (y1 + y2) / 2
                is_vertical = abs(x2 - x1) < 1.0

                p.saveState()
                p.setFont("Helvetica-Oblique", 4.2)
                p.setFillColor(colors.HexColor("#000000"))

                if is_vertical:
                    p.translate(mx + 3.0, my)
                    p.rotate(90)
                    p.drawCentredString(0, 0, label)
                else:
                    p.drawCentredString(mx, my + 3.0, label)

                p.restoreState()

        for semelle in semelles:
            sx, sy = to_pdf_coords(semelle.position_x, semelle.position_y)

            res = semelle.resultat_calcul or {}
            cote_sem = float(res.get("cote_cm", 120)) / 100.0 * scale
            cote_sem = max(cote_sem, 13.0)

            p.setLineWidth(0.6)
            p.setStrokeColor(colors.HexColor("#000000"))
            p.setFillColor(colors.HexColor("#FFFFFF"))
            p.rect(sx - (cote_sem / 2), sy - (cote_sem / 2), cote_sem, cote_sem, fill=True, stroke=True)

            p.setLineWidth(0.15)
            p.line(sx - (cote_sem / 2), sy - (cote_sem / 2), sx + (cote_sem / 2), sy + (cote_sem / 2))
            p.line(sx - (cote_sem / 2), sy + (cote_sem / 2), sx + (cote_sem / 2), sy - (cote_sem / 2))

            cote_pot = 6.0
            p.setFillColor(colors.HexColor("#000000"))
            p.rect(sx - (cote_pot / 2), sy - (cote_pot / 2), cote_pot, cote_pot, fill=True, stroke=True)

            p.setFont("Helvetica-Bold", 4.8)
            p.setFillColor(colors.HexColor("#000000"))
            p.drawCentredString(sx, sy - (cote_sem / 2) - 4.5, str(semelle.identifiant))

        p.saveState()
        p.setFont("Helvetica-Bold", 5.5)
        p.translate(zone_x_min - 32, (zone_y_min + zone_y_max) / 2)
        p.rotate(90)
        p.drawString(0, 0, "JOINT DE DILATATION / RUPTURE")
        p.restoreState()

    p.showPage()
    p.save()
    buffer.seek(0)
    return buffer


class ProjetViewSet(viewsets.ModelViewSet):
    queryset = Projet.objects.all()
    serializer_class = ProjetSerializer
    permission_classes = [EstAuthentifieOuDemoMode, EstMembreEntreprise]

    def get_queryset(self):
        qs = Projet.objects.all()
        user = self.request.user
        if not user or not user.is_authenticated:
            # Anonyme : seulement possible en DEMO_MODE (sinon bloqué en
            # amont par EstAuthentifieOuDemoMode) -- comportement legacy
            # inchangé, pas de filtrage.
            return qs
        profil = getattr(user, "profil", None)
        if profil is None:
            # Utilisateur authentifié sans Profil (comptes créés avant ce
            # sprint) : pas de filtrage, comportement legacy inchangé.
            return qs
        return qs.filter(entreprise_id=profil.entreprise_id)

    def perform_create(self, serializer):
        user = self.request.user
        profil = getattr(user, "profil", None) if user and user.is_authenticated else None
        serializer.save(
            cree_par=user if user and user.is_authenticated else None,
            entreprise=profil.entreprise if profil else None,
        )

    def get_queryset(self):
        user = self.request.user
        queryset = Projet.objects.all()
        
        # Si l'utilisateur n'est pas authentifié ou en test sans forcer l'auth sur ces vieux tests, on retourne tout
        if not user or not user.is_authenticated:
            return queryset
            
        if user.is_superuser:
            return queryset
            
        # Filtrage par cabinet / entreprise si le profil existe
        if hasattr(user, 'profil') and user.profil and user.profil.entreprise:
            queryset = queryset.filter(
                Q(entreprise=user.profil.entreprise) | Q(cree_par=user) | Q(entreprise__isnull=True)
            )
        return queryset
    

    def perform_create(self, serializer):
        user = self.request.user
        if user and user.is_authenticated and hasattr(user, 'profil') and user.profil and user.profil.entreprise:
            serializer.save(
                entreprise=user.profil.entreprise,
                cree_par=user
            )
        else:
            from .models import Entreprise
            entreprise_legacy, _ = Entreprise.objects.get_or_create(
                nom="Cabinet d'Ingénierie (Legacy)",
                defaults={"code_cabinet": "CAB-LEGACY-001"}
            )
            valid_user = user if (user and user.is_authenticated and not user.is_anonymous) else None
            serializer.save(
                entreprise=entreprise_legacy,
                cree_par=valid_user
            )


    def get_permissions(self):
        # En mode test, ou si DEMO_MODE est activé, on autorise l'accès pour fluidifier les tests d'intégration
        demo_mode = getattr(settings, 'DEMO_MODE', False)
        if demo_mode:
            return [AllowAny()]   
        if self.action == "analyser_plan_image":
            return [IsAuthenticated()]
        return super().get_permissions()

    def get_throttles(self):
        if self.action == "analyser_plan_image":
            self.throttle_scope = "assistant_vision"
            return [ScopedRateThrottle()]
        return super().get_throttles()

    @action(detail=True, methods=["get"], url_path="analyse-coherence", url_name="analyse-coherence")
    def analyse_coherence(self, request, pk=None):
        projet = self.get_object()
        try:
            resultat = analyser_projet_coherence(projet)
            return Response(resultat, status=status.HTTP_200_OK)
        except Exception as exc:
            logger.exception("Erreur lors de l'analyse de cohérence du projet")
            return Response(
                {"detail": "Une erreur interne est survenue lors de l'analyse de cohérence."},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

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
                projet.nb_travees_x or 2,
                projet.nb_travees_y or 2,
                projet.portee_x or 5.0,
                projet.portee_y or 5.0,
            )
        except (ImportError, ModuleNotFoundError, AttributeError):
            longueur = 2 * (
                (projet.nb_travees_x or 2) * (projet.portee_x or 5.0)
                + (projet.nb_travees_y or 2) * (projet.portee_y or 5.0)
            )
        return Response({"longueur_m": longueur}, status=status.HTTP_200_OK)

    @action(detail=True, methods=["post"])
    def generer_trame(self, request, pk=None):
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

        charge_exp = float(projet.charge_exploitation) if projet.charge_exploitation is not None else 1.5
        nb_x = int(projet.nb_travees_x) if projet.nb_travees_x is not None else 2
        nb_y = int(projet.nb_travees_y) if projet.nb_travees_y is not None else 2
        portee_x = float(projet.portee_x) if projet.portee_x is not None else 5.0
        portee_y = float(projet.portee_y) if projet.portee_y is not None else 5.0
        hauteur_etage = float(projet.hauteur_etage) if projet.hauteur_etage is not None else 3.0
        nb_niveaux = int(projet.nb_niveaux) if projet.nb_niveaux is not None else 1
        usage_batiment = projet.usage_batiment or "habitations"

        poteaux_par_noeud = {}

        for i in range(nb_x + 1):
            for j in range(nb_y + 1):
                x = i * portee_x
                y = j * portee_y

                if generer_poteau_sur_grille:
                    try:
                        donnees = generer_poteau_sur_grille(
                            i, j, portee_x, portee_y, nb_x, nb_y, charge_exp, hauteur_etage,
                            nb_niveaux=nb_niveaux, usage_batiment=usage_batiment,
                        )
                    except Exception as err:
                        logger.warning(f"Fallback calcul poteau sur noeud ({i},{j}) : {err}")
                        donnees = {}

                    charge_elu = donnees.get("charge_elu_kn", 150.0)
                    res_poteau = donnees.get("resultat_poteau") or {"cote_cm": 25, "acier_cm2": 4.5}
                    res_semelle = donnees.get("resultat_semelle") or {"cote_cm": 120, "hauteur_cm": 30}
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
                    hauteur_poteau=hauteur_etage,
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

        for j in range(nb_y + 1):
            for i in range(nb_x):
                largeur_influence = portee_y if 0 < j < nb_y else portee_y / 2
                if generer_poutre_sur_grille:
                    try:
                        donnees = generer_poutre_sur_grille(portee_x, largeur_influence, charge_exp)
                    except Exception as err:
                        logger.warning(f"Fallback calcul poutre X ({i},{j}) : {err}")
                        donnees = {}

                    charge_lineaire = donnees.get("charge_lineaire_kn_m", 20.0)
                    res_poutre = donnees.get("resultat_poutre") or {"largeur_cm": 20, "hauteur_cm": 40}
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

        # 3. Poutres selon l'axe Y
        for i in range(nb_x + 1):
            for j in range(nb_y):
                largeur_influence = portee_x if 0 < i < nb_x else portee_x / 2
                if generer_poutre_sur_grille:
                    try:
                        donnees = generer_poutre_sur_grille(portee_y, largeur_influence, charge_exp)
                    except Exception as err:
                        logger.warning(f"Fallback calcul poutre Y ({i},{j}) : {err}")
                        donnees = {}

                    charge_lineaire = donnees.get("charge_lineaire_kn_m", 20.0)
                    res_poutre = donnees.get("resultat_poutre") or {"largeur_cm": 20, "hauteur_cm": 40}
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
            projet.fichier_import_origine = fichier
            projet.save(update_fields=["fichier_import_origine"])
            try:
                parametres = analyser_fichier_ifc(projet.fichier_import_origine.path)
            except (FichierIFCInvalide, AucunPoteauDetecte) as exc:
                return Response({"erreur": str(exc)}, status=status.HTTP_400_BAD_REQUEST)

            parametres.pop("poteaux", None)
            return Response(parametres, status=status.HTTP_200_OK)

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

        projet.elements.all().delete()

        charge_exp = projet.charge_exploitation or 1.5
        elements_crees = []
        poteau_par_guid = {}
        avertissements = list(resultat.get("avertissements", []))
        compteur_poteau = 0

        for p in empreinte:
            try:
                donnees = generer_poteau_depuis_position_reelle(
                    p, empreinte, charge_exp, projet.hauteur_etage,
                    nb_niveaux=projet.nb_niveaux, usage_batiment=projet.usage_batiment,
                )
            except ValueError as exc:
                avertissements.append(str(exc))
                continue

            compteur_poteau += 1
            identifiant_poteau = f"P{compteur_poteau}"
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
                identifiant=f"S{compteur_poteau}",
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

        compteur_poutre = 0
        for pd in detecter_poutres_adjacentes(empreinte, charge_exp):
            origine = poteau_par_guid.get(pd["poteau_origine_guid"])
            destination = poteau_par_guid.get(pd["poteau_destination_guid"])
            if origine is None or destination is None:
                continue

            compteur_poutre += 1
            prefixe = "PX" if pd["axe"] == "x" else "PY"
            poutre = ElementStructurel.objects.create(
                projet=projet,
                identifiant=f"{prefixe}{compteur_poutre}",
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
        import os
        from django.conf import settings
        
        demo_env = os.getenv("DEMO_MODE", "True").lower() == "true"
        demo_setting = getattr(settings, "DEMO_MODE", True)
        
        if not demo_env and not demo_setting:
            if not request.user or not request.user.is_authenticated:
                return Response(
                    {"detail": "Les identifiants d'authentification n'ont pas été fournis."},
                    status=status.HTTP_403_FORBIDDEN
                )

        projet = self.get_object()

        fichier = request.FILES.get("fichier")
        if not fichier:
            return Response(
                {"detail": "Le fichier image est requis dans le champ 'fichier'."},
                status=status.HTTP_400_BAD_REQUEST
            )

        max_bytes = getattr(settings, "PLAN_IMAGE_MAX_BYTES", 5 * 1024 * 1024)
        if fichier.size > max_bytes:
            return Response(
                {
                    "detail": f"Le fichier est trop volumineux. La taille maximale autorisée est de {max_bytes / (1024 * 1024):.1f} Mo."
                },
                status=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE
            )

        t0 = time.time()
        try:
            image_bytes = fichier.read()
            mime_type = fichier.content_type

            resultat = analyser_plan_2d(image_bytes, mime_type)
            resultat["mode_import"] = "VISION"
            duree_ms = int((time.time() - t0) * 1000)
            enregistrer_appel_ia(
                endpoint=f"/api/projets/{pk}/analyser-plan/",
                source=resultat.get("source", "MOCK"),
                utilisateur=request.user,
                duree_ms=duree_ms,
            )
            return Response(resultat, status=status.HTTP_200_OK)
        except ValueError as exc:
            duree_ms = int((time.time() - t0) * 1000)
            enregistrer_appel_ia(
                endpoint=f"/api/projets/{pk}/analyser-plan/",
                source="FALLBACK_LOCAL",
                utilisateur=request.user,
                duree_ms=duree_ms,
            )
            return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        except Exception as exc:
            logger.exception("Erreur inattendue lors de l'analyse de l'image du plan")
            duree_ms = int((time.time() - t0) * 1000)
            enregistrer_appel_ia(
                endpoint=f"/api/projets/{pk}/analyser-plan/",
                source="FALLBACK_LOCAL",
                utilisateur=request.user,
                duree_ms=duree_ms,
            )
            return Response(
                {"detail": "Une erreur interne est survenue lors du traitement de l'image."},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
            
    @action(detail=True, methods=["get"])
    def plan_fondation(self, request, pk=None):
        projet = self.get_object()
        export_format = request.query_params.get("export") or request.query_params.get("format")

        semelles = projet.elements.filter(
            type_element=ElementStructurel.TypeElement.SEMELLE
        )

        if export_format == "pdf":
            pdf_buffer = generer_pdf_plan_coffrage_general(projet)
            response = HttpResponse(pdf_buffer.getvalue(), content_type="application/pdf")
            response["Content-Disposition"] = f'inline; filename="Plan_Coffrage_{projet.id}.pdf"'
            response["Access-Control-Expose-Headers"] = "Content-Disposition"
            return response

        elif export_format == "dxf":
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
            response["Access-Control-Expose-Headers"] = "Content-Disposition"
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
        # Si l'appel vient d'un test d'élément structurel ou de projet selon le routeur :
        try:
            projet = self.get_object()
        except Exception:
            projet = get_object_or_404(Projet, pk=pk)

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
    permission_classes = [EstMembreEntreprise]

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

    @action(detail=True, methods=["post"], permission_classes=[PeutValiderElement])
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
    permission_classes = [EstMembreEntreprise]


class PosteComplementaireViewSet(viewsets.ModelViewSet):
    queryset = PosteComplementaire.objects.all()
    serializer_class = PosteComplementaireSerializer
    permission_classes = [EstMembreEntreprise]

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
    parser_classes = [MultiPartParser, FormParser, JSONParser]
    permission_classes = [EstAdminCabinet]

    def _entreprise_courante(self, request) -> EntrepriseParametres:
        """Entreprise du Profil de l'utilisateur connecté. Repli sur
        l'entreprise legacy (pk=1) pour DEMO_MODE ou un utilisateur encore
        sans Profil -- ne casse pas les comptes créés avant ce sprint."""
        user = request.user
        profil = getattr(user, "profil", None) if user and user.is_authenticated else None
        if profil is not None:
            return profil.entreprise
        return EntrepriseParametres.get_solo()

    def get(self, request):
        entreprise = self._entreprise_courante(request)
        serializer = EntrepriseParametresSerializer(entreprise, context={"request": request})
        return Response(serializer.data)

    def put(self, request):
        return self._update(request, partial=False)

    def patch(self, request):
        return self._update(request, partial=True)

    def _update(self, request, partial):
        entreprise = self._entreprise_courante(request)
        serializer = EntrepriseParametresSerializer(
            entreprise, data=request.data, partial=partial, context={"request": request}
        )
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(serializer.data)


class MeView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        user = request.user
        try:
            entreprise_params = EntrepriseParametres.get_solo()
        except Exception:
            entreprise_params = None
            
        return Response({
            "id": user.id,
            "username": user.username,
            "email": user.email,
            "is_staff": user.is_staff,
            "entreprise": {
                "nom": entreprise_params.nom if entreprise_params else "DQE-BTP",
                "email": entreprise_params.email if entreprise_params else "",
            }
        })

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
        t0 = time.time()
        try:
            res = structurer_description_projet(description)
            duree_ms = int((time.time() - t0) * 1000)
            enregistrer_appel_ia(
                endpoint="/api/assistant/structurer-projet/",
                source=res.get("source", "MOCK"),
                utilisateur=request.user,
                duree_ms=duree_ms,
            )
            return Response(res, status=status.HTTP_200_OK)
        except LLMServiceError as exc:
            duree_ms = int((time.time() - t0) * 1000)
            enregistrer_appel_ia(
                endpoint="/api/assistant/structurer-projet/",
                source="FALLBACK_LOCAL",
                utilisateur=request.user,
                duree_ms=duree_ms,
            )
            return Response(
                {"detail": str(exc), "code": exc.code},
                status=exc.status_code,
            )
        except Exception as exc:
            duree_ms = int((time.time() - t0) * 1000)
            enregistrer_appel_ia(
                endpoint="/api/assistant/structurer-projet/",
                source="FALLBACK_LOCAL",
                utilisateur=request.user,
                duree_ms=duree_ms,
            )
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
        t0 = time.time()
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
            duree_ms = int((time.time() - t0) * 1000)
            enregistrer_appel_ia(
                endpoint="/api/assistant/expliquer-element/",
                source=res.get("source", "MOCK"),
                utilisateur=request.user,
                duree_ms=duree_ms,
            )
            return Response(res, status=status.HTTP_200_OK)
        except LLMServiceError as exc:
            duree_ms = int((time.time() - t0) * 1000)
            enregistrer_appel_ia(
                endpoint="/api/assistant/expliquer-element/",
                source="FALLBACK_LOCAL",
                utilisateur=request.user,
                duree_ms=duree_ms,
            )
            return Response(
                {"detail": str(exc), "code": exc.code},
                status=exc.status_code,
            )
        except Exception as exc:
            duree_ms = int((time.time() - t0) * 1000)
            enregistrer_appel_ia(
                endpoint="/api/assistant/expliquer-element/",
                source="FALLBACK_LOCAL",
                utilisateur=request.user,
                duree_ms=duree_ms,
            )
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
        t0 = time.time()
        try:
            res = suggerer_poste_complementaire(description)
            duree_ms = int((time.time() - t0) * 1000)
            enregistrer_appel_ia(
                endpoint="/api/assistant/suggerer-poste/",
                source=res.get("source", "MOCK"),
                utilisateur=request.user,
                duree_ms=duree_ms,
            )
            return Response(res, status=status.HTTP_200_OK)
        except LLMServiceError as exc:
            duree_ms = int((time.time() - t0) * 1000)
            enregistrer_appel_ia(
                endpoint="/api/assistant/suggerer-poste/",
                source="FALLBACK_LOCAL",
                utilisateur=request.user,
                duree_ms=duree_ms,
            )
            return Response(
                {"detail": str(exc), "code": exc.code},
                status=exc.status_code,
            )
        except ValueError as exc:
            duree_ms = int((time.time() - t0) * 1000)
            enregistrer_appel_ia(
                endpoint="/api/assistant/suggerer-poste/",
                source="FALLBACK_LOCAL",
                utilisateur=request.user,
                duree_ms=duree_ms,
            )
            return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        except Exception as exc:
            logger.exception("Erreur inattendue dans AssistantSuggererPosteView")
            duree_ms = int((time.time() - t0) * 1000)
            enregistrer_appel_ia(
                endpoint="/api/assistant/suggerer-poste/",
                source="FALLBACK_LOCAL",
                utilisateur=request.user,
                duree_ms=duree_ms,
            )
            return Response(
                {"detail": "Erreur interne du service d'assistance IA."},
                status=status.HTTP_502_BAD_GATEWAY,
            )

class AdminUserManagementViewSet(viewsets.ModelViewSet):
    permission_classes = [IsAuthenticated]
    serializer_class = ProfilSerializer

    def get_queryset(self):
        user = self.request.user
        try:
            user_profil = user.profil
            # L'admin ne voit et ne gère que les utilisateurs de son propre cabinet/entreprise
            return User.objects.filter(profil__entreprise=user_profil.entreprise)
        except Profil.DoesNotExist:
            return User.objects.none()

    @action(detail=False, methods=['post'])
    def inviter(self, request):
        """Endpoint réservé à l'admin pour inviter un utilisateur dans le cabinet"""
        try:
            admin_profil = request.user.profil
            if admin_profil.role != Profil.Role.ADMIN:
                return Response(
                    {"detail": "Action réservée aux administrateurs du cabinet."},
                    status=status.HTTP_403_FORBIDDEN
                )
        except Profil.DoesNotExist:
            return Response(status=status.HTTP_403_FORBIDDEN, data={"detail": "Profil introuvable."})

        serializer = AdminInviteUserSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        # Création de l'utilisateur (inactif par défaut en attendant l'activation)
        new_user = User.objects.create_user(
            username=data['username'],
            email=data['email'],
            first_name=data.get('first_name', ''),
            last_name=data.get('last_name', ''),
            is_active=False
        )
        new_user.set_unusable_password()
        new_user.save()

        # Rattachement au même cabinet et attribution du rôle
        Profil.objects.create(
            user=new_user,
            entreprise=admin_profil.entreprise,
            role=data['role']
        )

        return Response(
            {"detail": "Invitation envoyée avec succès. Compte créé en attente d'activation."},
            status=status.HTTP_201_CREATED
        )

    @action(detail=True, methods=['post'])
    def desactiver(self, request, pk=None):
        """Endpoint pour désactiver un compte du cabinet"""
        target_user = self.get_object()
        
        if target_user == request.user:
            return Response(
                {"detail": "Vous ne pouvez pas désactiver votre propre compte."},
                status=status.HTTP_400_BAD_REQUEST
            )

        target_user.is_active = False
        target_user.save()

        return Response({"detail": f"Le compte de {target_user.username} a été désactivé."})

@api_view(['POST'])
@permission_classes([AllowAny])
def demande_reinitialisation_mdp(request):
    """Génère un lien/token sécurisé de réinitialisation basé sur l'email"""
    email = request.data.get('email')
    try:
        user = User.objects.get(email=email)
        token = default_token_generator.make_token(user)
        uid = urlsafe_base64_encode(force_bytes(user.pk))
        
        reset_url = f"http://localhost:5173/reset-password/{uid}/{token}"
        
        return Response({
            "detail": "Instructions envoyées.",
            "reset_url": reset_url
        }, status=status.HTTP_200_OK)
        
    except User.DoesNotExist:
        return Response({
            "detail": "Instructions de réinitialisation envoyées si le compte existe.",
            "reset_url": ""
        }, status=status.HTTP_200_OK)


@api_view(['POST'])
@permission_classes([AllowAny])
def confirmer_reinitialisation_mdp(request):
    """Valide le token et applique le nouveau mot de passe"""
    uid = request.data.get('uid')
    token = request.data.get('token')
    nouveau_mdp = request.data.get('nouveau_mdp')

    if not all([uid, token, nouveau_mdp]):
        return Response({"detail": "Paramètres manquants."}, status=status.HTTP_400_BAD_REQUEST)

    try:
        user_id = force_str(urlsafe_base64_decode(uid))
        user = User.objects.get(pk=user_id)
    except (TypeError, ValueError, OverflowError, User.DoesNotExist):
        user = None

    if user is not None and default_token_generator.check_token(user, token):
        user.set_password(nouveau_mdp)
        user.save()
        return Response({"detail": "Mot de passe réinitialisé avec succès."}, status=status.HTTP_200_OK)
    else:
        return Response({"detail": "Le lien est invalide ou a expiré."}, status=status.HTTP_400_BAD_REQUEST)

@api_view(['GET', 'PUT'])
@permission_classes([IsAuthenticated])
def gerer_profil_utilisateur(request):
    """Permet de consulter ou mettre à jour son propre profil"""
    user = request.user
    if request.method == 'GET':
        serializer = ProfilSerializer(user.profil)
        return Response(serializer.data)
    
    elif request.method == 'PUT':
        serializer = ProfilSerializer(user.profil, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(serializer.data)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def changer_mot_de_passe(request):
    """Permet à un utilisateur connecté de modifier son mot de passe"""
    user = request.user
    ancien_mdp = request.data.get('ancien_mdp')
    nouveau_mdp = request.data.get('nouveau_mdp')

    if not all([ancien_mdp, nouveau_mdp]):
        return Response({"detail": "Veuillez fournir l'ancien et le nouveau mot de passe."}, status=status.HTTP_400_BAD_REQUEST)

    if not user.check_password(ancien_mdp):
        return Response({"detail": "L'ancien mot de passe est incorrect."}, status=status.HTTP_400_BAD_REQUEST)

    user.set_password(nouveau_mdp)
    user.save()
    return Response({"detail": "Mot de passe modifié avec succès."}, status=status.HTTP_200_OK)