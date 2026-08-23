# Projet DQE — Backend & API REST

Module backend Django dédié au dimensionnement structurel BTP, à l'exécution du moteur de calcul et à la génération automatique de Devis Quantitatifs Estimatifs (DQE).

---

## 🚀 Livrables de la Phase 2 (Backend DRF — Samuel YEO)

Cette mise à jour intègre l'ensemble des fonctionnalités backend requises pour la Phase 2 afin de prendre en charge des cas de calcul BTP complexes.

### 📌 Module 6 : Lien Semelle-Poteau en Base de Données
- **Modèle Data** : Ajout du champ `poteau_associe` (`ForeignKey`) sur `ElementStructurel` pointant vers l'élément poteau supporté.
- **Service Calcul** : Propagation automatique de la dimension calculée du poteau (`cote_cm`) lors du pré-dimensionnement de la semelle associée dans `services/calculations.py`.
- **API Serializer** : Exposition du champ `poteau_associe` dans `ElementStructurelSerializer`.

### 📌 Module 7 : Dalles Pleines à l'API REST
- **Modèle Data** : Ajout du type d'élément `DALLE` (`dalle`) dans l'énumération des choix du modèle.
- **Raccordement Moteur** : Connexion sécurisée de l'action `/calculer/` avec la fonction `predimensionner_dalle()` du moteur de calcul via import dynamique.

### 📌 Module 4 : Semelles Filantes
- **Modèle Data** : Intégration du type d'élément `SEMELLE_FILANTE` (`semelle_filante`).
- **Raccordement Moteur** : Gestion des charges linéaires continues ($kN/m$) via `dimensionner_semelle_filante()` avec gestion d'import sécurisé.

### 📌 Module 2 : Charges Permanentes Composées (Multi-couches)
- **Modèle Data** : Création du modèle `CoucheCharge` (désignation, épaisseur en cm, poids volumique en $kN/m^3$) relié aux projets et éléments.
- **Service Calcul** : Implémentation du calcul automatique de la charge permanente surfacique cumulée $G$ ($kN/m^2$).
- **API REST** : Exposition du ViewSet `/api/couches-charges/` dans `views.py` et enregistrement de la route dans `api/urls.py`.

---

## 🧪 Validation & Suite de Tests
- **Périmètre couvert** : Endpoints REST API, verrous logiciels de validation, génération DQE, Assistant IA et intégration du Moteur BTP.
- **Résultat** : **100 % de réussite (59 tests sur 59 validés au vert — `OK`)**.
---

## ⚙️ Configuration de l'environnement (`.env`)

Le projet utilise `python-dotenv` pour charger automatiquement les variables d'environnement depuis un fichier `.env` à la racine du projet.

### Première installation (tous les développeurs)

```bash
# 1. Copier le template
cp .env.example .env

# 2. Installer les dépendances
pip install -r requirements.txt
```

Le fichier `.env` n'est **jamais commité** (il est dans `.gitignore`). Il reste local à chaque machine.

### Configuration pour la démo devant le jury

Ouvrir le fichier `.env` et vérifier que ces deux lignes sont présentes :

```env
DEMO_MODE=True
LLM_PROVIDER=mock
```

| Variable | Valeur démo | Explication |
|---|---|---|
| `DEMO_MODE` | `True` | Désactive l'authentification sur les endpoints IA |
| `LLM_PROVIDER` | `mock` | Utilise le client IA local (pas besoin de clé API) |

> ⚠️ **Si `DEMO_MODE` n'est pas à `True`, les endpoints IA renverront 401 Unauthorized.**

### Configuration pour le smoke test Gemini réel

Pour tester avec la vraie API Google Gemini :

```env
DEMO_MODE=True
LLM_PROVIDER=gemini
LLM_API_KEY=VOTRE_CLE_API_GOOGLE
```

> ⚠️ **Ne jamais commiter la clé API. Vérifier avec `git diff` avant tout commit.**

### Résumé des variables disponibles

| Variable | Défaut | Description |
|---|---|---|
| `DEMO_MODE` | `False` | `True` pour désactiver l'auth sur les endpoints IA |
| `LLM_PROVIDER` | `mock` | `mock` (simulation locale) ou `gemini` (API réelle) |
| `LLM_API_KEY` | _(vide)_ | Clé API Google Gemini (requise si `LLM_PROVIDER=gemini`) |
| `LLM_MODEL` | `gemini-3.5-flash` | Modèle Gemini à utiliser |
| `LLM_TIMEOUT_SECONDS` | `20` | Timeout des appels LLM en secondes |
| `LLM_MAX_RESPONSE_BYTES` | `65536` | Taille max de la réponse LLM |

## 🚂 Déploiement Railway (React + Django)

Le dépôt est organisé comme un monorepo avec un backend Django à la racine et un frontend React/Vite dans `frontend/`.

### Services Railway

- **Backend Django** : racine du dépôt (`/`), domaine conseillé `api.ivoireinnovationbtp.com`.
- **Frontend React** : Root Directory `/frontend`, domaine conseillé `www.ivoireinnovationbtp.com`.
- **PostgreSQL** : service PostgreSQL Railway.

### Variables Backend

```env
SECRET_KEY=<secret Railway>
DEBUG=False
ALLOWED_HOSTS=api.ivoireinnovationbtp.com
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

### Variable Frontend

```env
VITE_API_URL=https://api.ivoireinnovationbtp.com/api
```

Le fichier `frontend/Dockerfile` construit Vite puis sert `dist/` avec Caddy, avec fallback SPA vers `index.html`.
