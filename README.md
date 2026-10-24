# Projet DQE — Ivoire Innovation BTP

Application web de **pré-dimensionnement de structures en béton armé** et de **production de DQE** (Devis Quantitatif et Estimatif) pour les bureaux d'études BTP.

À partir des paramètres d'un bâtiment, ou d'un plan importé (IFC ou DXF), le logiciel :
- calcule la descente de charges ;
- dimensionne poteaux, poutres, semelles, longrines, chaînages et dalles (BAEL 91 mod. 99) ;
- fait valider chaque élément par un ingénieur ;
- produit le DQE par lots, au barème du cabinet, avec les exports PDF et Excel, le plan de fondation et la fiche d'approvisionnement.

> **Règle d'or : zéro fausse donnée.**
> - Une valeur manquante est demandée, ou affichée comme hypothèse : jamais inventée.
> - Chaque ligne du DQE indique l'origine de sa quantité :
>   - **calculée** : par le moteur, à partir des données du projet ;
>   - **saisie** : par l'utilisateur, ou reprise de la bibliothèque avec son origine ;
>   - **estimée** : par un ratio de référence documenté.
> - Si le serveur échoue, l'interface affiche l'erreur, jamais un résultat de remplacement.

---

## Sommaire

- [Fonctionnalités](#fonctionnalités)
- [Démarrage rapide](#démarrage-rapide)
- [Variables d'environnement](#variables-denvironnement)
- [Tests](#tests)
- [Architecture](#architecture)
- [Structure du dépôt](#structure-du-dépôt)
- [Moteur de calcul](#moteur-de-calcul)
- [Assistant IA](#assistant-ia)
- [Déploiement](#déploiement)
- [Contribuer](#contribuer)
- [Limites connues](#limites-connues)
- [Documentation](#documentation)

---

## Fonctionnalités

| Domaine | Ce qui existe |
|---|---|
| **Cabinets et comptes** | Inscription d'un cabinet, invitations, 3 rôles (admin, ingénieur, technicien), JWT avec rotation, mot de passe oublié. Données isolées par cabinet. |
| **Projets** | Trame régulière générée par le moteur, ou import de plan **IFC** / **DXF** (AutoCAD, ArchiCAD) avec aperçu avant création. |
| **Calcul** | Descente de charges (G, Q, ELU, ELS, dégression, poids propre, toiture dalle ou charpente, murs placés tronçon par tronçon). Dimensionnement des poteaux, poutres, semelles isolées et filantes, longrines, chaînages et dalles. |
| **Contrôle** | Plausibilité des paramètres et des résultats, analyse de cohérence, validation et verrouillage par un ingénieur. **Le DQE refuse de se générer tant qu'un élément n'est pas validé.** |
| **Chiffrage** | DQE par lots (00 à 15), postes complémentaires (saisis, à ratio ou repris de la bibliothèque), déboursé sec, marge, TVA, TTC ; aucun taux supposé. |
| **Bibliothèque** | Ouvrages types du cabinet avec l'origine et la date du prix, import d'un DQE Excel (aperçu, puis confirmation tout ou rien). |
| **Exports** | DQE en PDF et en Excel, plan de fondation en DXF et en PDF, fiche d'approvisionnement en Excel (ciment, sable, gravier, acier, agglos, pertes comprises). |
| **Analyse** | Variantes « et si ? » recalculées par le moteur sans rien enregistrer ; tableaux de bord du cabinet et du projet. |
| **IA (facultative)** | Structuration d'une description en texte libre, explication d'un calcul, suggestion de poste, lecture d'une image de plan en aperçu. L'IA **propose** ; elle ne décide jamais d'un chiffre. |

---

## Démarrage rapide

### Prérequis

| Outil | Version | Pourquoi |
|---|---|---|
| Python | 3.12 ou plus (développé en 3.13) | Exigé par Django 6 |
| Node.js | 18 ou plus | Pour Vite 5 |
| Git | — | — |

### 1. Backend (Django)

```bash
git clone -b dev https://github.com/angeyeo/Projet-DQE.git
cd Projet-DQE

python -m venv venv
source venv/bin/activate              # Windows : venv\Scripts\activate
pip install -r requirements.txt

cp .env.example .env
```

Dans `.env`, pour le développement local, il suffit de :

```dotenv
DEBUG=True
SECRET_KEY=une-cle-locale-quelconque
# Laisser DATABASE_URL vide : la base SQLite locale (db.sqlite3) est utilisée.
# LLM_PROVIDER vide = assistant IA désactivé (erreur 503 explicite). Voir « Assistant IA ».
```

Puis :

```bash
python manage.py migrate
python manage.py runserver            # API sur http://127.0.0.1:8000/api/
```

### 2. Frontend (React + Vite)

Dans un second terminal :

```bash
cd frontend
npm install
npm run dev                           # http://localhost:5173
```

Vite redirige `/api` vers `http://127.0.0.1:8000` (`frontend/vite.config.js`) : il n'y a rien d'autre à configurer en local.

### 3. Premier compte

Ouvrez http://localhost:5173, puis cliquez sur **Inscription**. Cette inscription crée le cabinet et son compte administrateur. Depuis le menu **Équipe**, l'administrateur invite ensuite les ingénieurs et les techniciens.

En local, sans `EMAIL_HOST`, les e-mails (invitations, mot de passe oublié) s'affichent dans le terminal de `runserver`.

---

## Variables d'environnement

Le modèle est `.env.example`. **Ne jamais committer `.env`.**

| Variable | Défaut | Rôle |
|---|---|---|
| `DEBUG` | `False` | `True` en local uniquement |
| `SECRET_KEY` | — | **Obligatoire** dès que `DEBUG=False` (le serveur refuse de démarrer sans) |
| `ALLOWED_HOSTS` | `localhost,127.0.0.1` | Domaines servis |
| `CORS_ALLOWED_ORIGINS`, `CSRF_TRUSTED_ORIGINS` | — | Origine du frontend en production |
| `DATABASE_URL` | vide → SQLite | PostgreSQL en production (`postgres://…`) |
| `DATABASE_SSL_REQUIRE` | `True` | `False` pour une base sans TLS |
| `SECURE_SSL_REDIRECT`, `SECURE_HSTS_SECONDS` | `False`, `0` | HTTPS strict, à activer en production derrière un proxy TLS |
| `EMAIL_HOST`, `EMAIL_PORT`, `EMAIL_HOST_USER`, `EMAIL_HOST_PASSWORD`, `EMAIL_USE_TLS`, `EMAIL_USE_SSL`, `EMAIL_TIMEOUT_SECONDS`, `DEFAULT_FROM_EMAIL` | vide → console | Envoi SMTP |
| `FRONTEND_URL` | — | Liens des e-mails (activation, réinitialisation) |
| `LLM_PROVIDER` | vide → IA désactivée | `gemini` ; `mock` pour les tests et les démonstrations (réponses marquées « MOCK ») |
| `LLM_API_KEY`, `LLM_MODEL`, `LLM_TIMEOUT_SECONDS`, `LLM_MAX_RESPONSE_BYTES` | — | Configuration de Gemini |
| `PLAN_IMAGE_MAX_BYTES` | 5 Mo | Taille maximale d'une image de plan |

Côté frontend, `VITE_API_URL` est facultatif : il sert à pointer vers une API distante au lieu du proxy local.

---

## Tests

```bash
python manage.py test                                # 580 tests (environ 2 minutes)
python manage.py test moteur_calcul                  # moteur de calcul seul
python manage.py makemigrations --check --dry-run    # modèles et migrations alignés ?
cd frontend && npm run build                         # le frontend compile ?
```

- Les tests de calcul utilisent des **cas de référence vérifiés à la main**, avec des prix explicitement nommés « TEST ».
- Pas encore de tests frontend (issue #62).

---

## Architecture

```
React (frontend/src)                         Django REST (projets/, api/)                  Moteur (moteur_calcul/)
───────────────────                          ────────────────────────────                  ───────────────────────
components/  →  hooks/  →  api/dqeService.js  ──JSON/JWT──▶  urls → views → serializers  ──▶  formules BAEL (Python pur)
(affiche,          (seul point de                              → services/ (trame, DQE,          hypothèses, unités,
 ne calcule         conversion des champs                        exports, IA…)                   plausibilité,
 rien de métier)    camelCase ↔ snake_case)                    → models → base                   import IFC / DXF
```

- **Django est la source de vérité.** Toute donnée est validée côté serveur ; le frontend ne fait que du confort de saisie.
- **Cloisonnement** : chaque requête est filtrée par le cabinet de l'utilisateur (`FiltreCabinetMixin`). Un objet d'un autre cabinet donne une erreur 404.
- **Droits** (`projets/permissions.py`) : un technicien prépare ; un ingénieur ou l'admin valide et modifie la bibliothèque ; l'admin gère l'équipe et les prix.
- **Contrat d'API** : renommer un champ côté Django implique de modifier `frontend/src/api/dqeService.js`.

---

## Structure du dépôt

```
backend/            settings.py, urls.py (racine), wsgi
api/urls.py         toutes les routes /api/
projets/
  models.py         Projet, ElementStructurel, PosteComplementaire, OuvrageType,
                    EntrepriseParametres (le cabinet), Profil, EvenementProduit, JournalAppelIA
  views.py          ViewSets et actions (trame, import de plan, DQE, exports, variantes…)
  serializers.py    validations métier des entrées
  permissions.py    rôles et cloisonnement
  services/         trame_service, calculations, dqe_calculator, pdf_dqe, dqe_exporters,
                    approvisionnement, plan_fondation, variantes, import_bibliotheque,
                    analytics, assistant_ia/
  management/commands/  audit_donnees_production, rattacher_projets_orphelins
  tests_projets/    tests d'API et de bout en bout
moteur_calcul/
  constantes.py     toutes les constantes, chacune avec sa source
  hypotheses.py     origine de chaque hypothèse (saisie, forfait, défaut, validée)
  formules/         descente_charges, trame, dimensionnement_{poteaux,poutres,semelles,dalles},
                    postes_ratio, methode_caquot, complements_plan_coffrage
  import_ifc/, import_dxf/   lecture des plans
  plausibilite.py   contrôles de plausibilité
  tests_moteur_calcul/
frontend/src/
  App.jsx           navigation entre les vues
  api/dqeService.js tous les appels API
  components/       étapes 1 à 4, validation, bibliothèque, tableaux de bord…
```

---

## Moteur de calcul

| Calcul | Ce que fait le moteur |
|---|---|
| Référentiel | BAEL 91 mod. 99 |
| Descente de charges | `Nu = 1,35 G + 1,5 Q`. Dégression 1 / 0,9 / 0,8 / 0,7. Murs : `q = p × (h_étage − h_poutre) × (1 − baies)`. |
| Poteaux | Flambement (refus explicite au-delà de λ = 70), acier `A = [Nu/α − Br·fc28/(0,9 γb)] / (fe/γs)` |
| Poutres | `h = max(L/8 ; 25 cm)`, flexion et effort tranchant |
| Semelles | `A = √(N / σsol)` (ELU par défaut, validé par le technicien), aciers par la méthode des bielles |
| DQE | Seuls les résultats **validés**. Calcul en `Decimal`, arrondi au franc près en fin de chaîne seulement. |

- **Valeurs par défaut** : sol à 180 kN/m², G forfaitaire de 5 kN/m², fc28 = 25 MPa. Chaque valeur par défaut est **signalée** dans les résultats comme hypothèse.
- **Acier** : calculé pour les semelles ; **estimé par ratio** pour les poteaux, poutres, longrines et dalles (ligne marquée « estimé »).
- **Règles en attente de validation par le technicien** : issue #64.
- Le détail des formules, des hypothèses et des cas limites est dans l'audit du 17/10/2026 (livrable 04).

---

## Assistant IA

- **Fournisseur** : Google Gemini, activé par `LLM_PROVIDER=gemini` et `LLM_API_KEY`.
- **Sans configuration** : les assistants renvoient une erreur 503 « assistant non configuré », jamais une réponse simulée.
- **Garde-fous** :
  - réponses validées par des schémas stricts ;
  - termes interdits (« conforme », « validé »…) ;
  - un texte qui contient un nombre absent des données fournies est rejeté ;
  - chaque appel est journalisé (`JournalAppelIA`) avec sa source (`GEMINI`, `MOCK`, `LOCAL`, `FALLBACK_LOCAL`) ;
  - limites d'appels par minute.
- **Rien n'est appliqué au projet sans un clic de l'utilisateur.**
- ⚠️ Les descriptions et les images de plans sont envoyées à Google (issue #71).

---

## Déploiement

- **Hébergement** : pas encore choisi (l'application n'est pas en production). Le `Procfile` décrit le lancement
  standard, valable chez tout hébergeur qui le lit :

  ```
  python manage.py migrate --noinput && python manage.py collectstatic --noinput && gunicorn backend.wsgi:application --bind 0.0.0.0:$PORT --timeout 120
  ```

  `--timeout 120` : la lecture d'un plan de 50 Mo dépasse le délai par défaut de gunicorn (30 s), issue #90.
- **Fichiers déposés** (`media/` : plans, logos) : stockés sur le disque du serveur. L'hébergement retenu devra
  offrir un disque **persistant** (ou un stockage de fichiers), sinon ils sont perdus à chaque redéploiement.

- **Variables de production** : `DEBUG=False`, `SECRET_KEY`, `DATABASE_URL` (PostgreSQL), `ALLOWED_HOSTS`, `CORS_ALLOWED_ORIGINS`, `CSRF_TRUSTED_ORIGINS`, SMTP et Gemini.
- **Contrôle avant mise en ligne** :

  ```bash
  python manage.py check --deploy
  ```

- **Commandes d'administration** :

  ```bash
  python manage.py audit_donnees_production [--json]                          # lecture seule, n'écrit rien
  python manage.py rattacher_projets_orphelins --dry-run                       # liste sans modifier
  python manage.py rattacher_projets_orphelins --cabinet <id> --projets <id…>  # rattachement explicite
  ```

- **Migrations** : toutes les migrations récentes sont **additives**. Toute migration qui supprime des données doit être validée explicitement avant d'être appliquée en production.

---

## Contribuer

1. Partir de `dev` : `git checkout dev && git pull`.
2. Créer une branche : `feature/<sujet>` ou `fix/<sujet>`.
3. Lancer `python manage.py test` et `npm run build` avant de pousser.
4. Ouvrir une pull request **vers `dev`**, avec `Closes #N` dans la description, pour que la tâche se ferme et avance sur le tableau.
5. Une relecture est nécessaire avant la fusion.

**Suivi des tâches** :
- [Issues du dépôt](https://github.com/angeyeo/Projet-DQE/issues) ;
- [Tableau du projet](https://github.com/users/angeyeo/projects/1).

Étiquettes : `P0` à `P3` pour la priorité, `moteur`, `backend`, `ia`, `metier` et `securite` pour le domaine.

**Règles du projet** :
- **Aucune donnée inventée.** Une valeur absente se demande ou s'affiche comme hypothèse.
- **Aucun repli silencieux.** Une erreur s'affiche clairement à l'utilisateur.
- **Une constante du moteur ne change pas sans décision tracée**, avec sa source en commentaire dans `constantes.py`.
- **Ne jamais committer** `.env`, `db.sqlite3` ni des fichiers de clients (`media/`).

---

## Limites connues

| Limite | Issue |
|---|---|
| Anciens fichiers de `media/` (plans de clients) toujours présents dans l'historique git | #61 |
| Acier des poteaux, poutres, longrines, dalles et chaînages estimé par ratio (marqué « estimé ») | #79 |
| Poutres continues calculées comme isostatiques (règle B3 validée ; Caquot non branché) | #68 |
| Main-d'œuvre : parts saisies par le cabinet seulement, pas de temps unitaires ni de déboursés détaillés | #85 |
| Poteaux très élancés (hauteur d'étage de 5 m et plus) refusés par le moteur | audit du 24/10 |

---

## Documentation

| Document | Contenu |
|---|---|
| `moteur_calcul/README.md` | Détail du moteur |
| `walkthrough_ia.md` | Parcours de l'assistant IA |
| `docs_audit_mathematique_2026-10-06.md` | Audit mathématique initial |
| Audit d'équipe du 17/10/2026 | État vérifié du projet, anomalies, plan d'action |