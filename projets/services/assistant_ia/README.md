# Module `projets/services/assistant_ia/` — Assistant IA d'Interface

Ce module fournit la couche d'assistance par Intelligence Artificielle (Gemini API / Mock) pour le pré-dimensionnement et l'explication des résultats de calcul.

---

## 🎯 Responsabilité du Module

L'Assistant IA est strictement une **couche d'interface et d'aide à la saisie / compréhension** :
- **Saisie naturelle (NLP)** : Extraction des paramètres du projet à partir d'une description en langage naturel.
- **Explications pédagogiques** : Rédige des synthèses claires des résultats de calcul pour les éléments structurels (poteaux, poutres, semelles).
- **Zéro écriture en BDD** : L'IA ne modifie jamais directement la base de données ni le statut d'un élément (`VALIDE` / `PROPOSE`).
- **Verrou humain obligatoire** : Toutes les réponses contiennent `validation_humaine_requise: true`.

---

## 📁 Architecture du Module

```text
projets/services/assistant_ia/
├── __init__.py        # Export des fonctions publiques
├── client.py          # Provider Gemini (REST urllib HTTPS) & Mock local
├── explanations.py    # Génération d'explications et Fallback local
├── parser.py          # Traitement NLP de la description projet
├── prompts.py         # Prompts système stricts et sécurisés
└── schemas.py         # Validation rigoureuse des entrées / sorties (Anti-bool, Anti-NaN)
```

---

## 🌐 Endpoints API (Django REST Framework)

Les vues sont exposées via `projets/views.py` et déclarées dans `api/urls.py` :

### 1. Structuration de description projet
- **Route** : `POST /api/assistant/structurer-projet/`
- **Body** : `{"description": "Bâtiment R+2 à usage commercial avec des portées de 6 mètres."}`
- **Réponse HTTP 200** :
  ```json
  {
    "donnees": {
      "nombre_niveaux": 3,
      "configuration": "R+2",
      "usage": "COMMERCE",
      "portee_m": 6.0,
      "hauteur_niveau_m": null,
      "contrainte_sol_kn_m2": null
    },
    "donnees_manquantes": [],
    "avertissements": [
      "La contrainte admissible du sol doit être confirmée par une étude géotechnique."
    ],
    "confirmation_requise": true
  }
  ```

### 2. Explication d'un élément structurel
- **Route** : `POST /api/assistant/expliquer-element/`
- **Body** : `{"element_id": 42}`
- **Réponse HTTP 200** :
  ```json
  {
    "element_id": 42,
    "repere": "P1",
    "type_element": "POTEAU",
    "explication": "Le poteau P1 de section 30 × 30 cm a été calculé pour reprendre les charges transmises...",
    "source": "GEMINI",
    "explication_technique_disponible": true,
    "validation_humaine_requise": true
  }
  ```

---

## ⚙️ Configuration & Fournisseurs (Providers)

Le fournisseur est contrôlé par les variables d'environnement dans `.env` :

```env
# Mode Développement / CI / Tests (Aucun appel réseau)
LLM_PROVIDER=mock

# Mode Production avec Gemini
LLM_PROVIDER=gemini
LLM_API_KEY=AIzaSy...
LLM_MODEL=gemini-1.5-flash
LLM_TIMEOUT_SECONDS=20
```

---

## 🧪 Exécution des Tests

Les tests unitaires et d'API du module IA se trouvent dans `projets/tests_projets/test_ai.py` :

```bash
python manage.py test projets.tests_projets.test_ai
```
