"""
Vues du sprint "Comptes & Permissions" : inscription d'un cabinet,
invitation/gestion des membres, mot de passe (changement + réinitialisation),
déconnexion (révocation du refresh token).

IMPORTANT -- honnêteté sur ce qui est réellement branché : aucun backend
d'envoi d'email n'est configuré dans ce projet (pas d'EMAIL_BACKEND dans
settings.py). Les vues qui devraient normalement envoyer un email
(invitation, réinitialisation de mot de passe) renvoient donc le lien
directement dans la réponse JSON, avec un champ explicite
`email_envoye: false` -- jamais de faux "email envoyé". À remplacer par un
vrai envoi dès qu'un backend SMTP est configuré (voir TODO ci-dessous).
"""

from django.contrib.auth.models import User
from django.contrib.auth.tokens import default_token_generator
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError as DjangoValidationError
from django.utils.encoding import force_bytes, force_str
from django.utils.http import urlsafe_base64_encode, urlsafe_base64_decode
from django.db import transaction

from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework.permissions import IsAuthenticated, AllowAny
from rest_framework_simplejwt.tokens import RefreshToken
from rest_framework_simplejwt.exceptions import TokenError

from .models import Profil, EntrepriseParametres
from .permissions import EstAdminEntreprise


def _profil_serialise(profil: Profil) -> dict:
    return {
        "id": profil.utilisateur_id,
        "username": profil.utilisateur.username,
        "email": profil.utilisateur.email,
        "role": profil.role,
        "role_display": profil.get_role_display(),
        "actif": profil.utilisateur.is_active,
        "entreprise_id": profil.entreprise_id,
        "date_creation": profil.date_creation,
    }


class InscriptionEntrepriseView(APIView):
    """
    POST /api/auth/inscription/
    Crée une nouvelle entreprise (cabinet) + son premier compte, en rôle
    Admin. C'est la vue derrière RegisterPage.jsx (frontend) une fois
    branchée -- avant ce sprint, ce bouton faisait juste entrer dans
    l'app sans rien créer côté serveur.
    """

    permission_classes = [AllowAny]

    def post(self, request):
        nom_entreprise = (request.data.get("nom_entreprise") or "").strip()
        username = (request.data.get("username") or request.data.get("email") or "").strip()
        email = (request.data.get("email") or "").strip()
        mot_de_passe = request.data.get("mot_de_passe") or ""

        erreurs = {}
        if not nom_entreprise:
            erreurs["nom_entreprise"] = "Ce champ est requis."
        if not username:
            erreurs["username"] = "Ce champ est requis (ou fournissez un email)."
        if User.objects.filter(username=username).exists():
            erreurs["username"] = "Ce nom d'utilisateur est déjà pris."
        if not mot_de_passe:
            erreurs["mot_de_passe"] = "Ce champ est requis."
        else:
            try:
                validate_password(mot_de_passe)
            except DjangoValidationError as exc:
                erreurs["mot_de_passe"] = list(exc.messages)

        if erreurs:
            return Response(erreurs, status=status.HTTP_400_BAD_REQUEST)

        with transaction.atomic():
            entreprise = EntrepriseParametres.objects.create(nom=nom_entreprise, email=email)
            user = User.objects.create_user(username=username, email=email, password=mot_de_passe)
            profil = Profil.objects.create(utilisateur=user, entreprise=entreprise, role=Profil.Role.ADMIN)

        refresh = RefreshToken.for_user(user)
        return Response(
            {
                "profil": _profil_serialise(profil),
                "access": str(refresh.access_token),
                "refresh": str(refresh),
            },
            status=status.HTTP_201_CREATED,
        )


class InviterUtilisateurView(APIView):
    """
    POST /api/auth/inviter/  {"email": ..., "role": "technicien"|"ingenieur"|"admin"}
    Réservé à un Admin du cabinet. Crée un compte désactivé + un lien
    d'activation à durée limitée (mécanisme standard Django, le même que
    la réinitialisation de mot de passe). Aucun email n'est réellement
    envoyé -- voir note d'honnêteté en tête de fichier.
    """

    permission_classes = [IsAuthenticated, EstAdminEntreprise]

    def post(self, request):
        email = (request.data.get("email") or "").strip()
        role = (request.data.get("role") or Profil.Role.TECHNICIEN).strip()

        if not email:
            return Response({"email": "Ce champ est requis."}, status=status.HTTP_400_BAD_REQUEST)
        if role not in Profil.Role.values:
            return Response(
                {"role": f"Rôle invalide. Valeurs possibles : {Profil.Role.values}"},
                status=status.HTTP_400_BAD_REQUEST,
            )
        if User.objects.filter(username=email).exists():
            return Response({"email": "Un compte existe déjà avec cet email."}, status=status.HTTP_400_BAD_REQUEST)

        entreprise = request.user.profil.entreprise
        with transaction.atomic():
            user = User.objects.create_user(username=email, email=email, is_active=False)
            user.set_unusable_password()
            user.save(update_fields=["password"])
            Profil.objects.create(utilisateur=user, entreprise=entreprise, role=role)

        uid = urlsafe_base64_encode(force_bytes(user.pk))
        token = default_token_generator.make_token(user)

        return Response(
            {
                "detail": "Compte créé (désactivé) -- lien d'activation ci-dessous.",
                "email_envoye": False,
                "uid": uid,
                "token": token,
                "lien_activation": f"/activer-compte?uid={uid}&token={token}",
            },
            status=status.HTTP_201_CREATED,
        )


class ActiverCompteView(APIView):
    """
    POST /api/auth/activer/  {"uid": ..., "token": ..., "mot_de_passe": ...}
    Confirme l'invitation : définit le mot de passe et active le compte.
    """

    permission_classes = [AllowAny]

    def post(self, request):
        uid = request.data.get("uid") or ""
        token = request.data.get("token") or ""
        mot_de_passe = request.data.get("mot_de_passe") or ""

        try:
            user_id = force_str(urlsafe_base64_decode(uid))
            user = User.objects.get(pk=user_id)
        except (ValueError, TypeError, User.DoesNotExist):
            return Response({"detail": "Lien d'activation invalide."}, status=status.HTTP_400_BAD_REQUEST)

        if not default_token_generator.check_token(user, token):
            return Response({"detail": "Lien d'activation invalide ou expiré."}, status=status.HTTP_400_BAD_REQUEST)

        if not mot_de_passe:
            return Response({"mot_de_passe": "Ce champ est requis."}, status=status.HTTP_400_BAD_REQUEST)
        try:
            validate_password(mot_de_passe, user=user)
        except DjangoValidationError as exc:
            return Response({"mot_de_passe": list(exc.messages)}, status=status.HTTP_400_BAD_REQUEST)

        user.set_password(mot_de_passe)
        user.is_active = True
        user.save(update_fields=["password", "is_active"])

        return Response({"detail": "Compte activé, vous pouvez maintenant vous connecter."})


class MembresEntrepriseView(APIView):
    """
    GET /api/auth/membres/ -- liste les comptes du cabinet de l'Admin connecté.
    """

    permission_classes = [IsAuthenticated, EstAdminEntreprise]

    def get(self, request):
        entreprise = request.user.profil.entreprise
        profils = Profil.objects.filter(entreprise=entreprise).select_related("utilisateur")
        return Response([_profil_serialise(p) for p in profils])


class DesactiverUtilisateurView(APIView):
    """
    POST /api/auth/membres/<id>/desactiver/ -- réservé à un Admin, et
    seulement pour un membre de sa propre entreprise (jamais un autre cabinet).
    """

    permission_classes = [IsAuthenticated, EstAdminEntreprise]

    def post(self, request, user_id):
        entreprise = request.user.profil.entreprise
        try:
            profil_cible = Profil.objects.select_related("utilisateur").get(
                utilisateur_id=user_id, entreprise=entreprise
            )
        except Profil.DoesNotExist:
            return Response({"detail": "Aucun membre trouvé dans votre entreprise."}, status=status.HTTP_404_NOT_FOUND)

        if profil_cible.utilisateur_id == request.user.id:
            return Response({"detail": "Vous ne pouvez pas désactiver votre propre compte."}, status=status.HTTP_400_BAD_REQUEST)

        profil_cible.utilisateur.is_active = False
        profil_cible.utilisateur.save(update_fields=["is_active"])
        return Response(_profil_serialise(profil_cible))


class ChangerMotDePasseView(APIView):
    """
    POST /api/auth/changer-mot-de-passe/  {"ancien_mot_de_passe", "nouveau_mot_de_passe"}
    Pour l'utilisateur connecté lui-même.
    """

    permission_classes = [IsAuthenticated]

    def post(self, request):
        ancien = request.data.get("ancien_mot_de_passe") or ""
        nouveau = request.data.get("nouveau_mot_de_passe") or ""

        if not request.user.check_password(ancien):
            return Response({"ancien_mot_de_passe": "Mot de passe actuel incorrect."}, status=status.HTTP_400_BAD_REQUEST)
        try:
            validate_password(nouveau, user=request.user)
        except DjangoValidationError as exc:
            return Response({"nouveau_mot_de_passe": list(exc.messages)}, status=status.HTTP_400_BAD_REQUEST)

        request.user.set_password(nouveau)
        request.user.save(update_fields=["password"])
        return Response({"detail": "Mot de passe modifié."})


class DemanderReinitialisationView(APIView):
    """
    POST /api/auth/mot-de-passe-oublie/  {"email": ...}
    Ne révèle jamais si l'email existe ou non (réponse identique dans les
    deux cas -- énumération d'emails). Le lien n'est renvoyé dans la
    réponse QUE si l'email correspond à un compte, jamais autrement.
    """

    permission_classes = [AllowAny]

    def post(self, request):
        email = (request.data.get("email") or "").strip()
        user = User.objects.filter(email=email, is_active=True).first()

        reponse = {
            "detail": "Si un compte existe avec cet email, un lien de réinitialisation a été généré.",
            "email_envoye": False,
        }
        if user is not None:
            uid = urlsafe_base64_encode(force_bytes(user.pk))
            token = default_token_generator.make_token(user)
            reponse["lien_reinitialisation"] = f"/reinitialiser-mot-de-passe?uid={uid}&token={token}"

        return Response(reponse)


class ConfirmerReinitialisationView(APIView):
    """
    POST /api/auth/reinitialiser-mot-de-passe/  {"uid", "token", "nouveau_mot_de_passe"}
    """

    permission_classes = [AllowAny]

    def post(self, request):
        uid = request.data.get("uid") or ""
        token = request.data.get("token") or ""
        nouveau = request.data.get("nouveau_mot_de_passe") or ""

        try:
            user_id = force_str(urlsafe_base64_decode(uid))
            user = User.objects.get(pk=user_id)
        except (ValueError, TypeError, User.DoesNotExist):
            return Response({"detail": "Lien invalide."}, status=status.HTTP_400_BAD_REQUEST)

        if not default_token_generator.check_token(user, token):
            return Response({"detail": "Lien invalide ou expiré."}, status=status.HTTP_400_BAD_REQUEST)

        try:
            validate_password(nouveau, user=user)
        except DjangoValidationError as exc:
            return Response({"nouveau_mot_de_passe": list(exc.messages)}, status=status.HTTP_400_BAD_REQUEST)

        user.set_password(nouveau)
        user.save(update_fields=["password"])
        return Response({"detail": "Mot de passe réinitialisé, vous pouvez vous connecter."})


class LogoutView(APIView):
    """
    POST /api/auth/logout/  {"refresh": ...}
    Révoque le refresh token (liste noire) -- nécessite
    rest_framework_simplejwt.token_blacklist dans INSTALLED_APPS.
    """

    permission_classes = [IsAuthenticated]

    def post(self, request):
        refresh_token = request.data.get("refresh")
        if not refresh_token:
            return Response({"refresh": "Ce champ est requis."}, status=status.HTTP_400_BAD_REQUEST)
        try:
            token = RefreshToken(refresh_token)
            token.blacklist()
        except TokenError:
            return Response({"detail": "Token invalide ou déjà révoqué."}, status=status.HTTP_400_BAD_REQUEST)
        return Response(status=status.HTTP_205_RESET_CONTENT)