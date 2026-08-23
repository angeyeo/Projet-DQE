# Déploiement Railway — Projet DQE

## Architecture

- `Backend` : racine du dépôt (`/`), Django + DRF + moteur de calcul.
- `Frontend` : `/frontend`, React + Vite + Caddy.
- `Postgres` : service PostgreSQL Railway.

## 1. Backend

Service Railway : `Backend`

- Source : le dépôt GitHub du projet
- Root Directory : `/`
- Start Command : laisser Railway utiliser le `Procfile`, ou mettre :

```bash
python manage.py migrate --noinput && python manage.py collectstatic --noinput && gunicorn backend.wsgi:application --bind 0.0.0.0:$PORT
```

Variables minimales :

```env
SECRET_KEY=<générer une clé aléatoire forte>
DEBUG=False
ALLOWED_HOSTS=api.ivoireinnovationbtp.com,.up.railway.app
CORS_ALLOWED_ORIGINS=https://www.ivoireinnovationbtp.com
CSRF_TRUSTED_ORIGINS=https://www.ivoireinnovationbtp.com
DATABASE_URL=${{Postgres.DATABASE_URL}}
DATABASE_SSL_REQUIRE=True
DEMO_MODE=False
LLM_PROVIDER=gemini
LLM_API_KEY=<clé Gemini>
LLM_MODEL=gemini-3.5-flash
LLM_TIMEOUT_SECONDS=60
LLM_MAX_RESPONSE_BYTES=65536
PLAN_IMAGE_MAX_BYTES=5242880
```

## 2. Frontend

Service Railway : `Frontend`

- Source : le même dépôt GitHub
- Root Directory : `/frontend`
- Dockerfile : détecté automatiquement
- Variable :

```env
VITE_API_URL=https://api.ivoireinnovationbtp.com/api
```

Vite injecte cette valeur au moment du build. Après toute modification de `VITE_API_URL`, redéployer le frontend.

## 3. PostgreSQL

Créer : `+ New` → `Database` → `PostgreSQL`.

Le backend utilise `DATABASE_URL` via la référence Railway :

```env
DATABASE_URL=${{Postgres.DATABASE_URL}}
```

## 4. Domaines

Frontend :

```text
www.ivoireinnovationbtp.com
```

Backend :

```text
api.ivoireinnovationbtp.com
```

Dans Railway, saisir uniquement le nom du domaine, sans `https://`.

## 5. DNS

Chez le registrar du domaine, suivre les enregistrements DNS affichés par Railway pour chaque service. Ne pas inventer les cibles DNS : copier exactement les valeurs données par Railway.

## 6. Fichiers utilisateurs

Le dossier `media/` contient les fichiers uploadés (logos et IFC). Sur Railway, le stockage local du conteneur n'est pas une solution durable pour ces fichiers. Pour conserver les uploads après redéploiement, monter un Railway Volume sur le chemin correspondant à `MEDIA_ROOT`, ou migrer vers un stockage objet compatible S3.

## 7. Mode IA

`DEMO_MODE=False` protège les endpoints IA, mais ton frontend actuel ne possède pas de système de connexion utilisateur. Dans ce mode, les endpoints IA protégés renverront donc `401` tant qu'une authentification n'est pas ajoutée.

Pour une démonstration publique temporaire, `DEMO_MODE=True` peut être utilisé, mais si `LLM_PROVIDER=gemini`, les appels peuvent consommer le quota/coût de la clé Gemini. Pour une démo sans clé, utiliser `LLM_PROVIDER=mock`.
