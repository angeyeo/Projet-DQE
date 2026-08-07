# Projet DQE — Pré-dimensionnement structurel assisté

Outil d'aide à la conception structurelle : pré-dimensionnement des sections (poteaux/poutres/semelles) à partir des formules BAEL/Eurocode, validation humaine obligatoire, et génération automatique du DQE (devis quantitatif estimatif).

---

## Stack

- **Backend** : Python + Django REST Framework
- **Frontend** : React + Bootstrap
- **Base de données** : PostgreSQL (SQLite en local pour le dev)
- **Export DQE** : ReportLab (PDF) / openpyxl (Excel)

---

## Structure du projet

```
projet-dqe/
├── backend/
│   ├── moteur_calcul/   # logique métier BAEL/Eurocode
│   ├── projets/         # modèles projet, éléments structurels, statuts
│   ├── api/             # serializers, vues DRF
│   └── manage.py
├── frontend/            # React + Bootstrap
└── docs/                 # documentation du projet
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

### Pour contribuer

```bash
git checkout dev
git pull origin dev
git checkout -b feature/nom-de-ta-tache
# ... travail ...
git add .
git commit -m "Description claire du changement"
git push -u origin feature/nom-de-ta-tache
```

Puis ouvrir une **Pull Request** vers `dev` sur GitHub.

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

# Walkthrough — Module de génération automatique du DQE

Ce document présente les changements réalisés pour l’implémentation du module de génération du Devis Quantitatif Estimatif, les corrections appliquées après la revue technique et les résultats des différents tests.

## 1. Gestion de la branche et des dépendances

Le développement a été réalisé sur la branche dédiée :

```text
feature/export-dqe
```

Deux dépendances ont été ajoutées dans le fichier `requirements.txt` :

```text
reportlab==4.2.2
openpyxl==3.1.5
```

ReportLab est utilisé pour la génération des documents PDF, tandis qu’openpyxl permet de créer les fichiers Excel au format `.xlsx`.

## 2. Restructuration du package de services

L’ancien fichier unique `services.py` a été remplacé par un package `services/` afin de mieux séparer les responsabilités et d’éviter de surcharger un seul module.

La structure mise en place est la suivante :

```text
projets/
└── services/
    ├── __init__.py
    ├── calculations.py
    ├── dqe_calculator.py
    └── dqe_exporters.py
```

### `calculations.py`

Ce fichier contient la logique d’appel au module `moteur_calcul`. Le déplacement de cette logique permet également d’éviter les conflits et le masquage de modules liés à l’ancien fichier `services.py`.

### `dqe_calculator.py`

Ce fichier prend en charge :

* le calcul des quantités de béton ;
* le calcul des surfaces de coffrage ;
* le calcul ou l’estimation du poids d’acier ;
* l’application des prix unitaires ;
* le calcul des sous-totaux ;
* le calcul du total général ;
* l’intégration des postes manuels de main-d’œuvre.

### `dqe_exporters.py`

Ce fichier contient les fonctions de génération des exports PDF et Excel. Les fichiers sont créés directement en mémoire avec `BytesIO`, sans produire de fichiers temporaires permanents sur le serveur.

### `__init__.py`

Ce fichier expose les principales fonctions du package afin de faciliter leur importation dans les autres modules de l’application.

## 3. Calcul des quantités et des montants

Le calculateur DQE traite uniquement les projets dont tous les éléments structurels sont au statut `VALIDE`.

Les métrés sont calculés pour les trois types d’éléments pris en charge dans le MVP :

* poteaux ;
* poutres ;
* semelles.

### Béton

Le volume de béton est calculé en mètres cubes à partir des dimensions validées de chaque élément.

### Coffrage

La surface de coffrage est calculée en mètres carrés.

Pour les poutres, la face supérieure n’est pas incluse dans le coffrage. Pour les semelles, seul le coffrage latéral est pris en compte.

### Acier

Le calculateur utilise en priorité le poids total d’acier fourni par le moteur de calcul.

Lorsque cette donnée n’est pas disponible, un ratio estimatif en kilogrammes par mètre cube de béton est appliqué selon le type d’élément.

### Normalisation des unités

Les dimensions reçues en centimètres sont systématiquement converties en mètres grâce à la fonction utilitaire :

```python
cm_vers_m()
```

Les unités finales utilisées dans le DQE sont :

* mètre cube pour le béton ;
* mètre carré pour le coffrage ;
* kilogramme pour l’acier ;
* FCFA pour les montants.

### Précision financière

Les montants sont calculés avec le type `Decimal` et arrondis à l’unité FCFA selon la méthode `ROUND_HALF_UP`.

Cette approche évite les erreurs d’arrondi liées aux nombres flottants.

### Précision des quantités

Les quantités sont conservées avec une précision allant jusqu’à quatre chiffres après la virgule.

Par exemple :

```text
0,1875 m³
```

Les zéros inutiles placés à la fin sont retirés afin d’améliorer la lisibilité :

```text
3,0000 devient 3
0,4000 devient 0,4
0,1875 reste 0,1875
```

### Main-d’œuvre

Les postes enregistrés dans le modèle `PosteMainDoeuvre` sont ajoutés dynamiquement au devis.

Ils alimentent également le sous-total consacré à la main-d’œuvre.

## 4. Structure DQE commune

Le calculateur génère une structure intermédiaire unique contenant :

* les informations du projet ;
* les différentes lignes du devis ;
* les quantités ;
* les prix unitaires ;
* les montants ;
* les sous-totaux ;
* le total général.

Cette même structure est utilisée par les exportateurs PDF et Excel.

Ainsi, aucun calcul financier n’est refait dans les fichiers exportés, ce qui garantit la cohérence entre les deux formats.

## 5. Export PDF

Le PDF est généré avec ReportLab.

Il contient :

* un en-tête professionnel ;
* le nom et l’identifiant du projet ;
* la devise utilisée ;
* un tableau des lignes du DQE ;
* les quantités ;
* les prix unitaires ;
* les montants ;
* les sous-totaux par catégorie ;
* le total général ;
* un espace de validation et de signature pour l’ingénieur structure.

Les nombres sont présentés avec des espaces comme séparateurs de milliers afin de respecter un format de lecture adapté aux montants en FCFA.

Le document est généré en mémoire et retourné directement par l’API.

## 6. Export Excel

Le fichier Excel est généré avec openpyxl.

Il comprend :

* un titre ;
* les informations du projet ;
* un tableau structuré ;
* des styles de police ;
* des bordures ;
* des couleurs ;
* des largeurs de colonnes adaptées ;
* les sous-totaux ;
* le total général.

Les montants sont écrits directement à partir des valeurs produites par le calculateur Python. Aucune formule Excel ne recalcule les montants.

Cela garantit que le PDF et l’Excel utilisent exactement la même source de vérité.

Les cellules contenant les quantités utilisent le format :

```text
0.####
```

Ce format affiche jusqu’à quatre chiffres après la virgule sans ajouter de zéros inutiles.

## 7. Intégration dans l’API Django REST Framework

L’action `generer_dqe` a été complétée dans `ProjetViewSet`.

Les exports sont accessibles à travers les endpoints suivants :

```http
GET /api/projets/{id}/generer_dqe/?export=pdf
GET /api/projets/{id}/generer_dqe/?export=excel
```

Le paramètre `export` a été retenu à la place de `format` afin d’éviter tout conflit avec le système de négociation de format de Django REST Framework.

L’action effectue les vérifications suivantes :

* le format demandé doit être `pdf` ou `excel` ;
* le projet doit contenir des éléments structurels ;
* tous les éléments doivent être au statut `VALIDE` ;
* les données nécessaires aux calculs doivent être disponibles.

En cas d’erreur :

* un format non pris en charge renvoie une erreur HTTP 400 ;
* un élément non validé bloque l’export et renvoie une erreur HTTP 400 ;
* une erreur inattendue de génération est journalisée et renvoie une erreur HTTP 500.

Les fichiers sont retournés avec les bons en-têtes HTTP :

* `Content-Type` ;
* `Content-Disposition`.

Le nom du fichier est généré dynamiquement à partir du nom du projet et de la date.

## 8. Tests existants adaptés

Le test :

```text
test_calculer_element_renvoie_moteur_non_disponible
```

attendait auparavant une réponse HTTP 503, car les fonctions du moteur de calcul levaient encore une exception `NotImplementedError`.

Les fonctions du moteur étant désormais implémentées, ce test renvoyait naturellement une réponse HTTP 200.

Un `mock.patch` a été ajouté afin de simuler volontairement l’indisponibilité du moteur et de conserver un test valide du mécanisme de gestion d’erreur.

## 9. Nouveaux tests du module DQE

Un nouveau fichier a été créé :

```text
projets/tests_projets/test_dqe.py
```

Les tests couvrent notamment :

* le calcul des métrés d’un poteau ;
* le calcul des métrés d’une poutre ;
* le calcul des métrés d’une semelle ;
* l’agrégation des lignes d’un projet ;
* l’intégration de la main-d’œuvre ;
* le calcul des sous-totaux ;
* le calcul du total général ;
* la génération du PDF en mémoire ;
* la génération de l’Excel en mémoire ;
* l’export PDF par l’API ;
* l’export Excel par l’API ;
* le rejet d’un format invalide ;
* le blocage lorsqu’au moins un élément n’est pas validé.

## 10. Résultats des tests

Les 26 tests du module `projets` passent avec succès :

```text
Found 26 test(s).
Creating test database for alias 'default'...
System check identified no issues (0 silenced).
..........................
----------------------------------------------------------------------
Ran 26 tests in 0.176s

OK
Destroying test database for alias 'default'...
```

Les vérifications complémentaires suivantes ont également été effectuées :

```bash
python manage.py check
python manage.py makemigrations --check --dry-run
```

Résultats :

* aucune erreur de configuration Django ;
* aucune migration parasite détectée.

## 11. Vérification manuelle

Un projet de test complet a été créé avec :

* un poteau ;
* une poutre ;
* une semelle ;
* un poste de main-d’œuvre.

Le PDF et l’Excel ont été téléchargés et ouverts manuellement.

Le montant obtenu est identique dans le calculateur, le PDF et l’Excel :

```text
Sous-total Béton : 77 950 FCFA
Sous-total Coffrage : 107 520 FCFA
Sous-total Acier : 65 688 FCFA
Sous-total Main-d’œuvre : 250 000 FCFA

TOTAL GÉNÉRAL : 501 158 FCFA
```

La précision de `0,1875 m³` pour le béton du poteau est correctement affichée dans les deux fichiers.

## 12. Point connu hors périmètre

Cinq anciens tests du package `moteur_calcul` échouent encore.

Ces tests attendent toujours une exception `NotImplementedError`, alors que les fonctions réelles du moteur sont maintenant implémentées.

Ces tests doivent être actualisés par le responsable du moteur de calcul. Ils ne sont pas modifiés dans la branche `feature/export-dqe` afin de respecter la répartition des responsabilités.

Les cinq échecs restants de la suite globale proviennent uniquement de tests obsolètes du module moteur_calcul qui attendent encore NotImplementedError. Ils ne remettent pas en cause le fonctionnement du module DQE.

## Conclusion

Le module DQE est désormais :

* développé ;
* structuré ;
* intégré à l’API ;
* couvert par des tests ;
* vérifié manuellement ;
* cohérent entre les formats PDF et Excel.

La branche `feature/export-dqe` peut maintenant être soumise en Pull Request vers `dev`.


---

## État d'avancement Backend DRF (Samuel YEO)

### Module `projets` & API REST (100% Fonctionnel)
- **Modèles de données** : Gestion complète des entités `Projet` et `ElementStructurel` avec cycle de vie des statuts (`PROPOSE`, `MODIFIE`, `VALIDE`).
- **Endpoints API REST (`/api/`)** :
  - `POST /api/projets/` & `GET /api/projets/` : Gestion des projets.
  - `POST /api/elements/` & `GET /api/elements/?projet={id}` : Saisie et filtrage des éléments structurels.
- **Actions Métier & Verrou Logiciel** :
  - `POST /api/elements/{id}/calculer/` : Gestion contrôlée via `services.py` (retourne HTTP 503 tant que les formules BTP ne sont pas injectées).
  - `POST /api/elements/{id}/valider/` : Vérification des résultats et passage au statut `VALIDE`.
  - **Sécurité Verrou** : Toute modification post-validation bascule automatiquement l'élément au statut `MODIFIE`.
- **Tests Unitaires** : Validation à 100% de la suite `projets.tests_projets.test_api` (9/9 OK).