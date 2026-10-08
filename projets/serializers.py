from decimal import ROUND_HALF_UP, Decimal

from rest_framework import serializers

from moteur_calcul.constantes import CHARGES_EXPLOITATION
from moteur_calcul.hypotheses import resoudre_charge_permanente
from moteur_calcul.validators import EntreeInvalide, valider_contrainte_sol_kn_m2

from .models import (
    Projet,
    ElementStructurel,
    CoucheCharge,
    PosteComplementaire,
    EntrepriseParametres,
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
        read_only_fields = ("statut", "resultat_calcul", "resultat_valide")

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
        read_only_fields = ("lignes_calculees",)

    def get_montant(self, obj):
        if obj.mode != PosteComplementaire.Mode.SIMPLE or obj.quantite is None or obj.prix_unitaire is None:
            return None
        return int((Decimal(str(obj.quantite)) * Decimal(str(obj.prix_unitaire))).quantize(
            Decimal("1"), rounding=ROUND_HALF_UP))

    def validate_projet(self, projet):
        return _verifier_projet_du_cabinet(self, projet)

    def validate(self, attrs):
        def val(champ):
            return attrs.get(champ, getattr(self.instance, champ, None))

        mode = val("mode") or PosteComplementaire.Mode.SIMPLE
        erreurs = {}
        if mode == PosteComplementaire.Mode.SIMPLE:
            if not (val("designation") or "").strip():
                erreurs["designation"] = "La désignation est requise."
            if not (val("unite") or "").strip():
                erreurs["unite"] = "L'unité est requise."
            q = val("quantite")
            if q is None or q <= 0:
                erreurs["quantite"] = "La quantité doit être renseignée et strictement positive."
            pu = val("prix_unitaire")
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
        read_only_fields = ("entreprise", "cree_par", "plan_fondation_valide", "fichier_import_origine")

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
            for cle, valeur in nouveaux.items():
                if anciens.get(cle) != valeur:
                    meta[cle] = {
                        "date": timezone.localdate().isoformat(),
                        "auteur": auteur,
                        "source": "reference" if origines.get(cle) == "reference" else "saisie",
                    }
            for cle in set(meta) - set(nouveaux):
                meta.pop(cle, None)
            validated_data["prix_unitaires_meta"] = meta
        return super().update(instance, validated_data)

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
