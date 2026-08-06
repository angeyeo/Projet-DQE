# Projet DQE — Pré-dimensionnement structurel assisté

Outil d'aide à la conception structurelle : pré-dimensionnement des sections (poteaux/poutres/semelles) à partir des formules BAEL/Eurocode, validation humaine obligatoire, et génération automatique du DQE (devis quantitatif estimatif).

---

## Stack

- **Backend** : Python + Django REST Framework
- **Frontend** : React + Bootstrap
- **Base de données** : PostgreSQL (SQLite en local pour le dev)
- **Export DQE** : ReportLab (PDF) / openpyxl (Excel)
- **Assistant IA** : Gemini API / Provider Mock local

---

## Structure du projet

```
projet-dqe/
├── backend/
│   ├── moteur_calcul/   # logique métier BAEL/Eurocode
│   ├── projets/         # modèles projet, éléments structurels, statuts, assistant IA, DQE
│   ├── api/             # serializers, vues DRF
│   └── manage.py
├── frontend/            # React + Bootstrap
└── docs/                # documentation du projet
```

---

## Installation en local

### Prérequis
- Python 3.11+
- Node.js 18+
- PostgreSQL (ou SQLite pour démarrer rapidement, déjà configuré par défaut en dev)

### 1. Cloner le projet

```bash
git clone https://github.com/votre-compte/projet-dqe.git
cd projet-dqe
```

### 2. Backend (Django)

```bash
cd backend
python -m venv venv
source venv/bin/activate        # Windows : venv\Scripts\activate
pip install -r requirements.txt
python manage.py migrate
python manage.py runserver
```

Le backend tourne sur `http://localhost:8000`.

### 3. Frontend (React)

Dans un autre terminal :

```bash
cd frontend
npm install
npm start
```

Le frontend tourne sur `http://localhost:3000`.

---

## Workflow Git

- `main` → toujours stable, sert pour la démo
- `dev` → intégration du travail de l'équipe
- `feature/xxx` → une branche par tâche

---

## Répartition de l'équipe (4 développeurs)

| Rôle | Responsabilité |
|---|---|
| Moteur de calcul | Fonctions Python à partir des formules BAEL/Eurocode fournies par le technicien BTP + tests unitaires |
| Backend DRF | Modèles, serializers, endpoints API |
| Frontend React + Bootstrap | Formulaire de saisie, tableau de validation |
| DQE + IA | Génération PDF/Excel, intégration de la couche IA d'interface |

---

## Jalons

| Semaine | Objectif |
|---|---|
| 1 | Moteur de calcul fonctionnel et testé |
| 2 | Interface de saisie + tableau de validation |
| 3 | Génération DQE + mise à jour automatique + couche IA + démo |

---

## Contact

Pour toute question sur l'installation ou le projet, contactez le chef de projet.

---

# Walkthrough — Module Assistant IA d'Interface

Ce document présente l'implémentation, les tests exécutés et les tests à venir pour le module d'assistance par Intelligence Artificielle sur la branche `feature/assistant-ia`.

## 1. Réalisations Effectuées

L'Assistant IA est déployé comme une **couche d’interface d'aide à la saisie et à la compréhension** :
- **Saisie naturelle (NLP)** : Extraction des paramètres de structure depuis une description textuelle.
- **Explicateur de calculs** : Génération de synthèses explicatives des pré-dimensionnements produits par le moteur.
- **Zéro écriture en base de données** : L'IA ne modifie jamais les modèles Django et ne modifie aucun statut (`VALIDE` / `PROPOSE`).
- **Verrou d'ingénieur obligatoire** : Toutes les réponses imposent la clé `validation_humaine_requise: true`.

## 2. Architecture du Package (`projets/services/assistant_ia/`)

```text
projets/services/assistant_ia/
├── __init__.py        # Export des fonctions publiques du module
├── client.py          # Client Gemini HTTPS (urllib) & Provider Mock local
├── explanations.py    # Générateur d'explications et Fallback local
├── parser.py          # Parser NLP pour la description projet
├── prompts.py         # Prompts système stricts et sécurisés
└── schemas.py         # Validation rigoureuse des entrées et typages (Anti-bool, Anti-NaN)
```

## 3. Endpoints REST Développés (Django REST Framework)

- **Structuration NLP** : `POST /api/assistant/structurer-projet/`
- **Explication Élément** : `POST /api/assistant/expliquer-element/`

## 4. Dispositifs de Sécurité Mis en Place

1. **Masquage de la clé Gemini** : Authentification via l'en-tête HTTP `x-goog-api-key` (clé absente des URL et des logs).
2. **Authentification & Rate Limiting (DRF)** : `permission_classes = [IsAuthenticated]` et `ScopedRateThrottle` (`assistant_structurer`: 10/min, `assistant_expliquer`: 20/min).
3. **Plafonnement des réponses LLM** : Limite de lecture à 64 Ko (`LLM_MAX_RESPONSE_BYTES=65536`) prévenant les dénis de service (OOM).
4. **Validation croisée des données** : Rejet automatique de toute contradiction entre la configuration (ex: `R+2`) et le nombre de niveaux déclaré (ex: 6).
5. **Anti-hallucination runtime & Mots interdits** :
   - Extrait et vérifie les nombres du texte généré par rapport aux données d'entrée.
   - Rejet vers `FALLBACK_LOCAL` si des nombres inédits ou des mots de fausse validation (`conforme`, `validé`, `sûr`, `optimal`) sont détectés.
6. **Mappage propre des erreurs** : Conversion des 401/403 de l'API Gemini en `HTTP 502 Bad Gateway` pour éviter la déconnexion de l'utilisateur.

## 5. Tests Réalisés et Validés

- **43/43 tests du module `projets` réussis** (`test_models`, `test_api`, `test_dqe`, `test_ai`).
- **Tests unitaires IA** : Validation de la structuration NLP, du rejet du texte vide, de la validation croisée des niveaux, du typage strict, de la post-validation anti-hallucination et des mots interdits.
- **Tests API & Sécurité** : Rejet de l'accès anonyme (HTTP 403), limitation de débit Throttling (HTTP 429), gestion des timeouts (HTTP 504) et des quotas (HTTP 503).
- **0 appel réseau distant** en mode de test (Provider Mock local).
- `python manage.py check` : **0 erreur**.

## 6. Tests à Venir (Prochaines étapes avant la production)

1. **Smoke Test Gemini en direct** : Test d'intégration réel avec une clé `GEMINI_API_KEY` valide sur le serveur de staging avant la démonstration officielle.
2. **Tests de charge sous trafic réel** : Évaluation de la latence et de la tenue en charge avec des requêtes simultanées en environnement de déploiement.
3. **Tests d'habilitation objet (BOLA / IDOR)** : Validation du cloisonnement des données dès l'implémentation du champ `projet.proprietaire` par le responsable backend principal.