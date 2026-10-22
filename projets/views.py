"""
Vues API du projet DQE.

Isolation multi-cabinet : TOUTE donnée métier est filtrée par le cabinet
de l'utilisateur connecté (Profil.entreprise). Un objet d'un autre
cabinet renvoie 404 (on ne révèle pas son existence). Il n'existe plus
de mode démo anonyme ni de repli sur une "entreprise legacy" partagée.
"""

import logging
import os
import time
from io import BytesIO

from django.db import transaction
from django.db.models import Count, Exists, OuterRef, Q
from django.http import HttpResponse
from django.utils import timezone
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4, landscape
from reportlab.pdfgen import canvas
from rest_framework import serializers as drf_serializers
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.parsers import FormParser, JSONParser, MultiPartParser
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.throttling import ScopedRateThrottle
from rest_framework.views import APIView

from moteur_calcul.constantes import (
    CHARGE_EXPLOITATION_TOITURE_KN_M2,
    G_TOITURE_CHARPENTE_KN_M2,
    POIDS_MURS_MAX_KN_M2,
    POIDS_MUR_REFERENCE_KN_M2,
    POURCENTAGE_BAIES_MAX,
    CHARGES_EXPLOITATION,
    COEFFICIENT_G_ELS,
    COEFFICIENT_G_ELU,
    COEFFICIENT_Q_ELS,
    COEFFICIENT_Q_ELU,
    CONTRAINTE_SOL_DEFAUT,
    POIDS_COUCHES_COURANTES,
)
from moteur_calcul.hypotheses import (
    CONTENU_G_FORFAITAIRE,
    G_PLANCHER_FORFAITAIRE_KN_M2,
    METHODE_SEMELLES_PAR_DEFAUT,
    POIDS_PROPRE_OSSATURE_PAR_DEFAUT,
)
from moteur_calcul.formules.postes_ratio import SCHEMA_GEOMETRIE
from moteur_calcul.validators import EntreeInvalide

from .models import (
    CoucheCharge,
    ElementStructurel,
    EvenementProduit,
    OuvrageType,
    PosteComplementaire,
    Projet,
)
from .permissions import (
    EstAdminCabinet, EstMembreEntreprise, PeutModifierBibliotheque, PeutValiderElement, entreprise_de,
)
from .serializers import (
    CoucheChargeSerializer,
    ElementStructurelSerializer,
    ElementValidationSerializer,
    EntrepriseParametresSerializer,
    OuvrageTypeSerializer,
    PosteComplementaireSerializer,
    ProjetResumeSerializer,
    ProjetSerializer,
)
from .services import CalculNonDisponible, calculer_element, recalculer_projet
from .services.assistant_ia import (
    analyser_element_coherence,
    analyser_projet_coherence,
    enregistrer_appel_ia,
    expliquer_analyse_coherence,
)
from .services.assistant_ia.client import LLMServiceError
from .services.assistant_ia.explanations import expliquer_resultat_element
from .services.assistant_ia.parser import structurer_description_projet
from .services.assistant_ia.postes import suggerer_poste_complementaire
from .services.assistant_ia.vision import analyser_plan_2d
from .services.dqe_calculator import (
    DQEIncomplet,
    LIBELLES_PRIX,
    PRIX_UNITAIRES_REFERENCE,
    TAUX_TVA_REFERENCE_PCT,
    calculer_projet_dqe,
)
from .services.approvisionnement import (
    BORNES_PARAMETRES,
    LIBELLES_PRIX_MATERIAUX,
    PARAMETRES_REFERENCE,
    PRIX_MATERIAUX_REFERENCE,
    calculer_fiche_approvisionnement,
)
from .services.dqe_exporters import exporter_approvisionnement_excel, exporter_dqe_excel, exporter_dqe_pdf
from .services.evenements import enregistrer_evenement
from .services.trame_service import creer_elements_depuis_positions, creer_elements_trame, murs_orphelins
from .services.parametres_projet import (
    MESSAGES_SOURCE_STRUCTURE, ParametresIncomplets, messages_source_structure, parametres_structure,
)

logger = logging.getLogger(__name__)

TypeEv = EvenementProduit.Type


def _nom_utilisateur(user) -> str:
    if not user or not user.is_authenticated:
        return "Utilisateur inconnu"
    return user.get_full_name() or user.username


def _reponse_parametres_incomplets(exc: ParametresIncomplets):
    return Response(
        {"erreur": str(exc), "champs_manquants": exc.manquants},
        status=status.HTTP_400_BAD_REQUEST,
    )


def _journaliser_ia(request, endpoint, source, t0, succes=True, projet=None):
    duree_ms = int((time.time() - t0) * 1000)
    enregistrer_appel_ia(endpoint=endpoint, source=source, utilisateur=request.user, duree_ms=duree_ms)
    enregistrer_evenement(
        TypeEv.APPEL_IA, utilisateur=request.user, projet=projet,
        endpoint=endpoint, source=source, succes=succes, duree_ms=duree_ms,
    )


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


def _entreprise_export_dict(entreprise) -> dict:
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


POINTS_PAR_MM = 72 / 25.4


def generer_pdf_plan_coffrage_general(projet, *, cabinet_nom, auteur, date_edition):
    """Plan d'ensemble fondation/coffrage (PDF A4 paysage).

    Le cartouche n'affiche que des données réelles : cabinet du projet,
    affaire, référence de devis, date d'édition, auteur, et l'échelle
    EFFECTIVEMENT appliquée au dessin (calculée, plus "1/50" en dur).
    Les mentions non issues des données (cote "-0.10", "joint de
    dilatation", sections par défaut 20x40 / 120 cm) ont été retirées.
    L'appelant garantit que chaque semelle a une position et un côté.
    """
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

    reference = projet.numero_devis or "non attribuée"
    p.setFont("Helvetica-Bold", 7.5)
    p.drawString(cart_x + 5, cart_y + 30, (cabinet_nom or "Cabinet non renseigné").upper()[:40])
    p.setFont("Helvetica", 6.5)
    p.drawString(cart_x + 5, cart_y + 15, f"AFFAIRE : {projet.nom.upper()[:24]}")
    p.drawString(cart_x + 100, cart_y + 15, f"RÉF. : {reference[:18]}")
    p.drawString(cart_x + 100, cart_y + 3, f"{date_edition:%d/%m/%Y} — {auteur[:14]}")

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
        # Échelle réelle du dessin : `scale` points par mètre.
        echelle = round(1000 / (scale / POINTS_PAR_MM))
        p.setFont("Helvetica", 6.5)
        p.drawString(cart_x + 5, cart_y + 3, f"ÉCHELLE : 1/{echelle} (A4 paysage)")

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
        total_x_cm = int(round((max_x - min_x) * 100))
        if total_x_cm > 0:
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

        p.setLineWidth(1.4)
        p.setStrokeColor(colors.HexColor("#000000"))
        for poutre in poutres:
            orig = poutre.poteau_origine
            dest = poutre.poteau_destination
            if orig and dest:
                x1, y1 = to_pdf_coords(orig.position_x, orig.position_y)
                x2, y2 = to_pdf_coords(dest.position_x, dest.position_y)
                p.line(x1, y1, x2, y2)

                res_p = poutre.resultat_valide or poutre.resultat_calcul or {}
                b = res_p.get("largeur_cm")
                h = res_p.get("hauteur_cm")
                label = f"{poutre.identifiant} ({b}x{h})" if b and h else f"{poutre.identifiant} (non dimensionnée)"

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

            res = semelle.resultat_valide or semelle.resultat_calcul or {}
            cote_sem = float(res["cote_cm"]) / 100.0 * scale
            cote_sem = max(cote_sem, 13.0)  # lisibilité : symbole agrandi si trop petit

            p.setLineWidth(0.6)
            p.setStrokeColor(colors.HexColor("#000000"))
            p.setFillColor(colors.HexColor("#FFFFFF"))
            p.rect(sx - (cote_sem / 2), sy - (cote_sem / 2), cote_sem, cote_sem, fill=True, stroke=True)

            p.setLineWidth(0.15)
            p.line(sx - (cote_sem / 2), sy - (cote_sem / 2), sx + (cote_sem / 2), sy + (cote_sem / 2))
            p.line(sx - (cote_sem / 2), sy + (cote_sem / 2), sx + (cote_sem / 2), sy - (cote_sem / 2))

            poteau = semelle.poteau_associe
            res_pot = (poteau.resultat_valide or poteau.resultat_calcul or {}) if poteau else {}
            cote_pot = max(float(res_pot["cote_cm"]) / 100.0 * scale, 3.0) if res_pot.get("cote_cm") else 0
            if cote_pot:
                p.setFillColor(colors.HexColor("#000000"))
                p.rect(sx - (cote_pot / 2), sy - (cote_pot / 2), cote_pot, cote_pot, fill=True, stroke=True)

            p.setFont("Helvetica-Bold", 4.8)
            p.setFillColor(colors.HexColor("#000000"))
            p.drawCentredString(sx, sy - (cote_sem / 2) - 4.5, str(semelle.identifiant))

    p.showPage()
    p.save()
    buffer.seek(0)
    return buffer






class FiltreCabinetMixin:
    """get_queryset() limité au cabinet de l'utilisateur.

    `champ_cabinet` : chemin ORM vers EntrepriseParametres depuis le modèle.
    """

    champ_cabinet = "entreprise"

    def get_queryset(self):
        entreprise = entreprise_de(self.request.user)
        if entreprise is None:
            return self.queryset.none()
        return self.queryset.filter(**{self.champ_cabinet: entreprise})


# Plans importables. ArchiCAD (.pln) et PDF ne sont pas lus : le message
# dit comment exporter, au lieu d'un dépôt qui ne fait rien.
FORMATS_PLAN = (".ifc", ".dxf", ".dwg")
TAILLE_MAX_PLAN_OCTETS = 50 * 1024 * 1024


def _extension_plan(nom):
    return os.path.splitext(nom or "")[1].lower()


def _message_format_refuse(extension):
    conseils = {
        # .pln : format fermé de Graphisoft, sans lecteur public (étude #95).
        ".pln": "Les projets ArchiCAD (.pln) ne peuvent pas être lus : c'est un format fermé. Dans ArchiCAD : "
                "Fichier > Enregistrer sous, type « IFC » (recommandé : poteaux, poutres et niveaux sont conservés) "
                "ou « DXF », puis déposez ce fichier.",
        ".pla": "Les archives ArchiCAD (.pla) ne peuvent pas être lues : exportez le projet en IFC depuis ArchiCAD.",
        ".pdf": "Les PDF ne sont pas lus : exportez le plan en IFC ou en DXF depuis votre logiciel de dessin.",
    }
    return conseils.get(extension, f"Format « {extension or 'inconnu'} » non pris en charge : plans IFC ou DXF uniquement.")


MODE_ARCHITECTE = "architecte"
NB_POTEAUX_SAISIS_MAX = 500
DISTANCE_MIN_POTEAUX_M = 0.30
COORDONNEE_MAX_M = 1000.0


# Tolérance de reconnaissance d'un poteau inchangé (arrondis d'affichage).
TOLERANCE_POTEAU_INCHANGE_M = 0.01
ORIGINE_PAR_SOURCE = {"trame": "trame", "plan": "plan", "saisie": "saisi", "mixte": ""}


def _references_poteaux(projet):
    """Poteaux actuels du projet avec leur origine (pour reconnaître ceux
    que l'ingénieur n'a pas bougés). Élément antérieur au champ d'origine :
    origine déduite de la source du projet si elle est connue, sinon vide."""
    defaut = ORIGINE_PAR_SOURCE.get(projet.source_structure, "")
    return [{"x": e.position_x, "y": e.position_y, "origine": e.origine_geometrie or defaut}
            for e in projet.elements.filter(type_element=ElementStructurel.TypeElement.POTEAU)
            if e.position_x is not None and e.position_y is not None] + list(projet.poteaux_saisis or [])


def resoudre_origines(poteaux, references):
    """Origine de chaque poteau, décidée par le SERVEUR : celle du poteau de
    référence à la même position (à 1 cm près), sinon « saisi » (ajouté ou
    déplacé par l'utilisateur)."""
    import math

    resultat = []
    for p in poteaux:
        origine = ElementStructurel.OrigineGeometrie.SAISI
        for r in references:
            try:
                rx, ry = float(r["x"]), float(r["y"])
            except (KeyError, TypeError, ValueError):
                continue
            if math.hypot(p["x"] - rx, p["y"] - ry) <= TOLERANCE_POTEAU_INCHANGE_M:
                origine = r.get("origine") or ElementStructurel.OrigineGeometrie.SAISI
                break
        resultat.append({"x": p["x"], "y": p["y"], "origine": origine})
    return resultat


def _avec_conversion(reponse, conversion):
    """Ajoute à une réponse réussie la mention d'un DWG converti (traçabilité)."""
    if conversion and reponse.status_code == 200:
        reponse.data["converti_depuis"] = "dwg"
        reponse.data["avertissements"] = [conversion] + list(reponse.data.get("avertissements", []))
    return reponse


def _est_mode_architecte(projet):
    return bool(projet.fichier_import_origine) and (projet.parametres_import or {}).get("mode") == MODE_ARCHITECTE


def valider_poteaux_saisis(brut):
    """Liste [{"x", "y"}] en mètres, validée côté serveur (le frontend
    n'est pas une frontière de sécurité). Lève ValueError avec un message
    compréhensible ; ne corrige ni n'arrondit rien en silence."""
    import math

    if not isinstance(brut, list) or not brut:
        raise ValueError("Placez au moins un poteau sur le plan avant de lancer le calcul.")
    if len(brut) > NB_POTEAUX_SAISIS_MAX:
        raise ValueError(f"{len(brut)} poteaux placés : {NB_POTEAUX_SAISIS_MAX} au maximum.")
    poteaux = []
    for i, p in enumerate(brut, start=1):
        try:
            x, y = float(p["x"]), float(p["y"])
        except (TypeError, KeyError, ValueError):
            raise ValueError(f"Poteau n° {i} : coordonnées x et y manquantes ou non numériques.") from None
        if not (math.isfinite(x) and math.isfinite(y)) or not (-COORDONNEE_MAX_M <= x <= COORDONNEE_MAX_M
                                                                 and -COORDONNEE_MAX_M <= y <= COORDONNEE_MAX_M):
            raise ValueError(f"Poteau n° {i} : coordonnées hors limites (± {COORDONNEE_MAX_M:g} m).")
        for j, q in enumerate(poteaux, start=1):
            d = math.hypot(x - q["x"], y - q["y"])
            if d < DISTANCE_MIN_POTEAUX_M:
                raise ValueError(
                    f"Poteaux n° {j} et n° {i} distants de {d * 100:.0f} cm : deux poteaux doivent être à au moins "
                    f"{DISTANCE_MIN_POTEAUX_M * 100:.0f} cm l'un de l'autre (doublon probable).")
        poteaux.append({"x": x, "y": y})
    return poteaux


class ProjetViewSet(FiltreCabinetMixin, viewsets.ModelViewSet):
    queryset = Projet.objects.all()
    serializer_class = ProjetSerializer
    permission_classes = [EstMembreEntreprise]

    def get_queryset(self):
        qs = super().get_queryset()
        if self.action == "list":
            qs = qs.select_related("cree_par").annotate(
                a_dqe=Exists(EvenementProduit.objects.filter(projet=OuterRef("pk"), type=TypeEv.DQE_GENERE)),
                nb_elements=Count("elements", distinct=True),
                nb_elements_valides=Count(
                    "elements", filter=Q(elements__statut=ElementStructurel.Statut.VALIDE), distinct=True
                ),
            ).order_by("-date_modification")
        return qs

    def get_serializer_class(self):
        if self.action == "list":
            return ProjetResumeSerializer
        return ProjetSerializer

    def perform_create(self, serializer):
        user = self.request.user
        projet = serializer.save(entreprise=user.profil.entreprise, cree_par=user)
        enregistrer_evenement(TypeEv.PROJET_CREE, utilisateur=user, projet=projet)

    def get_permissions(self):
        # Supprimer un projet (et tous ses éléments) est réservé à un
        # ingénieur ou à l'administrateur du cabinet.
        if self.action == "destroy":
            return [PeutValiderElement()]
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
            return Response(analyser_projet_coherence(projet), status=status.HTTP_200_OK)
        except Exception:
            logger.exception("Erreur lors de l'analyse de cohérence du projet %s", projet.pk)
            return Response(
                {"detail": "Une erreur interne est survenue lors de l'analyse de cohérence."},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

    @action(detail=True, methods=["post"])
    def recalculer(self, request, pk=None):
        projet = self.get_object()
        return Response(recalculer_projet(projet), status=status.HTTP_200_OK)

    @action(detail=True, methods=["get"])
    def chainage_suggere(self, request, pk=None):
        from moteur_calcul.formules.trame import calculer_longueur_chainage

        projet = self.get_object()
        manquants = [
            {"champ": c, "libelle": l} for c, l in (
                ("nb_travees_x", "nombre de travées en X"), ("nb_travees_y", "nombre de travées en Y"),
                ("portee_x", "portée en X (m)"), ("portee_y", "portée en Y (m)"),
            ) if not getattr(projet, c)
        ]
        if manquants:
            return _reponse_parametres_incomplets(ParametresIncomplets(manquants))
        longueur = calculer_longueur_chainage(
            projet.nb_travees_x, projet.nb_travees_y, projet.portee_x, projet.portee_y
        )
        return Response({"longueur_m": longueur}, status=status.HTTP_200_OK)

    @action(detail=True, methods=["post"])
    def generer_trame(self, request, pk=None):
        """Génère poteaux, semelles et poutres d'une grille régulière.

        Tout ou rien : si le moteur échoue sur un seul nœud, aucun élément
        n'est créé et les éléments existants sont conservés (transaction).
        """
        projet = self.get_object()
        try:
            prm = parametres_structure(projet, avec_grille=True)
        except ParametresIncomplets as exc:
            return _reponse_parametres_incomplets(exc)

        try:
            with transaction.atomic():
                elements_crees, hypotheses = creer_elements_trame(projet, prm)
                projet.source_structure = Projet.SourceStructure.TRAME
                projet.poteaux_saisis = []
                projet.save(update_fields=["source_structure", "poteaux_saisis"])
        except (ValueError, EntreeInvalide) as exc:
            return Response(
                {"erreur": f"Le moteur de calcul a refusé la trame : {exc}"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Rappel d'une ancienne source (saisie, mixte) calculé avant le changement : retiré.
        hypotheses = [m for m in hypotheses if not m.startswith(MESSAGES_SOURCE_STRUCTURE)]
        enregistrer_evenement(TypeEv.TRAME_GENEREE, utilisateur=request.user, projet=projet,
                              nb_elements=len(elements_crees))
        serializer = ElementStructurelSerializer(elements_crees, many=True)
        return Response(
            {"elements": serializer.data, "hypotheses": sorted(set(hypotheses))},
            status=status.HTTP_201_CREATED,
        )

    def _apercu_dxf(self, projet, plan):
        """Aperçu d'un DXF : plans détectés, et pour le plan retenu la trame
        (travées et portées moyennes pour le formulaire) et les murs du
        dessin rattachés aux poutres (PROPOSÉS, appliqués seulement si
        l'utilisateur l'accepte). Mémorise le plan retenu."""
        from moteur_calcul.formules.trame import troncons_adjacents
        from moteur_calcul.import_dxf.lecture_dxf import analyser_fichier_dxf, associer_murs_aux_poutres
        from moteur_calcul.import_ifc.lecture_ifc import detecter_parametres_trame

        resultat = analyser_fichier_dxf(projet.fichier_import_origine.path, plan=plan)
        conserve = {k: v for k, v in (projet.parametres_import or {}).items() if k == "converti_depuis"}
        projet.parametres_import = {"format": "dxf", "plan": resultat["plan_retenu"], **conserve}
        projet.save(update_fields=["parametres_import"])
        reponse = {k: resultat[k] for k in ("format", "unite", "plans", "plan_retenu", "nb_poteaux_detectes")}
        avertissements = list(resultat["avertissements"])
        if resultat["plan_retenu"]:
            trame = detecter_parametres_trame(resultat["poteaux"], avec_niveaux=False)
            avertissements += trame["avertissements"]
            reponse.update({k: trame[k] for k in ("nb_travees_x", "nb_travees_y", "portee_x", "portee_y")})
            reponse["nb_poteaux_detectes"] = len(resultat["poteaux"])
            reponse["nb_murs"] = len(resultat["murs"])
            reponse["murs_proposes"] = associer_murs_aux_poutres(
                resultat["murs"], troncons_adjacents(resultat["poteaux"]))
        reponse["avertissements"] = avertissements
        return reponse

    @action(detail=True, methods=["post"], parser_classes=[MultiPartParser, FormParser, JSONParser])
    def importer_plan(self, request, pk=None):
        projet = self.get_object()
        fichier = request.FILES.get("fichier")
        confirmer = str(request.data.get("confirmer", "")).strip().lower() in (
            "1", "true", "vrai", "oui", "yes",
        )

        plan_choisi = request.data.get("plan")
        mode_architecte = str(request.data.get("mode", "")).strip().lower() == MODE_ARCHITECTE
        if fichier is None and not confirmer and not plan_choisi:
            return Response(
                {"erreur": "Fournissez un plan IFC ou DXF (champ \"fichier\") pour un aperçu, ou "
                           "confirmer=true pour créer les éléments à partir d'un aperçu déjà réalisé."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            from moteur_calcul.import_dxf.lecture_dxf import AucunPoteauDXF, FichierDXFInvalide
            from moteur_calcul.import_ifc.lecture_ifc import (
                AucunPoteauDetecte, FichierIFCInvalide, analyser_fichier_ifc,
            )
        except ImportError as exc:
            return Response(
                {"erreur": f"Moteur d'import IFC indisponible sur ce serveur : {exc}"},
                status=status.HTTP_503_SERVICE_UNAVAILABLE,
            )

        erreurs_lecture = (FichierIFCInvalide, AucunPoteauDetecte, FichierDXFInvalide, AucunPoteauDXF)
        if fichier is not None:
            extension = _extension_plan(fichier.name)
            if extension not in FORMATS_PLAN:
                return Response({"erreur": _message_format_refuse(extension)}, status=status.HTTP_400_BAD_REQUEST)
            if fichier.size > TAILLE_MAX_PLAN_OCTETS:
                return Response(
                    {"erreur": f"Plan trop volumineux ({fichier.size / 1048576:.1f} Mo) : "
                               f"{TAILLE_MAX_PLAN_OCTETS // 1048576} Mo au maximum."},
                    status=status.HTTP_400_BAD_REQUEST)
            conversion = None
            if extension == ".dwg":
                # DWG (AutoCAD) : converti en DXF par LibreDWG si le serveur
                # l'a ; ensuite, même lecture que pour un DXF déposé.
                from django.core.files.base import ContentFile

                from moteur_calcul.import_dxf.conversion_dwg import ConversionDWGImpossible, convertir_dwg_en_dxf

                try:
                    contenu_dxf = convertir_dwg_en_dxf(fichier.read())
                except ConversionDWGImpossible as exc:
                    return Response({"erreur": str(exc)}, status=status.HTTP_400_BAD_REQUEST)
                fichier = ContentFile(contenu_dxf, name=os.path.splitext(fichier.name)[0] + ".dxf")
                extension = ".dxf"
                conversion = ("Plan DWG converti en DXF sur le serveur (GNU LibreDWG) : vérifiez l'aperçu avant "
                              "le calcul. En cas de doute, enregistrez le DXF depuis AutoCAD.")
            if mode_architecte:
                if extension != ".dxf":
                    return Response(
                        {"erreur": "Le mode « Plan d'architecte » accepte les fichiers DXF ou DWG : exportez le plan "
                                   "en DXF (en mètres, centimètres ou millimètres) depuis votre logiciel."},
                        status=status.HTTP_400_BAD_REQUEST)
                projet.fichier_import_origine = fichier
                projet.parametres_import = {"format": "dxf", "mode": MODE_ARCHITECTE,
                                            **({"converti_depuis": "dwg"} if conversion else {})}
                projet.save(update_fields=["fichier_import_origine", "parametres_import"])
                return _avec_conversion(self._reponse_fond_plan(projet), conversion)
            projet.fichier_import_origine = fichier
            projet.parametres_import = {"format": extension.lstrip("."),
                                        **({"converti_depuis": "dwg"} if conversion else {})}
            projet.save(update_fields=["fichier_import_origine", "parametres_import"])
            try:
                if extension == ".dxf":
                    return _avec_conversion(
                        Response(self._apercu_dxf(projet, plan=None), status=status.HTTP_200_OK), conversion)
                parametres = analyser_fichier_ifc(projet.fichier_import_origine.path)
            except erreurs_lecture as exc:
                return Response({"erreur": str(exc)}, status=status.HTTP_400_BAD_REQUEST)
            parametres.pop("poteaux", None)
            return Response(parametres, status=status.HTTP_200_OK)

        if not projet.fichier_import_origine:
            return Response(
                {"erreur": "Aucun plan importé au préalable pour ce projet : envoyez d'abord un fichier IFC ou DXF."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        if _est_mode_architecte(projet):
            return Response(
                {"erreur": "Ce projet utilise un plan d'architecte : la structure n'est pas lue dans le fichier. "
                           "Placez les poteaux sur le plan (placer_poteaux)."},
                status=status.HTTP_400_BAD_REQUEST)
        format_plan = _extension_plan(projet.fichier_import_origine.name)
        if plan_choisi and not confirmer:
            # Choix du plan des fondations dans un DXF à plusieurs plans.
            if format_plan != ".dxf":
                return Response({"erreur": "Le choix d'un plan ne concerne que les fichiers DXF."},
                                status=status.HTTP_400_BAD_REQUEST)
            try:
                return Response(self._apercu_dxf(projet, plan=str(plan_choisi)), status=status.HTTP_200_OK)
            except erreurs_lecture as exc:
                return Response({"erreur": str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        try:
            prm = parametres_structure(projet, avec_grille=False)
        except ParametresIncomplets as exc:
            return _reponse_parametres_incomplets(exc)
        try:
            if format_plan == ".dxf":
                from moteur_calcul.import_dxf.lecture_dxf import analyser_fichier_dxf

                plan_dxf = (projet.parametres_import or {}).get("plan")
                if not plan_dxf:
                    return Response(
                        {"erreur": "Ce DXF contient plusieurs plans : choisissez celui des fondations dans "
                                   "l'aperçu de l'import avant de lancer le calcul."},
                        status=status.HTTP_400_BAD_REQUEST)
                resultat = analyser_fichier_dxf(projet.fichier_import_origine.path, plan=plan_dxf)
                empreinte = resultat["poteaux"]
            else:
                resultat = analyser_fichier_ifc(projet.fichier_import_origine.path)
                empreinte = _empreinte_niveau_bas(resultat["poteaux"])
        except erreurs_lecture as exc:
            return Response({"erreur": str(exc)}, status=status.HTTP_400_BAD_REQUEST)

        if not empreinte:
            return Response(
                {"erreur": "Aucun poteau exploitable au niveau bas détecté dans ce plan."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        avertissements = list(resultat.get("avertissements", []))
        try:
            with transaction.atomic():
                elements_crees, hypotheses, avert_creation, troncons_non_calcules = creer_elements_depuis_positions(
                    projet, empreinte, prm, origine=ElementStructurel.OrigineGeometrie.PLAN)
        except (ValueError, EntreeInvalide) as exc:
            return Response(
                {"erreur": f"Le moteur de calcul a refusé le plan importé : {exc}"},
                status=status.HTTP_400_BAD_REQUEST,
            )
        avertissements += avert_creation
        projet.source_structure = Projet.SourceStructure.PLAN
        projet.poteaux_saisis = []
        projet.save(update_fields=["source_structure", "poteaux_saisis"])

        hypotheses.extend(murs_orphelins(prm["hyp"], elements_crees, troncons_non_calcules))
        # Rappel d'une ancienne source (saisie, mixte) calculé avant le changement : retiré.
        hypotheses = [m for m in hypotheses if not m.startswith(MESSAGES_SOURCE_STRUCTURE)]
        enregistrer_evenement(TypeEv.IMPORT_IFC, utilisateur=request.user, projet=projet,
                              nb_elements=len(elements_crees))
        serializer = ElementStructurelSerializer(elements_crees, many=True)
        return Response(
            {"elements": serializer.data, "avertissements": avertissements,
             "hypotheses": sorted(set(hypotheses))},
            status=status.HTTP_201_CREATED,
        )

    def _reponse_fond_plan(self, projet):
        from moteur_calcul.import_dxf.fond_plan import FondPlanVide, lire_fond_plan
        from moteur_calcul.import_dxf.lecture_dxf import FichierDXFInvalide

        try:
            fond = lire_fond_plan(projet.fichier_import_origine.path)
        except (FichierDXFInvalide, FondPlanVide) as exc:
            return Response({"erreur": str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        except FileNotFoundError:
            return Response({"erreur": "Le fichier du plan d'architecte n'est plus disponible sur le serveur : "
                                       "déposez-le à nouveau."}, status=status.HTTP_404_NOT_FOUND)
        return Response({"mode": MODE_ARCHITECTE, **fond}, status=status.HTTP_200_OK)

    @action(detail=True, methods=["get"])
    def fond_plan(self, request, pk=None):
        """Fond de plan d'architecte déjà déposé (affichage seulement)."""
        projet = self.get_object()
        if not _est_mode_architecte(projet):
            return Response({"erreur": "Aucun plan d'architecte n'a été déposé pour ce projet."},
                            status=status.HTTP_404_NOT_FOUND)
        return self._reponse_fond_plan(projet)

    def _structure_depuis_positions(self, projet, brut, references):
        """Valide les positions, fixe l'origine de chacune (voir
        resoudre_origines), recalcule poteaux, semelles, poutres et charges
        avec le moteur, puis enregistre la liste. Tout ou rien."""
        try:
            poteaux = resoudre_origines(valider_poteaux_saisis(brut), references)
        except ValueError as exc:
            return Response({"erreur": str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        try:
            prm = parametres_structure(projet, avec_grille=False)
        except ParametresIncomplets as exc:
            return _reponse_parametres_incomplets(exc)
        empreinte = [{**p, "guid": f"poteau-{i}", "nom": f"poteau n° {i}"} for i, p in enumerate(poteaux, start=1)]
        origines = {p["origine"] for p in poteaux}
        # Source du projet : tout saisi -> « saisie » ; tout revenu à la
        # trame ou au plan d'origine (modification annulée) -> cette source,
        # sans liste à conserver ; sinon « mixte ».
        if origines == {ElementStructurel.OrigineGeometrie.SAISI}:
            source, liste = Projet.SourceStructure.SAISIE, poteaux
        elif origines in ({"trame"}, {"plan"}):
            source, liste = origines.pop(), []
        else:
            source, liste = Projet.SourceStructure.MIXTE, poteaux
        try:
            with transaction.atomic():
                elements_crees, hypotheses, avertissements, troncons_non_calcules = creer_elements_depuis_positions(
                    projet, empreinte, prm, origine=ElementStructurel.OrigineGeometrie.SAISI)
                if not any(e.type_element == ElementStructurel.TypeElement.POTEAU for e in elements_crees):
                    raise ValueError(
                        "aucun poteau n'a pu être calculé. Chaque poteau doit avoir au moins un voisin aligné "
                        "en X et un en Y (trame en deux directions) : " + " ; ".join(avertissements[:3]))
                projet.poteaux_saisis = liste
                projet.source_structure = source
                projet.save(update_fields=["poteaux_saisis", "source_structure"])
        except (ValueError, EntreeInvalide) as exc:
            return Response({"erreur": f"Structure non créée : {exc}"}, status=status.HTTP_400_BAD_REQUEST)
        hypotheses = [m for m in hypotheses if not m.startswith(MESSAGES_SOURCE_STRUCTURE)]
        hypotheses.extend(messages_source_structure(projet))
        hypotheses.extend(murs_orphelins(prm["hyp"], elements_crees, troncons_non_calcules))
        serializer = ElementStructurelSerializer(elements_crees, many=True)
        nb_saisis = sum(1 for p in poteaux if p["origine"] == ElementStructurel.OrigineGeometrie.SAISI)
        return Response(
            {"elements": serializer.data, "avertissements": avertissements,
             "hypotheses": sorted(set(hypotheses)),
             "poteaux": {"total": len(poteaux), "saisis": nb_saisis, "conserves": len(poteaux) - nb_saisis}},
            status=status.HTTP_201_CREATED,
        )

    @action(detail=True, methods=["post"])
    def placer_poteaux(self, request, pk=None):
        """Crée la structure à partir de poteaux PLACÉS PAR L'UTILISATEUR
        (mode plan d'architecte, issue #93) : mêmes calculs que pour un plan
        importé, éléments d'origine « saisi ». Sans liste dans la requête,
        reprend les poteaux déjà enregistrés, avec leur origine (régénération
        après une modification des paramètres ou des murs).
        """
        projet = self.get_object()
        brut = request.data.get("poteaux", None) if isinstance(request.data, dict) else None
        if brut is None:
            brut = projet.poteaux_saisis
        return self._structure_depuis_positions(projet, brut, references=projet.poteaux_saisis or [])

    @action(detail=True, methods=["post"])
    def modifier_poteaux(self, request, pk=None):
        """Étape 2 (issue #94) : remplace la liste des poteaux par celle
        dessinée par l'ingénieur (ajouts, déplacements, suppressions), puis
        recalcule poutres, charges et semelles avec le moteur.

        Un poteau resté exactement à sa place garde son origine (trame ou
        plan) ; un poteau ajouté ou déplacé devient « saisi ». L'origine est
        fixée ici, jamais par le client.
        """
        projet = self.get_object()
        brut = request.data.get("poteaux", None) if isinstance(request.data, dict) else None
        if brut is None:
            return Response({"erreur": "Envoyez la liste complète des poteaux (champ « poteaux »)."},
                            status=status.HTTP_400_BAD_REQUEST)
        return self._structure_depuis_positions(projet, brut, references=_references_poteaux(projet))

    @action(detail=True, methods=["post"], parser_classes=[MultiPartParser, FormParser])
    def analyser_plan_image(self, request, pk=None):
        from django.conf import settings

        projet = self.get_object()
        fichier = request.FILES.get("fichier")
        if not fichier:
            return Response(
                {"detail": "Le fichier image est requis dans le champ 'fichier'."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        max_bytes = getattr(settings, "PLAN_IMAGE_MAX_BYTES", 5 * 1024 * 1024)
        if fichier.size > max_bytes:
            return Response(
                {"detail": f"Le fichier est trop volumineux. La taille maximale autorisée est de "
                           f"{max_bytes / (1024 * 1024):.1f} Mo."},
                status=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            )

        endpoint = f"/api/projets/{projet.pk}/analyser_plan_image/"
        t0 = time.time()
        try:
            resultat = analyser_plan_2d(fichier.read(), fichier.content_type)
            resultat["mode_import"] = "VISION"
            _journaliser_ia(request, endpoint, resultat.get("source", "INCONNUE"), t0, projet=projet)
            return Response(resultat, status=status.HTTP_200_OK)
        except LLMServiceError as exc:
            _journaliser_ia(request, endpoint, "FALLBACK_LOCAL", t0, succes=False, projet=projet)
            return Response({"detail": str(exc), "code": exc.code}, status=exc.status_code)
        except ValueError as exc:
            _journaliser_ia(request, endpoint, "FALLBACK_LOCAL", t0, succes=False, projet=projet)
            return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        except Exception:
            logger.exception("Erreur inattendue lors de l'analyse de l'image du plan")
            _journaliser_ia(request, endpoint, "FALLBACK_LOCAL", t0, succes=False, projet=projet)
            return Response(
                {"detail": "Une erreur interne est survenue lors du traitement de l'image."},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

    @action(detail=True, methods=["get"])
    def plan_fondation(self, request, pk=None):
        projet = self.get_object()
        export_format = request.query_params.get("export") or request.query_params.get("format")
        semelles = projet.elements.filter(type_element=ElementStructurel.TypeElement.SEMELLE)

        if export_format in ("pdf", "dxf"):
            if not semelles.exists():
                return Response(
                    {"erreur": "Aucune semelle disponible : impossible de générer le plan de fondation."},
                    status=status.HTTP_400_BAD_REQUEST,
                )
            incompletes = [
                s.identifiant for s in semelles
                if s.position_x is None or s.position_y is None
                or not (s.resultat_valide or s.resultat_calcul or {}).get("cote_cm")
            ]
            if incompletes:
                return Response(
                    {"erreur": "Semelles sans position ou sans dimension calculée : "
                               + ", ".join(incompletes) + ". Calculez-les avant d'exporter le plan.",
                     "elements": incompletes},
                    status=status.HTTP_400_BAD_REQUEST,
                )

        if export_format == "pdf":
            pdf_buffer = generer_pdf_plan_coffrage_general(
                projet,
                cabinet_nom=projet.entreprise.nom if projet.entreprise else "",
                auteur=_nom_utilisateur(request.user),
                date_edition=timezone.localdate(),
            )
            response = HttpResponse(pdf_buffer.getvalue(), content_type="application/pdf")
            response["Content-Disposition"] = f'inline; filename="Plan_Coffrage_{projet.id}.pdf"'
            response["Access-Control-Expose-Headers"] = "Content-Disposition"
            return response

        if export_format == "dxf":
            try:
                from projets.services.plan_fondation import generer_plan_fondation_dxf
            except ImportError as exc:
                # Avant : un DXF VIDE était renvoyé avec un code 200.
                return Response(
                    {"erreur": f"Générateur DXF indisponible sur ce serveur : {exc}"},
                    status=status.HTTP_503_SERVICE_UNAVAILABLE,
                )
            ouvrages = _ouvrages_lineaires_pour_dxf(projet.elements.all())
            try:
                content = generer_plan_fondation_dxf(
                    _semelles_pour_dxf(semelles),
                    poutres=ouvrages["poutres"],
                    longrines=ouvrages["longrines"],
                    chainages_identifies=ouvrages["chainages_identifies"],
                )
            except ValueError as err:
                return Response({"erreur": str(err)}, status=status.HTTP_400_BAD_REQUEST)
            response = HttpResponse(content, content_type="application/dxf")
            response["Content-Disposition"] = f'attachment; filename="Plan_fondation_{projet.id}.dxf"'
            response["Access-Control-Expose-Headers"] = "Content-Disposition"
            return response

        if export_format:
            return Response({"erreur": f"Format d'export invalide : {export_format}"},
                            status=status.HTTP_400_BAD_REQUEST)
        serializer = ElementStructurelSerializer(semelles, many=True)
        return Response({"semelles": serializer.data}, status=status.HTTP_200_OK)

    @action(detail=True, methods=["post"])
    def variantes(self, request, pk=None):
        """Compare des variantes (G, sol, portées, méthode des semelles...)
        recalculées par le moteur dans une transaction annulée : rien n'est
        enregistré. Résultats : totaux DQE, quantités, écarts vs projet actuel."""
        from .services.variantes import VarianteInvalide, calculer_variantes

        projet = self.get_object()
        try:
            resultats = calculer_variantes(projet, request.data.get("variantes"))
        except VarianteInvalide as exc:
            return Response({"erreur": str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        return Response({"variantes": resultats,
                         "note": "Calcul à titre de comparaison : résultats du moteur non validés par "
                                 "l'ingénieur, rien n'est enregistré."})

    @action(detail=True, methods=["post"], permission_classes=[PeutValiderElement])
    def valider_plan_fondation(self, request, pk=None):
        projet = self.get_object()
        projet.plan_fondation_valide = True
        projet.save(update_fields=["plan_fondation_valide"])
        return Response({"status": "Plan de fondation validé."}, status=status.HTTP_200_OK)

    @staticmethod
    def _dqe_ou_erreur(projet):
        """(dqe_data, None) ou (None, Response d'erreur) -- conditions communes
        au DQE et à la fiche d'approvisionnement."""
        if not projet.elements.exists() and not projet.postes_complementaires.exists():
            return None, Response(
                {"erreur": "Le projet ne contient aucun élément structurel ni poste : rien à chiffrer."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        non_valides = projet.elements.exclude(statut=ElementStructurel.Statut.VALIDE)
        if non_valides.exists():
            return None, Response(
                {"erreur": "Tous les éléments doivent être validés par un ingénieur avant le DQE.",
                 "elements_en_attente": list(non_valides.values_list("identifiant", flat=True))},
                status=status.HTTP_400_BAD_REQUEST,
            )
        # Barème du cabinet PROPRIÉTAIRE du projet, et lui seul.
        try:
            return calculer_projet_dqe(projet, prix_unitaires=projet.entreprise.get_prix_unitaires()), None
        except DQEIncomplet as exc:
            return None, Response(
                {"erreur": "Le DQE ne peut pas être généré : des données indispensables manquent.",
                 "problemes": exc.problemes},
                status=status.HTTP_400_BAD_REQUEST,
            )

    @action(detail=True, methods=["get"], url_path="approvisionnement", url_name="approvisionnement")
    def approvisionnement(self, request, pk=None):
        """Fiche d'approvisionnement (matériaux à acheter) calculée à partir du DQE."""
        projet = self.get_object()
        export_format = request.query_params.get("export")
        if export_format not in (None, "excel"):
            return Response({"erreur": f"Format d'export invalide : {export_format}"},
                            status=status.HTTP_400_BAD_REQUEST)
        dqe_data, erreur = self._dqe_ou_erreur(projet)
        if erreur is not None:
            return erreur
        cabinet = projet.entreprise
        fiche = calculer_fiche_approvisionnement(
            dqe_data, cabinet.parametres_approvisionnement, cabinet.get_prix_unitaires(),
            taux_tva_pct=cabinet.taux_tva_pct,
        )
        if export_format is None:
            return Response(fiche, status=status.HTTP_200_OK)
        fiche["projet"]["date_edition"] = timezone.localdate().isoformat()
        buffer = exporter_approvisionnement_excel(fiche, entreprise=_entreprise_export_dict(cabinet))
        response = HttpResponse(
            buffer.getvalue(),
            content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        )
        response["Content-Disposition"] = (
            f'attachment; filename="Approvisionnement_{projet.nom.replace(" ", "_")}_{projet.id}.xlsx"'
        )
        response["Access-Control-Expose-Headers"] = "Content-Disposition"
        return response

    @action(detail=True, methods=["get", "post"], url_path="generer-dqe", url_name="generer-dqe")
    def generer_dqe(self, request, pk=None):
        projet = self.get_object()
        export_format = request.query_params.get("export") or (
            request.data.get("export") if isinstance(request.data, dict) else None
        )
        dqe_data, erreur = self._dqe_ou_erreur(projet)
        if erreur is not None:
            return erreur
        if export_format not in (None, "pdf", "excel"):
            return Response({"erreur": f"Format d'export invalide : {export_format}"},
                            status=status.HTTP_400_BAD_REQUEST)

        if export_format is None:
            if not self._dqe_deja_journalise(projet, dqe_data):
                self._journaliser_dqe(request, projet, dqe_data)
            return Response(dqe_data, status=status.HTTP_200_OK)
        return self._exporter_dqe(request, projet, dqe_data, export_format)

    @staticmethod
    def _dqe_deja_journalise(projet, dqe_data):
        """Un DQE réaffiché sans aucun changement (même total, mêmes lots,
        rien de modifié depuis) n'est pas un NOUVEAU DQE : on ne le compte
        pas une seconde fois dans les analytics."""
        dernier = EvenementProduit.objects.filter(projet=projet, type=TypeEv.DQE_GENERE).order_by("-date").first()
        if dernier is None:
            return False
        lots = {l["lot"]: l["sous_total"] for l in dqe_data["lots"]}
        if dernier.donnees.get("total_general") != dqe_data["total_general"] or dernier.donnees.get("lots") != lots:
            return False
        modifie = (
            projet.elements.filter(date_modification__gt=dernier.date).exists()
            or projet.postes_complementaires.filter(date_modification__gt=dernier.date).exists()
        )
        return not modifie

    @staticmethod
    def _journaliser_dqe(request, projet, dqe_data):
        # Instantané RÉEL du DQE au moment de sa génération : seule source
        # des montants affichés par les analytics (aucune reconstitution).
        enregistrer_evenement(
            TypeEv.DQE_GENERE, utilisateur=request.user, projet=projet,
            total_general=dqe_data["total_general"], nb_lignes=len(dqe_data["lignes"]),
            sous_totaux=dqe_data["sous_totaux"],
            lots={l["lot"]: l["sous_total"] for l in dqe_data["lots"]},
            synthese=dqe_data["synthese"],
        )

    def _exporter_dqe(self, request, projet, dqe_data, export_format):
        dqe_data["projet"]["date_edition"] = timezone.localdate().isoformat()
        dqe_data["projet"]["auteur"] = _nom_utilisateur(request.user)
        if not dqe_data["projet"]["numero_devis"]:
            dqe_data["projet"]["numero_devis"] = "non attribué"
        entreprise = _entreprise_export_dict(projet.entreprise)
        nom_fichier_base = f"DQE_{projet.nom.replace(' ', '_')}_{projet.id}"
        if export_format == "pdf":
            buffer = exporter_dqe_pdf(dqe_data, entreprise=entreprise)
            response = HttpResponse(buffer.getvalue(), content_type="application/pdf")
            response["Content-Disposition"] = f'attachment; filename="{nom_fichier_base}.pdf"'
        else:
            buffer = exporter_dqe_excel(dqe_data, entreprise=entreprise)
            response = HttpResponse(
                buffer.getvalue(),
                content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            )
            response["Content-Disposition"] = f'attachment; filename="{nom_fichier_base}.xlsx"'
        response["Access-Control-Expose-Headers"] = "Content-Disposition"
        enregistrer_evenement(
            TypeEv.DQE_EXPORTE, utilisateur=request.user, projet=projet,
            format=export_format, total_general=dqe_data["total_general"],
        )
        return response


class ElementStructurelViewSet(FiltreCabinetMixin, viewsets.ModelViewSet):
    queryset = ElementStructurel.objects.select_related("projet")
    serializer_class = ElementStructurelSerializer
    permission_classes = [EstMembreEntreprise]
    champ_cabinet = "projet__entreprise"

    def get_queryset(self):
        qs = super().get_queryset()
        projet_id = self.request.query_params.get("projet")
        if projet_id:
            qs = qs.filter(projet_id=projet_id)
        return qs

    def get_throttles(self):
        if self.action == "expliquer_coherence":
            self.throttle_scope = "assistant_coherence"
            return [ScopedRateThrottle()]
        return super().get_throttles()

    @action(detail=True, methods=["post"])
    def calculer(self, request, pk=None):
        element = self.get_object()
        if element.statut == ElementStructurel.Statut.VALIDE:
            return Response(
                {"erreur": "Élément verrouillé : déverrouillez-le avant de relancer le calcul."},
                status=status.HTTP_409_CONFLICT,
            )
        try:
            resultat = calculer_element(element)
        except CalculNonDisponible as exc:
            return Response({"erreur": "Moteur indisponible", "detail": str(exc)},
                            status=status.HTTP_503_SERVICE_UNAVAILABLE)
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
        resultat_valide = serializer.validated_data.get("resultat_valide", element.resultat_calcul)
        if not resultat_valide:
            return Response({"erreur": "Aucun résultat de calcul disponible à valider."},
                            status=status.HTTP_400_BAD_REQUEST)
        element.resultat_valide = resultat_valide
        element.statut = ElementStructurel.Statut.VALIDE
        element.save(update_fields=["resultat_valide", "statut", "date_modification"])
        enregistrer_evenement(TypeEv.ELEMENT_VALIDE, utilisateur=request.user, projet=element.projet,
                              element_id=element.id)
        return Response(ElementStructurelSerializer(element).data)

    @action(detail=True, methods=["post"], permission_classes=[PeutValiderElement])
    def deverrouiller(self, request, pk=None):
        """Déverrouillage CÔTÉ SERVEUR : l'élément repasse en "modifié" et
        son résultat validé est retiré (il ne peut plus entrer au DQE tant
        qu'un ingénieur ne l'a pas revalidé)."""
        element = self.get_object()
        if element.statut != ElementStructurel.Statut.VALIDE:
            return Response({"erreur": "Cet élément n'est pas verrouillé."},
                            status=status.HTTP_409_CONFLICT)
        element.statut = ElementStructurel.Statut.MODIFIE
        element.resultat_valide = None
        element.save(update_fields=["statut", "resultat_valide", "date_modification"])
        enregistrer_evenement(TypeEv.ELEMENT_DEVERROUILLE, utilisateur=request.user,
                              projet=element.projet, element_id=element.id)
        return Response(ElementStructurelSerializer(element).data)

    @action(detail=True, methods=["post"], url_path="expliquer-coherence", url_name="expliquer-coherence")
    def expliquer_coherence(self, request, pk=None):
        element = self.get_object()  # 404 si autre cabinet
        t0 = time.time()
        analyse = analyser_element_coherence(element)
        resultat = expliquer_analyse_coherence(analyse)
        _journaliser_ia(request, f"/api/elements/{element.pk}/expliquer-coherence/",
                        resultat.get("source_explication", "LOCAL"), t0, projet=element.projet)
        return Response(resultat, status=status.HTTP_200_OK)

    def perform_update(self, serializer):
        if serializer.instance.statut == ElementStructurel.Statut.VALIDE:
            raise drf_serializers.ValidationError(
                {"statut": "Élément verrouillé : un ingénieur doit le déverrouiller avant toute modification."}
            )
        serializer.save()

    def perform_destroy(self, instance):
        if instance.statut == ElementStructurel.Statut.VALIDE:
            raise drf_serializers.ValidationError(
                {"statut": "Élément verrouillé : déverrouillez-le avant de le supprimer."}
            )
        instance.delete()


class CoucheChargeViewSet(FiltreCabinetMixin, viewsets.ModelViewSet):
    queryset = CoucheCharge.objects.all()
    serializer_class = CoucheChargeSerializer
    permission_classes = [EstMembreEntreprise]

    def get_queryset(self):
        entreprise = entreprise_de(self.request.user)
        if entreprise is None:
            return CoucheCharge.objects.none()
        return CoucheCharge.objects.filter(
            Q(projet__entreprise=entreprise) | Q(element__projet__entreprise=entreprise)
        ).distinct()


def _lignes_poste_ratio(type_poste, geometrie):
    from moteur_calcul.formules.postes_ratio import calculer_poste_ratio

    try:
        return calculer_poste_ratio(type_poste, geometrie)
    except KeyError as exc:
        raise drf_serializers.ValidationError(
            {"geometrie": f"Donnée géométrique manquante : {exc.args[0]}."}
        )
    except (ValueError, TypeError) as exc:
        raise drf_serializers.ValidationError({"geometrie": str(exc)})


class PosteComplementaireViewSet(FiltreCabinetMixin, viewsets.ModelViewSet):
    queryset = PosteComplementaire.objects.all()
    serializer_class = PosteComplementaireSerializer
    permission_classes = [EstMembreEntreprise]
    champ_cabinet = "projet__entreprise"

    def get_queryset(self):
        # Avant : ?projet=<id> était ignoré -> la liste renvoyait les
        # postes de TOUS les projets de TOUS les cabinets.
        qs = super().get_queryset()
        projet_id = self.request.query_params.get("projet")
        if projet_id:
            qs = qs.filter(projet_id=projet_id)
        return qs.order_by("id")

    def _sauver(self, serializer):
        mode = serializer.validated_data.get("mode", getattr(serializer.instance, "mode", None))
        lignes = None
        if mode == PosteComplementaire.Mode.RATIO:
            type_poste = serializer.validated_data.get("type_poste", getattr(serializer.instance, "type_poste", None))
            geometrie = serializer.validated_data.get("geometrie", getattr(serializer.instance, "geometrie", None))
            lignes = _lignes_poste_ratio(type_poste, geometrie)
        serializer.save(lignes_calculees=lignes)

    def perform_create(self, serializer):
        self._sauver(serializer)

    def perform_update(self, serializer):
        self._sauver(serializer)


class OuvrageTypeViewSet(FiltreCabinetMixin, viewsets.ModelViewSet):
    """Bibliothèque d'ouvrages du cabinet (filtres : ?lot=, ?q=)."""

    queryset = OuvrageType.objects.all()
    serializer_class = OuvrageTypeSerializer
    permission_classes = [PeutModifierBibliotheque]

    def get_queryset(self):
        qs = super().get_queryset()
        lot = self.request.query_params.get("lot")
        if lot:
            qs = qs.filter(lot=lot)
        q = (self.request.query_params.get("q") or "").strip()
        if q:
            qs = qs.filter(designation__icontains=q)
        return qs.annotate(nb_postes_annote=Count("postes")).order_by("lot", "designation")

    def perform_create(self, serializer):
        serializer.save(entreprise=entreprise_de(self.request.user), cree_par=self.request.user)

    @action(detail=False, methods=["post"], parser_classes=[MultiPartParser, FormParser])
    def importer(self, request):
        """Aperçu de l'import d'un DQE Excel : rien n'est écrit."""
        from .services.import_bibliotheque import TAILLE_MAX_OCTETS, FichierDQEInvalide, analyser_dqe_excel

        fichier = request.FILES.get("fichier")
        if fichier is None:
            return Response({"erreur": "Joignez un fichier Excel (.xlsx) dans le champ « fichier »."},
                            status=status.HTTP_400_BAD_REQUEST)
        if not fichier.name.lower().endswith(".xlsx"):
            return Response({"erreur": "Format non pris en charge : enregistrez le DQE au format Excel .xlsx."},
                            status=status.HTTP_400_BAD_REQUEST)
        if fichier.size > TAILLE_MAX_OCTETS:
            return Response({"erreur": f"Fichier trop volumineux : {TAILLE_MAX_OCTETS // 1048576} Mo au maximum."},
                            status=status.HTTP_400_BAD_REQUEST)
        existants = self.get_queryset().values_list("lot", "designation", "unite", "prix_unitaire")
        try:
            apercu = analyser_dqe_excel(fichier, existants)
        except FichierDQEInvalide as exc:
            return Response({"erreur": str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        apercu["fichier"] = fichier.name
        return Response(apercu)

    @action(detail=False, methods=["post"], url_path="importer/confirmer")
    def confirmer_import(self, request):
        """Écrit les lignes retenues dans l'aperçu : tout ou rien. Chaque
        ligne passe les mêmes validations qu'un ajout à la main."""
        lignes = request.data.get("lignes")
        if not isinstance(lignes, list) or not lignes:
            return Response({"erreur": "Aucune ligne à importer."}, status=status.HTTP_400_BAD_REQUEST)
        if len(lignes) > 2000:
            return Response({"erreur": "2 000 lignes au maximum par import."}, status=status.HTTP_400_BAD_REQUEST)
        commun = {"source_prix": str(request.data.get("source_prix") or "")[:200],
                  "date_prix": request.data.get("date_prix") or None}
        entreprise = entreprise_de(request.user)
        erreurs, crees, maj = {}, 0, 0
        with transaction.atomic():
            for i, l in enumerate(lignes):
                if not isinstance(l, dict):
                    erreurs[str(i + 1)] = "Ligne invalide."
                    continue
                donnees = {k: l.get(k) for k in ("lot", "designation", "unite", "prix_unitaire")} | commun
                instance = None
                if l.get("action") == "mettre_a_jour":
                    instance = self.get_queryset().filter(
                        lot=donnees["lot"], designation__iexact=(donnees["designation"] or "").strip(),
                        unite__iexact=(donnees["unite"] or "").strip()).first()
                    if instance is None:
                        erreurs[str(i + 1)] = f"« {donnees['designation']} » : ouvrage à mettre à jour introuvable."
                        continue
                    # Mise à jour : seul le prix (et son origine) change ; la
                    # désignation de la bibliothèque garde son écriture.
                    donnees = {"prix_unitaire": donnees["prix_unitaire"]} | commun
                s = OuvrageTypeSerializer(instance, data=donnees, partial=instance is not None,
                                          context={"request": request})
                if not s.is_valid():
                    erreurs[str(i + 1)] = f"« {donnees.get('designation') or '?'} » : " + " ".join(
                        str(m) for msgs in s.errors.values() for m in (msgs if isinstance(msgs, list) else [msgs]))
                    continue
                if instance is None:
                    s.save(entreprise=entreprise, cree_par=request.user)
                    crees += 1
                else:
                    s.save()
                    maj += 1
            if erreurs:
                transaction.set_rollback(True)
                return Response({"erreur": "Import annulé : aucune ligne n'a été écrite.", "lignes": erreurs},
                                status=status.HTTP_400_BAD_REQUEST)
        return Response({"crees": crees, "mis_a_jour": maj}, status=status.HTTP_201_CREATED)


class EntrepriseParametresView(APIView):
    """Paramètres du cabinet de l'utilisateur connecté (et de lui seul).
    Lecture : tout membre. Modification : administrateur du cabinet."""

    parser_classes = [MultiPartParser, FormParser, JSONParser]

    def get_permissions(self):
        if self.request.method in ("GET", "HEAD", "OPTIONS"):
            return [EstMembreEntreprise()]
        return [EstAdminCabinet()]

    def get(self, request):
        entreprise = request.user.profil.entreprise
        return Response(EntrepriseParametresSerializer(entreprise, context={"request": request}).data)

    def put(self, request):
        return self._update(request, partial=False)

    def patch(self, request):
        return self._update(request, partial=True)

    def _update(self, request, partial):
        serializer = EntrepriseParametresSerializer(
            request.user.profil.entreprise, data=request.data, partial=partial, context={"request": request}
        )
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(serializer.data)


class ReferentielView(APIView):
    """Référentiel technique exposé au frontend (source unique : le
    moteur). Évite toute copie locale des constantes côté React."""

    def get(self, request):
        return Response({
            "usages": [
                {"cle": cle, "libelle": cle.replace("_", " ").capitalize(), "charge_exploitation_kn_m2": v}
                for cle, v in CHARGES_EXPLOITATION.items()
            ],
            "contrainte_sol_defaut_kn_m2": CONTRAINTE_SOL_DEFAUT,
            "cles_prix": [{"cle": c, "libelle": l} for c, l in LIBELLES_PRIX.items()],
            "lots": [{"cle": c, "libelle": l} for c, l in PosteComplementaire.Lot.choices],
            "types_postes_ratio": [
                {"cle": c, "libelle": l, "geometrie": SCHEMA_GEOMETRIE[c]}
                for c, l in PosteComplementaire.TypePoste.choices
            ],
            "norme": "BAEL 91 modifié 99 (seule norme implémentée par le moteur)",
            "charges_permanentes": {
                "forfait_kn_m2": G_PLANCHER_FORFAITAIRE_KN_M2,
                "contenu_forfait": CONTENU_G_FORFAITAIRE,
                "statut_forfait": "valeur par défaut validée par le technicien BTP (07/10/2026)",
                "catalogue_couches": [
                    {"type": t, "libelle": t.replace("_", " ").capitalize(), **v}
                    for t, v in POIDS_COUCHES_COURANTES.items()
                ],
                "avertissement": "Catalogue de couches : valeurs courantes de la pratique, non validées par le "
                                 "référentiel technique -- à confirmer (moteur_calcul/constantes.py).",
            },
            "combinaisons": {
                "elu": f"{COEFFICIENT_G_ELU} G + {COEFFICIENT_Q_ELU} Q",
                "els": f"{COEFFICIENT_G_ELS:g} G + {COEFFICIENT_Q_ELS:g} Q",
            },
            "methodes_semelles": [{"cle": c, "libelle": l} for c, l in Projet.MethodeSemelles.choices],
            "charge_exploitation_toiture_kn_m2": CHARGE_EXPLOITATION_TOITURE_KN_M2,
            "types_toiture": [
                {"cle": c, "libelle": l,
                 "g_kn_m2": G_TOITURE_CHARPENTE_KN_M2 if c == "charpente" else None}
                for c, l in Projet.TypeToiture.choices
            ],
            # Aucune valeur par défaut : le poids des murs est une donnée de l'ingénieur.
            "murs": {
                "max_kn_m2": POIDS_MURS_MAX_KN_M2, "valeur_par_defaut": None,
                "baies_max_pct": POURCENTAGE_BAIES_MAX,
                # Proposée, jamais appliquée d'office : l'utilisateur la choisit.
                "reference": {
                    "valeur_kn_m2": round(POIDS_MUR_REFERENCE_KN_M2, 2),
                    "detail": "agglo de 15 creux 2,5 kN/m² + enduit ciment 2 cm × 2 faces (2 × 0,4 kN/m²)",
                    "source": "Ingénieur BTP, 12/10/2026",
                },
            },
            "defauts_projet": {
                "methode_semelles": METHODE_SEMELLES_PAR_DEFAUT,
                "inclure_poids_propre_ossature": POIDS_PROPRE_OSSATURE_PAR_DEFAUT,
            },
            # Proposé, jamais appliqué d'office : le cabinet saisit son taux.
            "taux_tva_reference_pct": TAUX_TVA_REFERENCE_PCT,
            "approvisionnement": {
                "parametres": [
                    {"cle": c, "libelle": l, "unite": u, "valeur_reference": v, "source": src,
                     "min": BORNES_PARAMETRES[c][0], "max": BORNES_PARAMETRES[c][1]}
                    for c, (v, l, u, src) in PARAMETRES_REFERENCE.items()
                ],
                "cles_prix": [{"cle": c, "libelle": l} for c, l in LIBELLES_PRIX_MATERIAUX.items()],
                "prix_reference": {
                    "source": "DQE de l'ingénieur BTP (R+1, 2026) -- sable et gravier vendus au voyage : pas de prix au m³",
                    "valeurs": PRIX_MATERIAUX_REFERENCE,
                },
            },
            "prix_reference": {
                "source": "DQE CIMBAT n°0017-2026 (villa basse 4 pièces) -- à adapter au marché du cabinet",
                "valeurs": PRIX_UNITAIRES_REFERENCE,
                "avertissements": [],
            },
        })


class MeView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        user = request.user
        entreprise = entreprise_de(user)
        profil = getattr(user, "profil", None)
        return Response({
            "id": user.id,
            "username": user.username,
            "email": user.email,
            "nom_complet": user.get_full_name(),
            "is_staff": user.is_staff,
            "role": profil.role if profil else None,
            "entreprise": (
                {"id": entreprise.id, "nom": entreprise.nom, "email": entreprise.email}
                if entreprise else None
            ),
        })


class _AssistantBase(APIView):
    throttle_classes = [ScopedRateThrottle]
    endpoint = ""

    def _executer(self, request, appel):
        t0 = time.time()
        try:
            res = appel()
            _journaliser_ia(request, self.endpoint, res.get("source", "INCONNUE"), t0)
            return Response(res, status=status.HTTP_200_OK)
        except LLMServiceError as exc:
            _journaliser_ia(request, self.endpoint, "FALLBACK_LOCAL", t0, succes=False)
            return Response({"detail": str(exc), "code": exc.code}, status=exc.status_code)
        except ValueError as exc:
            _journaliser_ia(request, self.endpoint, "FALLBACK_LOCAL", t0, succes=False)
            return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        except Exception:
            logger.exception("Erreur inattendue dans %s", self.__class__.__name__)
            _journaliser_ia(request, self.endpoint, "FALLBACK_LOCAL", t0, succes=False)
            return Response({"detail": "Erreur interne du service d'assistance IA."},
                            status=status.HTTP_502_BAD_GATEWAY)


class AssistantStructurerView(_AssistantBase):
    throttle_scope = "assistant_structurer"
    endpoint = "/api/assistant/structurer-projet/"

    def post(self, request):
        description = (request.data.get("description") or "").strip()
        if not description:
            return Response({"detail": "La description du projet est requise."},
                            status=status.HTTP_400_BAD_REQUEST)
        if len(description) > 1000:
            return Response({"detail": "La description ne doit pas dépasser 1000 caractères."},
                            status=status.HTTP_400_BAD_REQUEST)
        return self._executer(request, lambda: structurer_description_projet(description))


class AssistantExpliquerView(_AssistantBase):
    throttle_scope = "assistant_expliquer"
    endpoint = "/api/assistant/expliquer-element/"

    def post(self, request):
        element_id = request.data.get("element_id")
        if not element_id:
            return Response({"detail": "Le champ element_id est requis."},
                            status=status.HTTP_400_BAD_REQUEST)
        element = ElementStructurel.objects.filter(
            id=element_id, projet__entreprise=entreprise_de(request.user)
        ).first()
        if element is None:
            return Response({"detail": "Élément introuvable."}, status=status.HTTP_404_NOT_FOUND)
        if element.resultat_calcul is None:
            return Response({"detail": "Cet élément n'a aucun calcul disponible à expliquer."},
                            status=status.HTTP_400_BAD_REQUEST)
        payload = {
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
        return self._executer(request, lambda: expliquer_resultat_element(payload))


class AssistantSuggererPosteView(_AssistantBase):
    throttle_scope = "assistant_suggerer_poste"
    endpoint = "/api/assistant/suggerer-poste/"

    def post(self, request):
        description = (request.data.get("description") or "").strip()
        if not description:
            return Response({"detail": "La description du poste est requise."},
                            status=status.HTTP_400_BAD_REQUEST)
        if len(description) > 500:
            return Response({"detail": "La description ne doit pas dépasser 500 caractères."},
                            status=status.HTTP_400_BAD_REQUEST)
        return self._executer(request, lambda: suggerer_poste_complementaire(description))
