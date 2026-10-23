from decimal import ROUND_HALF_UP, Decimal

from rest_framework import serializers

from .services.decomposition_prix import verifier_decomposition

import re

from moteur_calcul.constantes import CHARGES_EXPLOITATION, POIDS_MURS_MAX_KN_M2, POURCENTAGE_BAIES_MAX
from moteur_calcul.hypotheses import resoudre_charge_permanente
from moteur_calcul.validators import EntreeInvalide, valider_contrainte_sol_kn_m2

from .models import (
    Projet,
    ElementStructurel,
    CoucheCharge,
    PosteComplementaire,
    EntrepriseParametres,
    OuvrageType,
)
from .permissions import entreprise_de


def _entreprise_requete(serializer):
    request = serializer.context.get("request")
    return entreprise_de(getattr(request, "user", None))


def _verifier_projet_du_cabinet(serializer, projet):
    """Interdit de rattacher un objet à un projet d'un autre cabinet.

    Message volontairement identique à "projet inexistant" : on ne révèle
    pas l'existence des projets des autres cabinets.
    """
    if projet is None:
        return projet
    entreprise = _entreprise_requete(serializer)
    if entreprise is None or projet.entreprise_id != entreprise.id:
        raise serializers.ValidationError("Projet introuvable.")
    return projet


class CoucheChargeSerializer(serializers.ModelSerializer):
    poids_surfacique_kn_m2 = serializers.ReadOnlyField()

    class Meta:
        model = CoucheCharge
        fields = "__all__"

    def validate_projet(self, projet):
        return _verifier_projet_du_cabinet(self, projet)

    def validate_element(self, element):
        if element is not None:
            _verifier_projet_du_cabinet(self, element.projet)
        return element

    def validate(self, attrs):
        if attrs.get("epaisseur_cm") is not None and attrs["epaisseur_cm"] <= 0:
            raise serializers.ValidationError({"epaisseur_cm": "L'épaisseur doit être positive (cm)."})
        if attrs.get("poids_volumique_kn_m3") is not None and attrs["poids_volumique_kn_m3"] <= 0:
            raise serializers.ValidationError({"poids_volumique_kn_m3": "Le poids volumique doit être positif (kN/m³)."})
        return attrs


class ElementStructurelSerializer(serializers.ModelSerializer):
    couches_charges = CoucheChargeSerializer(many=True, read_only=True)

    class Meta:
        model = ElementStructurel
        fields = "__all__"
        # origine_geometrie : fixée par le serveur (trame, plan lu, saisie).
        read_only_fields = ("statut", "resultat_calcul", "resultat_valide", "origine_geometrie")

    def validate_projet(self, projet):
        return _verifier_projet_du_cabinet(self, projet)

    def validate_nombre_identiques(self, n):
        if n is None or n < 1:
            raise serializers.ValidationError("Le nombre d'ouvrages identiques doit être au moins 1.")
        return n

    def validate_taux_travail_sol(self, valeur):
        try:
            return valider_contrainte_sol_kn_m2(valeur)
        except EntreeInvalide as exc:
            raise serializers.ValidationError(str(exc))

    def validate(self, attrs):
        projet = attrs.get("projet") or getattr(self.instance, "projet", None)
        type_element = attrs.get("type_element", getattr(self.instance, "type_element", None))
        if type_element == ElementStructurel.TypeElement.DALLE:
            # Dalle rectangulaire : portee = Lx (petite portée), longueur_m
            # = Ly. La surface (utilisée par le DQE) est déduite ICI, côté
            # serveur, quand elle n'est pas fournie.
            lx = attrs.get("portee", getattr(self.instance, "portee", None))
            ly = attrs.get("longueur_m", getattr(self.instance, "longueur_m", None))
            if lx is not None and ly is not None:
                if lx <= 0 or ly <= 0:
                    raise serializers.ValidationError("Les portées de la dalle doivent être positives (m).")
                if lx > ly:
                    raise serializers.ValidationError(
                        {"portee": "Lx (portee) doit être la PETITE portée : Lx ≤ Ly (longueur_m)."}
                    )
                if attrs.get("surface_m2") is None:
                    attrs["surface_m2"] = round(lx * ly, 4)
        for champ in ("poteau_associe", "poteau_origine", "poteau_destination"):
            cible = attrs.get(champ)
            if cible is not None and projet is not None and cible.projet_id != projet.id:
                raise serializers.ValidationError({champ: "Cet élément n'appartient pas au même projet."})
        return attrs


class ElementValidationSerializer(serializers.Serializer):
    resultat_valide = serializers.JSONField(required=False)


class PosteComplementaireSerializer(serializers.ModelSerializer):
    # Montant d'un poste SIMPLE, calculé côté serveur (Decimal, arrondi au
    # FCFA) -- le frontend ne recalcule plus quantité x prix. None pour un
    # poste RATIO : il n'est valorisé qu'au DQE, avec le barème du cabinet.
    montant = serializers.SerializerMethodField()

    class Meta:
        model = PosteComplementaire
        fields = "__all__"
        # Origine du prix : fixée par le serveur (bibliothèque ou saisie).
        read_only_fields = ("lignes_calculees", "prix_source", "prix_date")
        # Le lot peut venir de l'ouvrage de la bibliothèque (voir validate).
        extra_kwargs = {"lot": {"required": False}}

    def get_montant(self, obj):
        if obj.mode != PosteComplementaire.Mode.SIMPLE or obj.quantite is None or obj.prix_unitaire is None:
            return None
        return int((Decimal(str(obj.quantite)) * Decimal(str(obj.prix_unitaire))).quantize(
            Decimal("1"), rounding=ROUND_HALF_UP))

    def validate_projet(self, projet):
        return _verifier_projet_du_cabinet(self, projet)

    def validate_ouvrage(self, ouvrage):
        if ouvrage is None:
            return ouvrage
        entreprise = _entreprise_requete(self)
        if entreprise is None or ouvrage.entreprise_id != entreprise.id:
            raise serializers.ValidationError("Ouvrage introuvable dans la bibliothèque du cabinet.")
        return ouvrage

    def _reprendre_ouvrage(self, attrs):
        """Poste repris de la bibliothèque : désignation, unité et lot copiés
        s'ils ne sont pas saisis ; prix copié s'il n'est pas saisi. L'origine
        du prix est tracée sur le poste (et donc sur la ligne du DQE)."""
        ouvrage = attrs.get("ouvrage")
        if ouvrage is None:
            if "prix_unitaire" in attrs:
                attrs["prix_source"], attrs["prix_date"] = "saisie (poste)", None
            return
        for champ in ("designation", "unite"):
            if not (attrs.get(champ) or "").strip():
                attrs[champ] = getattr(ouvrage, champ)
        attrs.setdefault("lot", ouvrage.lot)
        if attrs.get("prix_unitaire") is None and ouvrage.prix_unitaire is not None:
            attrs["prix_unitaire"] = ouvrage.prix_unitaire
            # Parts matériaux / main-d'œuvre copiées avec le prix (issue #92).
            attrs.setdefault("prix_materiaux", ouvrage.prix_materiaux)
            attrs.setdefault("prix_main_oeuvre", ouvrage.prix_main_oeuvre)
            attrs["prix_source"] = "bibliothèque du cabinet" + (f" ({ouvrage.source_prix})" if ouvrage.source_prix else "")
            attrs["prix_date"] = ouvrage.date_prix
        elif "prix_unitaire" in attrs:
            attrs["prix_source"], attrs["prix_date"] = "saisie (poste)", None

    def validate(self, attrs):
        self._reprendre_ouvrage(attrs)

        def val(champ):
            return attrs.get(champ, getattr(self.instance, champ, None))

        mode = val("mode") or PosteComplementaire.Mode.SIMPLE
        erreurs = {}
        if not val("lot"):
            erreurs["lot"] = "Le lot est requis."
        if mode == PosteComplementaire.Mode.SIMPLE:
            if not (val("designation") or "").strip():
                erreurs["designation"] = "La désignation est requise."
            if not (val("unite") or "").strip():
                erreurs["unite"] = "L'unité est requise."
            q = val("quantite")
            if q is None or q <= 0:
                erreurs["quantite"] = "La quantité doit être renseignée et strictement positive."
            pu = val("prix_unitaire")
            try:
                pu, mat, mo = verifier_decomposition(pu, val("prix_materiaux"), val("prix_main_oeuvre"),
                                                     "Prix du poste")
                if mat is not None:
                    attrs.update(prix_unitaire=pu, prix_materiaux=mat, prix_main_oeuvre=mo)
            except ValueError as exc:
                erreurs["prix_materiaux"] = str(exc)
            if pu is None or pu < 0:
                erreurs["prix_unitaire"] = "Le prix unitaire doit être renseigné (≥ 0 FCFA)."
        else:
            if not val("type_poste"):
                erreurs["type_poste"] = "Le type de poste est requis en mode ratio."
            if not val("geometrie"):
                erreurs["geometrie"] = "La géométrie est requise en mode ratio."
        if erreurs:
            raise serializers.ValidationError(erreurs)
        return attrs


class OuvrageTypeSerializer(serializers.ModelSerializer):
    """Ouvrage de la bibliothèque du cabinet. Le cabinet et l'auteur sont
    fixés par le serveur ; un même ouvrage (lot, désignation, unité) n'existe
    qu'une fois par cabinet."""

    lot_libelle = serializers.CharField(source="get_lot_display", read_only=True)
    nb_postes = serializers.SerializerMethodField()

    class Meta:
        model = OuvrageType
        fields = ("id", "lot", "lot_libelle", "designation", "unite", "prix_unitaire", "prix_materiaux",
                  "prix_main_oeuvre", "source_prix", "date_prix", "nb_postes", "date_modification")
        read_only_fields = ("date_modification",)

    def get_nb_postes(self, obj):
        annote = getattr(obj, "nb_postes_annote", None)
        return annote if annote is not None else obj.postes.count()

    def validate_designation(self, v):
        v = (v or "").strip()
        if not v:
            raise serializers.ValidationError("La désignation est requise.")
        return v

    def validate_unite(self, v):
        v = (v or "").strip()
        if not v:
            raise serializers.ValidationError("L'unité est requise.")
        return v

    def validate_prix_unitaire(self, v):
        if v is not None and v < 0:
            raise serializers.ValidationError("Le prix unitaire doit être positif ou nul (FCFA).")
        return v

    def validate(self, attrs):
        entreprise = _entreprise_requete(self)
        cle = {k: attrs.get(k, getattr(self.instance, k, None)) for k in ("lot", "designation", "unite")}
        doublons = OuvrageType.objects.filter(entreprise=entreprise, **cle)
        if self.instance is not None:
            doublons = doublons.exclude(pk=self.instance.pk)
        if doublons.exists():
            raise serializers.ValidationError(
                f"« {cle['designation']} » ({cle['unite']}) existe déjà dans ce lot de la bibliothèque.")
        # Décomposition (issue #92) : deux parts ou aucune ; total = somme.
        val = lambda k: attrs.get(k, getattr(self.instance, k, None))  # noqa: E731
        try:
            pu, mat, mo = verifier_decomposition(val("prix_unitaire"), val("prix_materiaux"),
                                                 val("prix_main_oeuvre"), f"« {cle['designation']} »")
        except ValueError as exc:
            raise serializers.ValidationError({"prix_materiaux": str(exc)})
        if mat is not None:
            attrs.update(prix_unitaire=pu, prix_materiaux=mat, prix_main_oeuvre=mo)
        return attrs


# Clé d'un tronçon (moteur_calcul.formules.trame.cle_segment) : "x;y|x;y" au cm.
MOTIF_CLE_SEGMENT = re.compile(r"^-?\d+\.\d{2};-?\d+\.\d{2}\|-?\d+\.\d{2};-?\d+\.\d{2}$")
MAX_TRONCONS_MURS = 2000


class ProjetSerializer(serializers.ModelSerializer):
    elements = ElementStructurelSerializer(many=True, read_only=True)
    couches_charges = CoucheChargeSerializer(many=True, read_only=True)
    postes_complementaires = PosteComplementaireSerializer(many=True, read_only=True)
    # Contrôles de plausibilité (signalent, ne modifient jamais).
    alertes_plausibilite = serializers.SerializerMethodField()
    hypotheses_calcul = serializers.SerializerMethodField()

    class Meta:
        model = Projet
        fields = "__all__"
        # Le cabinet et l'auteur sont fixés par le serveur à partir de
        # l'utilisateur connecté : jamais modifiables par le client (avant,
        # un utilisateur pouvait déplacer un projet dans un autre cabinet).
        read_only_fields = ("entreprise", "cree_par", "plan_fondation_valide", "fichier_import_origine",
                            "parametres_import", "source_structure", "poteaux_saisis")

    def validate_usage_batiment(self, usage):
        if usage and usage not in CHARGES_EXPLOITATION:
            raise serializers.ValidationError(
                f"Usage inconnu : « {usage} ». Valeurs acceptées : {', '.join(CHARGES_EXPLOITATION)}."
            )
        return usage

    def validate_contrainte_sol_kn_m2(self, valeur):
        try:
            return valider_contrainte_sol_kn_m2(valeur)
        except EntreeInvalide as exc:
            raise serializers.ValidationError(str(exc))

    def validate_poids_murs_kn_m2(self, valeur):
        if valeur is not None and not (0 < valeur <= POIDS_MURS_MAX_KN_M2):
            raise serializers.ValidationError(
                f"Le poids des murs doit être compris entre 0 et {POIDS_MURS_MAX_KN_M2:g} kN/m² de mur "
                f"(enduits compris). Vide = charge des murs non comptée."
            )
        return valeur

    def _valider_murs(self, valeur):
        if not isinstance(valeur, list) or len(valeur) > MAX_TRONCONS_MURS:
            raise serializers.ValidationError(f"Liste de tronçons de mur attendue (au plus {MAX_TRONCONS_MURS}).")
        if any(not isinstance(c, str) or not MOTIF_CLE_SEGMENT.match(c) for c in valeur):
            raise serializers.ValidationError("Tronçon de mur invalide : identifiant de poutre inconnu.")
        return sorted(set(valeur))

    def validate_murs_rdc(self, valeur):
        return self._valider_murs(valeur)

    def validate_murs_etages(self, valeur):
        return self._valider_murs(valeur)

    def validate_pourcentage_baies_murs(self, valeur):
        if valeur is None or not (0 <= valeur <= POURCENTAGE_BAIES_MAX):
            raise serializers.ValidationError(
                f"La part des baies doit être comprise entre 0 et {POURCENTAGE_BAIES_MAX:g} %.")
        return valeur

    def get_hypotheses_calcul(self, obj):
        from .services.parametres_projet import messages_hypotheses

        return messages_hypotheses(obj)

    def get_alertes_plausibilite(self, obj):
        from moteur_calcul.plausibilite import controler_projet

        return controler_projet(obj)

    def validate_couches_permanentes(self, couches):
        if couches in (None, ""):
            return []
        if not isinstance(couches, list):
            raise serializers.ValidationError("La composition du plancher doit être une liste de couches.")
        if couches:
            try:
                resoudre_charge_permanente(None, couches)
            except (ValueError, TypeError, AttributeError) as exc:
                raise serializers.ValidationError(f"Composition du plancher invalide : {exc}")
        return couches

    def validate(self, attrs):
        for champ, libelle in (("charge_permanente_kn_m2", "charge permanente G"), ("portee_x", "portée X"), ("portee_y", "portée Y"),
                               ("hauteur_etage", "hauteur d'étage"),
                               ("charge_exploitation", "charge d'exploitation")):
            v = attrs.get(champ)
            if v is not None and v <= 0:
                raise serializers.ValidationError({champ: f"La {libelle} doit être strictement positive."})
        return attrs


class ProjetResumeSerializer(serializers.ModelSerializer):
    """Liste "Mes projets" : pas d'imbrication des éléments (performance)."""

    nb_elements = serializers.IntegerField(read_only=True)
    nb_elements_valides = serializers.IntegerField(read_only=True)
    cree_par_nom = serializers.SerializerMethodField()
    statut = serializers.SerializerMethodField()

    class Meta:
        model = Projet
        fields = (
            "id", "nom", "description", "usage_batiment", "nb_niveaux", "numero_devis",
            "date_creation", "date_modification", "plan_fondation_valide",
            "nb_elements", "nb_elements_valides", "cree_par_nom", "statut",
        )

    def get_statut(self, obj):
        from .services.parametres_projet import statut_projet

        return statut_projet(obj.nb_elements, obj.nb_elements_valides, bool(getattr(obj, "a_dqe", False)))

    def get_cree_par_nom(self, obj):
        u = obj.cree_par
        if u is None:
            return None
        return u.get_full_name() or u.username


class EntrepriseParametresSerializer(serializers.ModelSerializer):
    # Origine déclarée des prix modifiés dans cette requête : {clé: "reference"}
    # quand l'admin a utilisé le pré-remplissage avec le barème de référence.
    prix_origines = serializers.JSONField(write_only=True, required=False)

    class Meta:
        model = EntrepriseParametres
        fields = "__all__"
        read_only_fields = ("date_modification", "prix_unitaires_meta")

    def validate_taux_tva_pct(self, v):
        if v is not None and not (0 <= v <= 100):
            raise serializers.ValidationError("Le taux de TVA doit être compris entre 0 et 100 %.")
        return v

    def validate_taux_marge_pct(self, v):
        if v is not None and not (0 <= v <= 300):
            raise serializers.ValidationError("Le taux de marge doit être compris entre 0 et 300 %.")
        return v

    def update(self, instance, validated_data):
        from django.utils import timezone

        origines = validated_data.pop("prix_origines", None) or {}
        if not isinstance(origines, dict):
            origines = {}
        if "prix_unitaires" in validated_data:
            anciens = instance.prix_unitaires or {}
            nouveaux = validated_data["prix_unitaires"]
            meta = dict(instance.prix_unitaires_meta or {})
            request = self.context.get("request")
            auteur = getattr(getattr(request, "user", None), "username", None)
            anciennes_parts = instance.prix_decomposition or {}
            nouvelles_parts = validated_data.get("prix_decomposition", anciennes_parts)
            for cle, valeur in nouveaux.items():
                if anciens.get(cle) != valeur or anciennes_parts.get(cle) != nouvelles_parts.get(cle):
                    meta[cle] = {
                        "date": timezone.localdate().isoformat(),
                        "auteur": auteur,
                        "source": "reference" if origines.get(cle) == "reference" else "saisie",
                    }
            for cle in set(meta) - set(nouveaux):
                meta.pop(cle, None)
            validated_data["prix_unitaires_meta"] = meta
        return super().update(instance, validated_data)

    def validate_prix_decomposition(self, valeur):
        if not isinstance(valeur, dict):
            raise serializers.ValidationError("La décomposition doit être un objet {clé: {materiaux, main_oeuvre}}.")
        propres = {}
        for cle, parts in valeur.items():
            if parts in (None, "", {}):
                continue  # décomposition retirée : prix « non décomposé »
            if not isinstance(parts, dict):
                raise serializers.ValidationError(f"Décomposition « {cle} » invalide.")
            mat, mo = parts.get("materiaux"), parts.get("main_oeuvre")
            if mat in (None, "") and mo in (None, ""):
                continue
            try:
                _, mat, mo = verifier_decomposition(None, None if mat == "" else mat, None if mo == "" else mo,
                                                    f"Prix « {cle} »")
            except ValueError as exc:
                raise serializers.ValidationError(str(exc))
            propres[cle] = {"materiaux": mat, "main_oeuvre": mo}
        return propres

    def validate(self, attrs):
        """Barème : chaque prix décomposé doit être égal à matériaux +
        main-d'œuvre ; retirer un prix retire sa décomposition."""
        attrs = super().validate(attrs)
        if "prix_unitaires" not in attrs and "prix_decomposition" not in attrs:
            return attrs
        prix = attrs.get("prix_unitaires", getattr(self.instance, "prix_unitaires", None) or {})
        decomposition = attrs.get("prix_decomposition", getattr(self.instance, "prix_decomposition", None) or {})
        decomposition = {c: p for c, p in decomposition.items() if c in prix}
        for cle, parts in decomposition.items():
            try:
                verifier_decomposition(prix[cle], parts["materiaux"], parts["main_oeuvre"], f"Prix « {cle} »")
            except ValueError as exc:
                raise serializers.ValidationError({"prix_decomposition": str(exc)})
        attrs["prix_decomposition"] = decomposition
        return attrs

    def validate_parametres_approvisionnement(self, params):
        from .services.approvisionnement import valider_parametres
        try:
            return valider_parametres(params)
        except ValueError as exc:
            raise serializers.ValidationError(str(exc))

    def validate_prix_unitaires(self, prix):
        if not isinstance(prix, dict):
            raise serializers.ValidationError("Le barème doit être un objet {clé: prix}.")
        propres = {}
        for cle, valeur in prix.items():
            if valeur in (None, ""):
                continue  # clé vidée = prix retiré du barème
            try:
                nombre = float(valeur)
            except (TypeError, ValueError):
                raise serializers.ValidationError(f"Prix « {cle} » invalide : {valeur!r}.")
            if nombre < 0:
                raise serializers.ValidationError(f"Prix « {cle} » négatif.")
            propres[cle] = nombre
        return propres
