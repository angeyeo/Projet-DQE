# Walkthrough — Module Assistant IA d'Interface

Ce document présente l'implémentation, les réorganisations et les durcissements de sécurité réalisés pour le module d'assistance par Intelligence Artificielle sur la branche `feature/assistant-ia`.

---

## 1. Objectif et Périmètre du Module IA

L'Assistant IA intervient exclusivement comme une **couche d’interface d'aide à la saisie et à la compréhension** :
- **Saisie naturelle (NLP)** : Extraction des paramètres de structure depuis une description textuelle.
- **Explication des calculs** : Génération de synthèses explicatives des pré-dimensionnements produits par le moteur.
- **Zéro écriture en base** : Aucun `save()` n'est exécuté par l'IA ; l'IA ne modifie jamais le statut d'un élément (`VALIDE` / `PROPOSE`).
- **Verrou d'ingénieur obligatoire** : Toutes les réponses imposent `validation_humaine_requise: true`.

---

## 2. Architecture du Package (`projets/services/assistant_ia/`)

```text
projets/services/assistant_ia/
├── __init__.py        # Façade publique et export des fonctions
├── client.py          # Client Gemini HTTPS (urllib) & Provider Mock local
├── explanations.py    # Générateur d'explications et Fallback local
├── parser.py          # Parser NLP pour la description projet
├── prompts.py         # Prompts système stricts et sécurisés
└── schemas.py         # Validation rigoureuse des entrées et typages (Anti-bool, Anti-NaN)
```

---

## 3. Endpoints REST Exposés (Django REST Framework)

- **Structuration NLP** : `POST /api/assistant/structurer-projet/`
  - *Payload* : `{"description": "Bâtiment R+2 commercial avec des portées de 6 mètres."}`
- **Explication Élément** : `POST /api/assistant/expliquer-element/`
  - *Payload* : `{"element_id": 42}`

---

## 4. Mesures de Sécurité & Durcissement CIA

1. **Masquage de la clé Gemini** : Authentification via l'en-tête HTTP `x-goog-api-key` (clé absente des URL et des logs).
2. **Authentification & Rate Limiting (DRF)** :
   - Restriction aux utilisateurs connectés (`IsAuthenticated`).
   - Limitation de fréquence via `ScopedRateThrottle` (`assistant_structurer`: 10/min, `assistant_expliquer`: 20/min).
3. **Plafonnement des réponses LLM** : Limite de lecture à 64 Ko (`LLM_MAX_RESPONSE_BYTES=65536`) prévenant les attaques par déni de service (OOM).
4. **Validation croisée des données** : Rejet automatique de toute contradiction entre la configuration (ex: `R+2`) et le nombre de niveaux déclaré (ex: 6).
5. **Anti-hallucination runtime & Mots interdits** :
   - Extrait et vérifie les nombres du texte généré par rapport aux données d'entrée.
   - Rejet vers `FALLBACK_LOCAL` si des nombres inédits ou des mots de fausse validation (`conforme`, `validé`, `sûr`, `optimal`) sont détectés.
6. **Mappage propre des erreurs** : Conversion des 401/403 de l'API Gemini en `HTTP 502 Bad Gateway` pour éviter la déconnexion de l'utilisateur.

---

## 5. Résultats des Tests

- **43/43 tests du module `projets` réussis** (`test_models`, `test_api`, `test_dqe`, `test_ai`).
- **Suite globale backend** : 53 tests découverts (48 réussis, 5 échecs obsolètes connus dans `moteur_calcul`).
- **0 appel réseau distant** en mode de test (Provider Mock local).
- `python manage.py check` : **0 erreur**.

---

## 6. Limite connue (BOLA / IDOR)

L'accès aux objets exige l'ajout d'une relation de propriété `projet.proprietaire` sur les modèles Django. Le module IA est **prêt pour la revue et une démonstration contrôlée**, mais **non prêt pour une exposition publique multi-utilisateur** tant que ce champ n'est pas ajouté en base de données.
