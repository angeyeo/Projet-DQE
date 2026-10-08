import os
from pathlib import Path
from datetime import timedelta
from dotenv import load_dotenv

# Build paths inside the project like this: BASE_DIR / 'subdir'.
BASE_DIR = Path(__file__).resolve().parent.parent

# Chargement automatique du fichier .env à la racine du projet
load_dotenv(BASE_DIR / ".env")


# DEBUG est piloté UNIQUEMENT par la variable d'environnement (défaut :
# False). Avant : `DEBUG = True` écrasait la variable, donc la production
# tournait en mode debug (pages d'erreur détaillées exposées).
DEBUG = os.getenv("DEBUG", "False").strip().lower() == "true"

# SECRET_KEY : obligatoire hors DEBUG. La clé de développement n'est
# acceptée qu'en DEBUG local, jamais en production.
SECRET_KEY = os.getenv("SECRET_KEY", "")
if not SECRET_KEY:
    if DEBUG:
        SECRET_KEY = "dev-only-insecure-key-change-me"
    else:
        from django.core.exceptions import ImproperlyConfigured

        raise ImproperlyConfigured(
            "SECRET_KEY doit être définie dans l'environnement quand DEBUG=False."
        )

# Plus de joker "*" par défaut : seuls les hôtes explicitement listés.
ALLOWED_HOSTS = [
    host.strip()
    for host in os.getenv("ALLOWED_HOSTS", "localhost,127.0.0.1").split(",")
    if host.strip()
]


# Application definition

INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'rest_framework',
    'rest_framework_simplejwt',
    'rest_framework_simplejwt.token_blacklist',
    'corsheaders',
    'api',
    'moteur_calcul',
    'projets',
]

REST_FRAMEWORK = {
    'DEFAULT_THROTTLE_RATES': {
        'assistant_structurer': '10/min',
        'assistant_expliquer': '20/min',
        'assistant_suggerer_poste': '15/min',
        'assistant_vision': '5/min',
        'assistant_coherence': '10/min',
    },
    # Fermé par défaut : toute vue exige un utilisateur authentifié ET
    # rattaché à un cabinet. Les vues publiques (inscription, login,
    # mot de passe oublié) déclarent AllowAny explicitement. Le
    # DEMO_MODE (accès anonyme à tout) a été supprimé.
    'DEFAULT_PERMISSION_CLASSES': [
        'projets.permissions.EstMembreEntreprise',
    ],
    'DEFAULT_AUTHENTICATION_CLASSES': [
        'rest_framework_simplejwt.authentication.JWTAuthentication',
        'rest_framework.authentication.SessionAuthentication',
    ],
}

# Une seule déclaration (avant : deux blocs, le second -- 8 h -- écrasait
# silencieusement le premier). Jeton d'accès court + refresh avec
# rotation : le frontend rafraîchit automatiquement (dqeService.apiFetch).
SIMPLE_JWT = {
    'ACCESS_TOKEN_LIFETIME': timedelta(minutes=30),
    'REFRESH_TOKEN_LIFETIME': timedelta(days=7),
    'ROTATE_REFRESH_TOKENS': True,
    'BLACKLIST_AFTER_ROTATION': True,
    'UPDATE_LAST_LOGIN': True,
    'AUTH_HEADER_TYPES': ('Bearer',),
}

# Limite d'upload pour les images de plans (Phase A Vision)
PLAN_IMAGE_MAX_BYTES = int(os.getenv("PLAN_IMAGE_MAX_BYTES", str(5 * 1024 * 1024))) # 5 Mo par défaut

# --- Envoi d'email (invitations, réinitialisation de mot de passe) ---
# Sans EMAIL_HOST défini (dev/tests), on retombe sur le backend "console" :
# aucun envoi réel, les emails sont juste affichés dans les logs du serveur.
# projets/auth_views.py considère ce cas comme "pas de SMTP configuré" et
# garde alors l'ancien comportement (lien renvoyé dans la réponse JSON en
# secours) -- voir _email_reellement_configure().
EMAIL_HOST = os.getenv("EMAIL_HOST", "")
if EMAIL_HOST:
    EMAIL_BACKEND = "django.core.mail.backends.smtp.EmailBackend"
    EMAIL_PORT = int(os.getenv("EMAIL_PORT", "587"))
    EMAIL_HOST_USER = os.getenv("EMAIL_HOST_USER", "")
    EMAIL_HOST_PASSWORD = os.getenv("EMAIL_HOST_PASSWORD", "")
    EMAIL_USE_TLS = os.getenv("EMAIL_USE_TLS", "True").strip().lower() == "true"
    EMAIL_USE_SSL = os.getenv("EMAIL_USE_SSL", "False").strip().lower() == "true"
    EMAIL_TIMEOUT = int(os.getenv("EMAIL_TIMEOUT_SECONDS", "10"))
    DEFAULT_FROM_EMAIL = os.getenv("DEFAULT_FROM_EMAIL", EMAIL_HOST_USER)
else:
    EMAIL_BACKEND = "django.core.mail.backends.console.EmailBackend"
    DEFAULT_FROM_EMAIL = os.getenv("DEFAULT_FROM_EMAIL", "no-reply@projet-dqe.local")

# Domaine du frontend, utilisé pour construire les liens absolus envoyés
# par email (activation de compte, réinitialisation de mot de passe).
FRONTEND_URL = os.getenv("FRONTEND_URL", "http://localhost:5173").rstrip("/")


MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'whitenoise.middleware.WhiteNoiseMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'corsheaders.middleware.CorsMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

ROOT_URLCONF = 'backend.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.debug',
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
            ],
        },
    },
]

WSGI_APPLICATION = 'backend.wsgi.application'


# Database
if os.getenv("DATABASE_URL"):
    import dj_database_url

    DATABASES = {
        "default": dj_database_url.parse(
            os.environ["DATABASE_URL"],
            conn_max_age=600,
            ssl_require=os.getenv("DATABASE_SSL_REQUIRE", "True").lower() == "true",
        )
    }
else:
    DATABASES = {
        "default": {
            "ENGINE": "django.db.backends.sqlite3",
            "NAME": BASE_DIR / "db.sqlite3",
        }
    }


# Password validation
AUTH_PASSWORD_VALIDATORS = [
    {
        'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator',
    },
]


# Internationalization
LANGUAGE_CODE = 'fr-fr'

TIME_ZONE = 'UTC'

USE_I18N = True

USE_TZ = True


# Static files (CSS, JavaScript, Images)
STATIC_URL = '/static/'

MEDIA_URL = '/media/'
MEDIA_ROOT = BASE_DIR / 'media'
STATIC_ROOT = BASE_DIR / "staticfiles"

STORAGES = {
    "default": {
        "BACKEND": "django.core.files.storage.FileSystemStorage",
    },
    "staticfiles": {
        "BACKEND": "whitenoise.storage.CompressedManifestStaticFilesStorage",
    },
}

CORS_ALLOWED_ORIGINS = [
    origin.strip().rstrip("/")
    for origin in os.getenv(
        "CORS_ALLOWED_ORIGINS",
        "http://localhost:5173,http://127.0.0.1:5173,https://loving-friendship-production-8d0d.up.railway.app",
    ).split(",")
    if origin.strip()
]

CSRF_TRUSTED_ORIGINS = [
    origin.strip().rstrip("/")
    for origin in os.getenv(
        "CSRF_TRUSTED_ORIGINS",
        "http://localhost:5173,http://127.0.0.1:5173,https://loving-friendship-production-8d0d.up.railway.app",
    ).split(",")
    if origin.strip()
]

SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
SESSION_COOKIE_SECURE = not DEBUG
CSRF_COOKIE_SECURE = not DEBUG

DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'
# HTTPS strict -- activable par environnement une fois le domaine et le
# proxy TLS vérifiés (une redirection SSL derrière certains proxys casse
# les health checks ; HSTS est quasi irréversible côté navigateurs).
SECURE_SSL_REDIRECT = os.getenv("SECURE_SSL_REDIRECT", "False").strip().lower() == "true"
SECURE_HSTS_SECONDS = int(os.getenv("SECURE_HSTS_SECONDS", "0"))
SECURE_HSTS_INCLUDE_SUBDOMAINS = SECURE_HSTS_SECONDS > 0