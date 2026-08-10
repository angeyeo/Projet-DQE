# Walkthrough — Module Assistant IA d'Interface

Ce document présente les fonctionnalités développées, les tests exécutés et les tests à venir pour le module d'assistance par Intelligence Artificielle sur la branche `feature/assistant-ia`.

---

## 1. Réalisations Effectuées

L'Assistant IA est déployé comme une **couche d’interface d'aide à la saisie et à la compréhension** :
- **Saisie naturelle (NLP)** : Extraction des paramètres de structure depuis une description textuelle.
- **Explicateur de calculs** : Génération de synthèses explicatives des pré-dimensionnements produits par le moteur.
- **Zéro écriture en base de données** : L'IA ne modifie jamais les modèles Django et ne modifie aucun statut (`VALIDE` / `PROPOSE`).
- **Verrou d'ingénieur obligatoire** : Toutes les réponses imposent la clé `validation_humaine_requise: true`.

---

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

---

## 3. Endpoints REST Développés (Django REST Framework)

- **Structuration NLP** : `POST /api/assistant/structurer-projet/`
  - *Payload* : `{"description": "Bâtiment R+2 commercial avec des portées de 6 mètres."}`
- **Explication Élément** : `POST /api/assistant/expliquer-element/`
  - *Payload* : `{"element_id": 42}`

---

## 4. Dispositifs de Sécurité Mis en Place

1. **Masquage de la clé Gemini** : Authentification via l'en-tête HTTP `x-goog-api-key` (clé absente des URL et des logs).
2. **Authentification & Rate Limiting (DRF)** :
   - Restriction aux utilisateurs connectés (`IsAuthenticated`).
   - Limitation de fréquence via `ScopedRateThrottle` (`assistant_structurer`: 10/min, `assistant_expliquer`: 20/min).
3. **Plafonnement des réponses LLM** : Limite de lecture à 64 Ko (`LLM_MAX_RESPONSE_BYTES=65536`) prévenant les dénis de service (OOM).
4. **Validation croisée des données** : Rejet automatique de toute contradiction entre la configuration (ex: `R+2`) et le nombre de niveaux déclaré (ex: 6).
5. **Anti-hallucination runtime & Mots interdits** :
   - Extrait et vérifie les nombres du texte généré par rapport aux données d'entrée.
   - Rejet vers `FALLBACK_LOCAL` si des nombres inédits ou des mots de fausse validation (`conforme`, `validé`, `sûr`, `optimal`) sont détectés.
6. **Mappage propre des erreurs** : Conversion des 401/403 de l'API Gemini en `HTTP 502 Bad Gateway` pour éviter la déconnexion de l'utilisateur.

---

## 5. Tests Réalisés et Validés

- **43/43 tests du module `projets` réussis** (`test_models`, `test_api`, `test_dqe`, `test_ai`).
- **Tests unitaires IA** : Validation de la structuration NLP, du rejet du texte vide, de la validation croisée des niveaux, du typage strict, de la post-validation anti-hallucination et des mots interdits.
- **Tests API & Sécurité** : Rejet de l'accès anonyme (HTTP 403), limitation de débit Throttling (HTTP 429), gestion des timeouts (HTTP 504) et des quotas (HTTP 503).
- **0 appel réseau distant** en mode de test (Provider Mock local).
- `python manage.py check` : **0 erreur**.

---

## 6. Tests à Venir (Prochaines étapes avant la production)

1. **Smoke Test Gemini en direct** : Test d'intégration réel avec une clé `GEMINI_API_KEY` valide sur le serveur de staging avant la démonstration officielle.
2. **Tests de charge sous trafic réel** : Évaluation de la latence et de la tenue en charge avec des requêtes simultanées en environnement de déploiement.
3. **Tests d'habilitation objet (BOLA / IDOR)** : Validation du cloisonnement des données dès l'implémentation du champ `projet.proprietaire` par le responsable backend principal.
