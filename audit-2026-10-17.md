# Audit du projet DQE — 17/10/2026

Documentation de référence et support de la réunion technique d'équipe.

## Ce que couvre cet audit

- Le **code de référence** du projet : la version livrée le 16/10/2026 dans le zip `Projet-DQE-mise-a-jour-16-10-import.zip`.
  - Dernier commit : « Bibliothèque : message explicite quand le serveur n'a pas la route (404) ».
- **Vérifié le 17/10 : la branche `dev` de GitHub (`angeyeo/Projet-DQE`, commit `16c90eb`) est identique à ce code** sur les 223 fichiers communs. Seuls trois anciens composants inutilisés y subsistent (A-23). Sur `dev` : 580 tests OK, migrations cohérentes. **Les conclusions de cet audit valent donc pour `dev`.**
- Audit en **lecture seule**. Aucun fichier de code, aucune donnée et aucune configuration n'ont été modifiés.
- Seule exception : la suppression des fichiers IFC temporaires que la suite de tests écrit dans `media/` (voir l'anomalie A-07).

## Ce qu'il ne couvre pas (à lire avant tout)

1. **L'historique Git** de `dev` a été lu sur ses 50 derniers commits (du 23/09 au 16/10). Contributeurs : RayannChadrac, Ange Yeo et ange-dev, aneyves11-boop, Elamus. L'historique plus ancien n'a pas été parcouru.
2. **Le serveur déployé** (Railway, voir `RAILWAY_DEPLOYMENT.md`) n'a pas été consulté.
3. **L'IA réelle (Gemini)** n'a pas été appelée : aucune clé n'est disponible dans l'environnement d'audit. Le comportement réseau n'est vérifié que par les tests, qui simulent le fournisseur.

## Commandes exécutées (preuves)

| Commande | Résultat |
|---|---|
| `python manage.py test` | **580 tests, OK** (environ 110 à 200 s) |
| `python manage.py check` | aucun problème |
| `python manage.py makemigrations --check --dry-run` | « No changes detected » : modèles et migrations cohérents |
| `python manage.py check --deploy` (avec `DEBUG=False`) | 2 avertissements : W004 HSTS, W008 SSL_REDIRECT (voir 08) |
| `npm run build` (frontend) | build OK ; **aucun test automatisé frontend** (pas de script `test`) |

## Les livrables

| N° | Fichier | Pour qui |
|---|---|---|
| 1 | `01_synthese_executive.md` | tous |
| 2 | `02_inventaire_fonctionnalites.md` | tous |
| 3 | `03_architecture.md` | développeurs |
| 4 | `04_moteur_de_calcul.md` | chef de projet, développeur Django, technicien |
| 5 | `05_backend_frontend.md` | développeur Django |
| 6 | `06_module_ia.md` | développeur IA |
| 7 | `07_verifications_btp.md` | technicien BTP |
| 8 | `08_anomalies_risques.md` | tous |
| 9 | `09_support_reunion.md` (introduction, discours de 10 à 15 min, questions) | chef de projet |
| 10 | `10_plan_action_responsabilites.md` | tous |
| 11 | `11_compte_rendu_vierge.md` | secrétaire de séance |
| 12 | `12_couverture_audit.md` | tous |

## Convention

| Marque | Sens |
|---|---|
| **[VÉRIFIÉ]** | constaté dans le code, et dans un test ou une exécution |
| **[CODE]** | présent dans le code, sans démonstration d'exécution complète |
| **[DÉDUIT]** | conclusion tirée de plusieurs éléments, à confirmer |
| **[À CONFIRMER BTP]** | règle métier qui attend la validation du technicien ou de l'ingénieur |

Les chemins sont relatifs à la racine du dépôt.


---

# 1. Synthèse exécutive

## En une phrase

Le projet DQE est une application web multi-cabinet (Django REST et React) qui, à partir des paramètres d'un bâtiment ou d'un plan importé, **pré-dimensionne la structure en béton armé**, puis **chiffre un DQE** au barème du cabinet. Le DQE n'est produit qu'après validation des éléments par un ingénieur, et il est **tracé** : pour chaque quantité, on sait si elle est calculée, saisie ou estimée.

## État général

| Aspect | Constat |
|---|---|
| Taille | Environ 14 500 lignes de Python métier (hors migrations et tests) et environ 7 100 lignes de React |
| Tests | 580 tests backend au vert ; 0 test frontend |
| Cohérence du schéma | Modèles et migrations alignés (28 migrations `projets`, toutes additives depuis la 0024) |
| Sécurité | JWT avec rotation et liste noire, cloisonnement par cabinet, 3 rôles, matrice de sécurité testée (`test_matrice_securite.py`, `test_securite_routes.py`) |
| Principe « zéro fausse donnée » | Largement respecté : valeur manquante = erreur explicite ou hypothèse affichée. Exceptions à surveiller : 08, A-01 à A-04 |
| Base métier | Formules BAEL 91 mod. 99 codées et testées. Une partie des règles est validée par l'ingénieur BTP (07, 10 et 12/10) ; d'autres attendent encore sa confirmation (07) |

## Ce qui fonctionne aujourd'hui (vérifié par les tests)

- Comptes, cabinets, invitations, rôles (admin, ingénieur, technicien), mot de passe oublié.
- Projets, avec deux modes de création :
  - **trame régulière** générée par le moteur ;
  - **import de plan IFC ou DXF**, avec aperçu et confirmation.
- Descente de charges (G, Q, ELU, ELS) avec dégression, poids propre, toiture en dalle ou en charpente, et **murs placés tronçon par tronçon**.
- Dimensionnement :
  - poteaux (flambement, acier) ;
  - poutres (flexion, effort tranchant, hauteur minimale de 25 cm) ;
  - semelles isolées et filantes ;
  - dalles (épaisseur) ;
  - longrines et chaînages.
- Validation et verrouillage des calculs par un ingénieur ou un admin. Le DQE est **bloqué** tant qu'un élément n'est pas validé.
- **DQE par lots (00 à 15)**, avec postes complémentaires (saisie libre, ratio, ou repris de la bibliothèque) et finances (déboursé sec, marge, TVA, TTC), sans taux supposé.
- Exports :
  - DQE en PDF professionnel et en Excel ;
  - plan de fondation en DXF et PDF ;
  - fiche d'approvisionnement en Excel.
- **Bibliothèque d'ouvrages** du cabinet et **import d'un DQE Excel** (aperçu, puis confirmation tout ou rien).
- Variantes « et si ? » recalculées par le moteur, sans rien enregistrer.
- Contrôles de plausibilité et analyse de cohérence déterministe.
- Tableaux de bord : cabinet, projet, pilotage produit.
- IA (Gemini), avec garde-fous :
  - structuration d'une description en texte libre ;
  - explication d'un calcul ;
  - suggestion de poste ;
  - lecture d'une image de plan.

## Les 5 points qui comptent le plus pour la réunion

1. **Plans de clients publics sur GitHub** : 153 fichiers de `media/` sont suivis dans le dépôt public, dont des plans qui portent le nom d'un client (A-22). La branche `dev`, elle, est identique au code audité (580 tests OK).
2. **L'acier des poteaux, poutres, dalles et longrines est estimé par ratio** quand le moteur ne fournit pas de poids d'acier. Les lignes sont marquées « estimé ». C'est la limite métier la plus visible du DQE (A-03).
3. **Plusieurs règles métier attendent le technicien** :
  - le contenu du G forfaitaire de 5 kN/m² ;
  - le sol à 180 kN/m² par défaut ;
  - le coefficient de maçonnerie de 0,80 ;
  - les ratios d'acier ;
  - les coefficients cachés de son propre DQE (1,02, 1,03, 1,48).
4. **Pas de test frontend ni d'intégration continue.** La non-régression de l'interface repose sur des vérifications manuelles ou des scripts Playwright hors dépôt.
5. **Fonctions codées mais non raccordées** :
  - la méthode de Caquot (poutres continues) ;
  - la semelle « affinée » ;
  - les routes `recalculer`, `chainage_suggere`, `couches-charges` et le changement de mot de passe, absents de l'interface.

  Il faut décider : raccorder ou retirer.

## Décisions attendues de l'équipe ce soir

- Qui valide les règles BTP listées dans 07, et quand ?
- Faut-il raccorder Caquot (poutres continues) ou garder le calcul isostatique (prudent) ?
- Priorité suivante :
  - maçonnerie et enduit tirés du plan des murs ;
  - acier calculé au lieu du ratio ;
  - ou tests frontend et intégration continue.
- Faut-il retirer les fichiers clients de `media/` du dépôt public, voire rendre le dépôt privé (A-22) ?


---

# 2. Inventaire des fonctionnalités

## Statuts

| Statut | Signification |
|---|---|
| **FV** | Fonctionnelle vérifiée (tests pertinents ou exécution) |
| **IVI** | Implémentée, validation incomplète |
| **PI** | Partiellement implémentée |
| **BFI** | Backend disponible, intégration frontend incomplète |
| **CNR** | Code présent mais non raccordé au parcours |
| **ES** | Expérimentale ou simulée |
| **AC** | À clarifier |

Les fiches ci-dessous donnent pour chaque fonctionnalité :

- objectif ;
- parcours ;
- frontend ;
- backend ;
- données ;
- règles ;
- dépendances ;
- état ;
- preuves ;
- limites.

Formules : voir 04. Fichiers : voir l'annexe de 05.

---

## A. Comptes, cabinets et sécurité

### A1. Inscription d'un cabinet et connexion (JWT) — FV

| | |
|---|---|
| **Objectif** | Chaque bureau d'études a son espace isolé. |
| **Parcours** | Page d'accueil → Inscription (crée le cabinet et son admin) → Connexion → Tableau de bord. |
| **Frontend** | `LandingPage.jsx`, `RegisterPage.jsx`, `LoginPage.jsx`, `api/dqeService.js` (jetons dans `localStorage`, rafraîchissement automatique). |
| **Backend** | `api/auth/inscription/`, `api/auth/token/`, `api/auth/token/refresh/`, `api/auth/logout/` (liste noire du refresh), `api/auth/moi/`. Code dans `projets/auth_views.py`. |
| **Données** | `auth.User`, `Profil` (rôle, cabinet), `EntrepriseParametres` (le cabinet). |
| **Preuves** | `projets/test_auth.py`, `tests_projets/test_permission.py`, `test_securite_routes.py`, `test_matrice_securite.py`. |
| **Limites** | Jetons en `localStorage`, exposés en cas de XSS (voir 08, A-10). Le modèle `Entreprise` est déprécié mais conservé (table non supprimée, volontairement). |

### A2. Équipe : invitation, activation, désactivation, rôles — FV

| | |
|---|---|
| **Rôles** | `admin` (gérant), `ingenieur`, `technicien` (`Profil.Role`). |
| **Droits** | Valider ou déverrouiller un calcul : admin ou ingénieur (`PeutValiderElement`). Modifier la bibliothèque : admin ou ingénieur. Paramètres du cabinet et équipe : admin. |
| **Frontend** | `TeamManagementView.jsx` (visible par l'admin), `ActivateAccountPage.jsx`. |
| **Backend** | `auth/inviter/`, `auth/activer/`, `auth/membres/`, `auth/membres/<id>/desactiver/`. |

### A3. Mot de passe oublié et réinitialisation — FV ; changement de mot de passe — BFI

- `auth/mot-de-passe-oublie/` et `auth/reinitialiser-mot-de-passe/` sont raccordés (`ForgotPasswordPage.jsx`, `ResetPasswordConfirmPage.jsx`).
- `auth/changer-mot-de-passe/` existe, et `dqeService.changerMotDePasse` aussi, mais **aucun écran ne l'appelle** [VÉRIFIÉ par recherche].
- E-mail : SMTP si configuré, sinon console (`backend/settings.py`).

### A4. Cloisonnement multi-cabinet — FV

- Toutes les listes passent par `FiltreCabinetMixin` (`projets/views.py`).
- Un objet d'un autre cabinet renvoie 404, jamais une fuite.
- Tests d'isolation dans chaque module récent, par exemple `test_lots_bibliotheque.py::test_isolation_entre_cabinets`.

---

## B. Projets et paramétrage

### B1. Mes projets (liste, création, ouverture, suppression) — FV

- `MesProjetsView.jsx` ; API `projets/` (CRUD).
- Statut du projet calculé par `parametres_projet.statut_projet`.
- `Projet.entreprise` peut être nul (projets antérieurs au multi-cabinet). La commande `rattacher_projets_orphelins` les rattache sur décision explicite.

### B2. Paramètres du projet (étape 1) — FV

| | |
|---|---|
| **Saisie** | Niveaux, hauteur d'étage, usage (donne Q), G forfaitaire ou couches de charges, contrainte du sol, portées et travées, méthode des semelles, poids propre de l'ossature, type de toiture (dalle ou charpente), poids des murs, part des baies, murs du RDC sur semelles. |
| **Frontend** | `Step1_Parametres.jsx` (711 lignes, le plus gros composant), `parametres/HypothesesCharges.jsx`. |
| **Backend** | `ProjetSerializer` (validations de bornes) ; `parametres_projet.parametres_structure()` lève `ParametresIncomplets` avec la liste des champs manquants : **aucune valeur cachée**. |
| **Règles** | Bornes : portée de 1 à 15 m, 20 niveaux au plus (`constantes.py`), poids des murs ≤ 10 kN/m², baies ≤ 90 %. |
| **Preuves** | `test_api.py`, `test_hypotheses_dqe.py`, `test_decisions_technicien.py`, `test_murs_et_portees.py`. |

### B3. Génération de la trame régulière — FV

- Le bouton « Générer » appelle `projets/<id>/generer_trame/`, qui appelle `trame_service.creer_elements_trame()`.
- `trame_service.creer_elements_trame()` s'appuie sur `moteur_calcul/formules/trame.py`.
- Elle crée les poteaux, poutres (avec clé de tronçon), semelles, longrines et chaînages, déjà calculés (statut « proposé »).
- **Régénérer la trame annule les validations** des éléments de trame. C'est un comportement assumé, à connaître.

### B4. Import de plan IFC — FV

- `importer_plan` avec un `.ifc` : aperçu, puis confirmation.
- `moteur_calcul/import_ifc/lecture_ifc.py` lit les poteaux et en déduit la trame (`detecter_parametres_trame`).
- Les poteaux dont la portée est hors domaine (< 1 m ou > 15 m) sont **listés, jamais ignorés en silence**.
- Preuves : `test_ifc.py`, `test_import_plan_api.py`.

### B5. Import de plan DXF (AutoCAD, ArchiCAD) — FV

- `moteur_calcul/import_dxf/lecture_dxf.py` :
  - unités lues dans `$INSUNITS`, sinon refus ;
  - blocs poteau et mur reconnus par nom ou calque ;
  - plans côte à côte regroupés : l'utilisateur choisit (`ApercuDXF.jsx`) ;
  - doublons fusionnés ;
  - murs associés aux poutres (écart ≤ 0,25 m, recouvrement ≥ 50 %).
- Refus explicite des formats `.pln`, `.pdf` et `.dwg`, avec un conseil d'export.
- Preuves : `test_import_dxf.py`, `test_phase_c_dxf.py`. Cas réel : duplex R+1 (14/10).
- **Limites** :
  - dalles non lues dans le DXF ;
  - poteaux à portée hors domaine non calculés (6 dans le cas réel) ;
  - le journal note « Import IFC confirmé » même pour un DXF (`EvenementProduit.Type.IMPORT_IFC`, `projets/models.py:628`).

### B6. Lecture d'une image de plan par IA (Vision) — ES / IVI

Voir 06. Affichage d'**aperçu seulement** : aucun élément n'est créé à partir de l'image (commentaire et code de `Step1_Parametres.jsx`, environ ligne 134).

### B7. Description en texte libre structurée par IA — IVI

Voir 06. Les valeurs proposées ne s'appliquent qu'au clic sur « Appliquer ».

**Point d'attention** : si Ly est vide, elle reçoit la portée X (`Step1_Parametres.jsx`, fonction `champsNlp`). C'est une hypothèse de symétrie qui n'est pas signalée (A-04).

---

## C. Éléments, calcul et validation

### C1. Calcul d'un élément — FV

- `elements/<id>/calculer/` appelle `services/calculations.calculer_element()`.
- Cette fonction choisit la formule selon le type : poteau, poutre, longrine, semelle, semelle filante, dalle, chaînage (04).
- Résultat stocké dans `ElementStructurel.resultat_calcul`, avec étapes, hypothèses et alertes.

### C2. Plan des murs (RDC et étages) — FV

- `murs/PlanMurs.jsx` dans `Step2_Calculs.jsx`.
- L'utilisateur désigne les tronçons un par un, pour le RDC et pour les étages. Bouton « Ajouter les façades ».
- Champs `Projet.murs_rdc` et `murs_etages` (clés « x;y|x;y » au cm).
- Si une clé ne correspond à aucune poutre calculée, un message l'explique (`trame_service.murs_orphelins`).
- **Limite** : un seul plan de murs pour tous les étages.

### C3. Dalles (étape « Dalles ») — FV

- `StepDalles.jsx`.
- Épaisseur pré-dimensionnée selon la portée (`dimensionnement_dalles.predimensionner_dalle`).
- Le DQE déduit l'emprise des poutres validées (`dqe_calculator.deduction_poutres_dalle`). Si Lx ou Ly manque, une hypothèse affichée l'indique : « volume surestimé ».

### C4. Validation et verrouillage — FV

- `elements/<id>/valider/` et `deverrouiller/` (admin ou ingénieur).
- `ListeElements.jsx`, `Step3_ValidationLock.jsx`, `BlocCoherence.jsx`.
- **Le DQE refuse de se générer** tant qu'un élément n'est pas validé : la liste des repères en attente est renvoyée (`views._dqe_ou_erreur`).

### C5. Analyse de cohérence (déterministe) et explication par IA facultative — FV (règles) / IVI (texte IA)

- `projets/<id>/analyse-coherence/` et `elements/<id>/expliquer-coherence/`.
- Signaux Python (`services/assistant_ia/coherence.py`) :
  - `PRESSION_SOL_DEPASSEE` ;
  - `HYPOTHESE_SOL_NON_CONFIRMEE` ;
  - `FRETTAGE_ACIER_DEPASSE` ;
  - `MINIMUM_NON_FRAGILITE_APPLIQUE`, etc.
- L'IA ne fait que **rédiger** l'explication (06).

### C6. Contrôles de plausibilité — FV

- `moteur_calcul/plausibilite.py`. Exemples :
  - sol > 300 kN/m² ;
  - poutre > 8 m ;
  - chevauchement des semelles calculé sur les positions réelles ;
  - valeurs hors plage.
- Exposés par `ProjetSerializer` (`controler_projet`).

### C7. Variantes « et si ? » — FV (trame régulière) / PI (plans importés)

- `projets/<id>/variantes/` (5 au plus), `VariantesPanel.jsx`.
- Recalcul complet dans une transaction **annulée** : rien n'est enregistré.
- 14 paramètres variables (`variantes.CHAMPS_VARIABLES`).
- **Non disponible pour un plan importé** (limite documentée en tête de `variantes.py`).

---

## D. Chiffrage

### D1. Génération du DQE — FV

- `projets/<id>/generer-dqe/` (GET ou POST), `Step4_DQEExport.jsx`.
- `dqe_calculator.calculer_projet_dqe()` : béton, coffrage et acier par élément validé, postes complémentaires, regroupement par lots, montant en lettres, finances.
- **Prix** : barème du cabinet (`EntrepriseParametres.prix_unitaires`).
  - Un prix manquant **bloque** avec un message (`DQEIncomplet`).
  - Chaque prix porte sa source et sa date (`prix_unitaires_meta`).
- **Type de donnée sur chaque ligne** : `calcul_moteur` (calculé), `ratio_reference` (estimé) ou `saisie` (saisi) — `TYPE_DONNEE`, `dqe_calculator.py:155`.
- **Finances** (`_finances`) : vente HT, ou déboursé sec + marge, puis TVA et TTC. Un taux absent n'est **jamais supposé** : le montant reste vide, avec un message.
- **Limite majeure** : acier par ratio pour les poteaux, poutres, longrines et dalles (A-03). L'acier des chaînages est un ratio étiqueté « calculé » (A-02).
- Preuves : `test_dqe.py`, `test_hypotheses_dqe.py`, `test_calculation.py`.

### D2. Lots 00 à 15 — FV

- `PosteComplementaire.Lot`. Lots 09 à 15 ajoutés le 16/10 (migration 0027, additive) ; noms dans `dqe_exporters.LOT_NOMS`.
- Preuve : `test_lots_bibliotheque.py`.

### D3. Postes complémentaires (simple, ratio, bibliothèque) — FV

- `validation/PostesComplementaires.jsx` ; API `postes-complementaires/`.
- **Mode ratio** (`moteur_calcul/formules/postes_ratio.py`) : maçonnerie avec un coefficient de plein de 0,80 [À CONFIRMER BTP], enduit, chaînage, raidisseur, acrotère.
- **Mode bibliothèque** : désignation, unité, lot et prix **copiés** dans le projet, avec origine et date tracées jusqu'à la ligne du DQE.

### D4. Bibliothèque d'ouvrages du cabinet — FV

- `bibliotheque/BibliothequeOuvrages.jsx` ; API `ouvrages/`.
- Modèle `OuvrageType`, unique par (cabinet, lot, désignation, unité).
- Lecture pour tous les membres, écriture pour admin et ingénieur.

### D5. Import d'un DQE Excel dans la bibliothèque — FV

- `bibliotheque/ImportDQEExcel.jsx`.
- API `ouvrages/importer/` (aperçu, rien n'est écrit) et `ouvrages/importer/confirmer/` (tout ou rien).
- `services/import_bibliotheque.py` :
  - lot reconnu par mots-clés, un titre ambigu reste « à choisir » ;
  - prix en conflit à arbitrer ;
  - formules sans valeur enregistrée signalées.
- Preuve : `test_import_bibliotheque.py` (8 tests).
- Testé sur l'export Excel du logiciel (237 lignes) et sur un classeur multi-lots de test.
- **Pas encore testé sur un vrai DQE d'un autre bureau d'études.**

### D6. Exports — FV

| Export | Code | Preuve |
|---|---|---|
| DQE PDF (en-tête, cartouche, tableaux numérotés, récapitulatifs, pagination) | `services/pdf_dqe.py` | `test_pdf_dqe.py` |
| DQE Excel | `services/dqe_exporters.py` | `test_dqe.py` |
| Plan de fondation DXF et PDF | `services/plan_fondation.py`, `StepPlanFondation.jsx` | `test_plan_fondation.py` |
| Fiche d'approvisionnement Excel | `services/approvisionnement.py` | `test_approvisionnement.py` |

Limite : pas de mention de responsabilité (« pré-dimensionnement à faire vérifier ») dans le PDF du DQE [VÉRIFIÉ par recherche].

### D7. Fiche d'approvisionnement — FV

- `approvisionnement/FicheApprovisionnement.jsx` ; API `projets/<id>/approvisionnement/`.
- Calcule ciment, sable, gravier, acier et agglos avec leurs pertes, puis les sacs et voyages (seulement si la capacité du camion est saisie), et le coût (seulement si le prix est saisi).
- Valeurs de référence avec leur source :
  - dosages 0,35 T de ciment, 0,45 m³ de sable et 0,85 m³ de gravier par m³ de béton (DQE de l'ingénieur) ;
  - pertes de 3 % et 4 % ;
  - 12 agglos/m².
- Les valeurs de référence sont modifiables par le cabinet (`ParametresApprovisionnement.jsx`).

---

## E. Pilotage

### E1. Tableaux de bord — FV

- `dashboards/CabinetDashboard.jsx`, `ProjetDashboard.jsx`, `StaffDashboard.jsx` (réservé au staff).
- API `analytics/cabinet/`, `analytics/projets/<id>/`, `analytics/staff/`.
- Les montants proviennent des **instantanés réels** des DQE générés (`EvenementProduit`), jamais d'une reconstitution.
- Preuve : `test_analytics.py`.

### E2. Journal produit et journal IA — FV

- `EvenementProduit` (création, import, validation, DQE), `JournalAppelIA` (source, durée, succès).
- Preuve : `test_ai_journal.py`.

### E3. Paramètres du cabinet — FV

- `settingsentreprise.jsx` ; API `entreprise/` (lecture pour les membres, écriture pour l'admin).
- Contenu : barème des prix (avec source et date), nature des prix, taux de marge, taux de TVA (18 % proposé, jamais appliqué d'office), logo, paramètres d'approvisionnement.

### E4. Référentiel — FV

- API `referentiel/` : lots, usages, murs, matériaux et sources des valeurs de référence (`views.ReferentielView`).
- Utilisé par `hooks/useReferentiel.js`.

---

## F. Code présent mais non raccordé (CNR)

| Élément | Où | Constat |
|---|---|---|
| Méthode de Caquot (poutres continues) | `formules/methode_caquot.py`, `dimensionner_poutre_continue` | Testée (`test_methode_caquot.py`, 15 tests), mais **jamais appelée** par le parcours : les poutres sont calculées comme isostatiques. |
| Semelle « affinée » | `dimensionnement_semelles.dimensionner_semelle_affinee` | Jamais appelée hors de son module. |
| `projets/<id>/recalculer/`, `projets/<id>/chainage_suggere/` | `views.py` | Routes sans appel côté frontend. |
| `couches-charges/` (CRUD) | `CoucheChargeViewSet` | Aucun appel frontend direct. |
| Alias `assistant/structurer/`, `assistant/expliquer/`, `projets/<id>/generer_dqe/` | `api/urls.py` | Doublons historiques. |
| `getMoi`, `patchProjet`, `listerPostesComplementaires` | `dqeService.js` | Fonctions jamais appelées. |
| Constantes `COEFFICIENTS_DEGRESSION` (1 / 0,95 / 0,90 / 0,85), `RATIO_HAUTEUR_POUTRE_CONTINUE` | `constantes.py:139`, `:164` | Inutilisées. Elles **contredisent** les valeurs réellement appliquées (dégression 1 / 0,9 / 0,8 / 0,7) : risque de confusion. |

## G. Fonctionnalités absentes (vérifiées par recherche)

- **Main-d'œuvre et déboursés détaillés** : aucun calcul. Le modèle `PosteMainDoeuvre` a été supprimé (migration 0006). Le DQE applique des prix unitaires globaux.
- **Maçonnerie et enduit tirés du plan des murs** : non fait. Les murs servent à la descente de charges, pas encore aux quantités.
- **Ferraillage détaillé** des poteaux, poutres et dalles (nomenclature des barres) : non fait. Ratio.
- **Historique et versions du DQE** : seuls les instantanés analytiques existent, pas de comparaison de versions dans l'interface.
- **Tests frontend et intégration continue** : absents.


---

# 3. Cartographie de l'architecture technique

## Vue d'ensemble

```
Navigateur (React 18 + Vite)
  App.jsx  ── vues : landing / login / dashboard / projets / step1..step4 / bibliothèque / équipe / staff
  components/*  ──>  hooks/ (useProjetCourant, useReferentiel, useRessource)
                ──>  api/dqeService.js  (fetch + JWT Bearer, refresh automatique, messages d'erreur FR)
                         │  HTTPS JSON / multipart
                         ▼
Django 6 + DRF  (backend/urls.py → api/urls.py)
  Authentification : SimpleJWT (access 30 min, refresh 7 j, rotation + liste noire)
  Permissions      : projets/permissions.py (EstMembreEntreprise, EstAdminCabinet,
                     PeutValiderElement, PeutModifierBibliotheque, EstStaff)
  Vues             : projets/views.py (ViewSets + actions), auth_views.py, analytics_views.py
  Serializers      : projets/serializers.py (validation métier des entrées)
  Services         : projets/services/*  (orchestration : trame, calculs, DQE, exports, IA…)
                         │ appels Python purs (aucun accès base)
                         ▼
  Moteur           : moteur_calcul/  (formules BAEL, hypothèses, unités, validators,
                     plausibilité, import IFC / DXF)  ── indépendant de Django pour les formules
                         ▼
  Base de données  : SQLite en local, PostgreSQL via DATABASE_URL (dj-database-url, SSL requis par défaut)
  Fichiers         : media/ (imports IFC/DXF, logos)
  IA externe       : Google Gemini (HTTP direct, services/assistant_ia/client.py), si LLM_PROVIDER=gemini
```

**Séparation des responsabilités [VÉRIFIÉ]**

- Les formules sont dans `moteur_calcul/formules/` : fonctions pures, qui reçoivent des nombres et renvoient des dictionnaires.
- Les services (`projets/services/`) lisent les modèles, appellent le moteur et assemblent les résultats.
- Les vues ne font que router, autoriser et sérialiser.
- Le frontend ne calcule rien de métier. Il affiche ce que renvoie l'API, et `dqeService.js` ne fait que convertir les noms de champs.

## Modèles et relations (`projets/models.py`)

```
EntrepriseParametres (cabinet)  1──n  Profil ──1 auth.User   (rôle admin | ingenieur | technicien)
        │ 1
        ├──n Projet ──n ElementStructurel ──n CoucheCharge
        │        │            (poteau_associe, poteau_origine, poteau_destination : FK internes)
        │        ├──n PosteComplementaire ──0..1 OuvrageType   (SET_NULL : le poste garde sa copie)
        │        └──n EvenementProduit
        ├──n OuvrageType (bibliothèque)
        └── prix_unitaires (+ _meta), nature_prix, taux_marge_pct, taux_tva_pct,
            parametres_approvisionnement (JSON)
JournalAppelIA ──n auth.User
Entreprise : DÉPRÉCIÉ, plus aucune FK (table conservée en attendant un audit des données de production)
```

| Modèle | Champs clés |
|---|---|
| `Projet` | paramètres de structure (niveaux, hauteur, portées, travées, usage, G, sol, méthode des semelles, toiture, murs, baies), `parametres_import` (plan DXF retenu) |
| `ElementStructurel` | `type_element` (7 types), `statut` (proposé, modifié, validé), géométrie, `resultat_calcul`, `resultat_valide` (copie figée à la validation), `nombre_identiques` |
| `PosteComplementaire` | lot, mode (simple ou ratio), géométrie, quantité, prix, `prix_source`, `prix_date`, `ouvrage` |

## Flux réels

### 1. Trame régulière jusqu'au DQE

```
Step1_Parametres → dqeService.creerProjet / mettreAJour → PATCH /api/projets/<id>/
  (ProjetSerializer valide les bornes)
→ « Générer » → POST /api/projets/<id>/generer_trame/
  → parametres_projet.parametres_structure()  (ParametresIncomplets si manque → 400 listé)
  → trame_service.creer_elements_trame() → moteur_calcul.formules.trame (poteaux, poutres, semelles…)
  → ElementStructurel créés, resultat_calcul rempli, statut « proposé »
→ Step2_Calculs / PlanMurs (PATCH murs) / StepDalles (POST elements + calculer)
→ Validation : POST /api/elements/<id>/valider/ (ingénieur/admin) → resultat_valide figé
→ Step4 : POST /api/projets/<id>/generer-dqe/
  → _dqe_ou_erreur (tout validé ?) → dqe_calculator.calculer_projet_dqe(projet, barème)
  → JSON (lots, lignes typées, hypothèses, finances) ; ?export=pdf|excel → fichier
```

### 2. Import de plan

```
Dépôt .ifc/.dxf → POST importer_plan (multipart) → aperçu (rien de créé)
→ (DXF multi-plans) POST importer_plan {plan} → aperçu du plan choisi
→ confirmation → éléments créés aux positions réelles (generer_poteau_depuis_position_reelle…)
```

### 3. Assistants IA

```
Composant → POST /api/assistant/... → _AssistantBase (throttle) → services/assistant_ia
→ client Gemini (ou Mock si LLM_PROVIDER=mock) → parser + schemas (validation stricte)
→ JournalAppelIA → réponse avec "source" (GEMINI / MOCK / LOCAL / FALLBACK_LOCAL)
```

## Configuration et déploiement

| Point | Constat |
|---|---|
| `backend/settings.py` | `DEBUG` vaut `False` par défaut ; `SECRET_KEY` est obligatoire hors `DEBUG` ; `ALLOWED_HOSTS`, CORS et CSRF viennent de l'environnement ; whitenoise ; e-mail SMTP ou console. |
| Production | `Procfile` (gunicorn), `RAILWAY_DEPLOYMENT.md`, `frontend/Dockerfile` et `frontend/Caddyfile`. |
| Variables IA | `LLM_PROVIDER`, `LLM_API_KEY`, `LLM_MODEL` (par défaut « gemini-3.5-flash », nom à vérifier côté fournisseur), `LLM_TIMEOUT_SECONDS`. |
| Dépendances Python (`requirements.txt`) | Django 6.0.7, DRF 3.17.1, SimpleJWT 5.5.1, ifcopenshell 0.8.5, ezdxf 1.4.4, openpyxl 3.1.5, reportlab 4.2.2, shapely, numpy, pillow, psycopg 3. |
| Dépendances frontend | react, react-dom et lucide-react seulement. Aucune bibliothèque de graphiques : les graphiques sont faits maison (`components/charts/`). |

## Duplications et risques d'architecture

- **Routes en double** :
  - `api/token/` (dans `backend/urls.py`) et `api/auth/token/` ;
  - `api/me/` et `api/auth/moi/` ;
  - `generer_dqe` et `generer-dqe` ;
  - alias `assistant/structurer` et `assistant/expliquer`.

  Le frontend utilise `auth/token`, `me/`, `auth/moi/` et `generer-dqe`.
- **Deux tables de dégression** dans `constantes.py`, dont une inutilisée et contradictoire (voir 02, section F).
- **`views.py` fait 1 524 lignes.** Il mélange vues CRUD, imports de plans, exports et assistants. Un découpage en modules (`views/plans.py`, `views/exports.py`…) faciliterait le travail à plusieurs.
- **Aucune logique métier dupliquée côté frontend** [VÉRIFIÉ par lecture des composants principaux]. Seule exception : la symétrie Ly = Lx appliquée lors de la reprise des données de l'IA (A-04).


---

# 4. Documentation du moteur de calcul

> Partie prioritaire : le chef de projet en est le responsable principal.
> Référentiel : **BAEL 91 mod. 99** (`constantes.NORME_PAR_DEFAUT`). Eurocode 2 est cité mais **non implémenté**.

## 4.1 Organisation

| Module | Rôle | Appelé par |
|---|---|---|
| `moteur_calcul/constantes.py` | toutes les constantes, chacune avec sa source en commentaire | tout le moteur |
| `moteur_calcul/hypotheses.py` | `HypothesesCalcul` : G, Q, poids propre, sol, toiture, murs, avec l'**origine** de chaque valeur (`saisie`, `forfait`, `defaut`, `valide_technicien`) et les messages d'hypothèse ou d'alerte | trame, calculations |
| `moteur_calcul/unites.py` | conversions explicites (kN↔MN, cm↔m, MPa↔kN/cm²) | formules |
| `moteur_calcul/validators.py` | `EntreeInvalide`, bornes des entrées (portée de poutre comprise entre 0,20 et 15 m…) | formules, serializers |
| `formules/descente_charges.py` | surfaces d'influence, G, Q, dégression, ELU et ELS, descente complète | calculations, trame |
| `formules/trame.py` | génération de la trame (grille ou positions réelles), nœuds, murs par tronçon, poutres adjacentes | `services/trame_service.py` |
| `formules/dimensionnement_poteaux.py` | élancement, flambement, acier, pré-dimension rapide | trame, calculations |
| `formules/dimensionnement_poutres.py` | hauteur retenue, flexion (pivots), effort tranchant, poutre continue | trame, calculations |
| `formules/dimensionnement_semelles.py` | semelle isolée (ELU ou ELS), filante, « affinée » (non raccordée) | trame, calculations |
| `formules/dimensionnement_dalles.py` | épaisseur selon la portée | calculations, plan_fondation |
| `formules/methode_caquot.py` | moments de Caquot (minoré) | **uniquement** `dimensionner_poutre_continue` : **non raccordé** |
| `formules/postes_ratio.py` | maçonnerie, enduit, chaînage, raidisseur, acrotère | dqe_calculator, calculations |
| `formules/complements_plan_coffrage.py` | joints de dilatation, dallage | plan_fondation |
| `tables_acier.py` | sections et masses des barres HA | semelles |
| `plausibilite.py` | contrôles de plausibilité des paramètres et des résultats | serializers, analytics |
| `import_ifc/lecture_ifc.py`, `import_dxf/lecture_dxf.py` | lecture des plans | `views.importer_plan` |

**Points d'entrée côté Django**

- `projets/services/trame_service.creer_elements_trame(projet, prm)` : génère et calcule toute la trame.
- `projets/services/calculations.calculer_element(element)` : calcule un élément isolé (bouton « Calculer »).
- `projets/services/dqe_calculator.calculer_projet_dqe(projet, prix)` : produit les quantités et le chiffrage à partir des résultats **validés**.

## 4.2 Données d'entrée

Les paramètres viennent de `parametres_projet.parametres_structure`.

| Donnée | Unité | Obligatoire | Si absente |
|---|---|---|---|
| Nombre de niveaux, hauteur d'étage | –, m | oui | `ParametresIncomplets` → 400 avec la liste des champs |
| Portées X/Y et nombre de travées (trame) | m | oui (trame) | idem |
| Usage du bâtiment, qui donne Q | kN/m² | oui | idem |
| Charge permanente G | kN/m² | non | **forfait de 5 kN/m²** (contenu validé par le technicien), signalé |
| Contrainte admissible du sol | kN/m² | non | **180 kN/m²**, signalé « HYPOTHÈSE » (`hypotheses.py:243`) [À CONFIRMER BTP pour chaque projet] |
| fc28 | MPa | non | 25 MPa (`RESISTANCE_BETON_DEFAUT`) |
| fe | MPa | – | 500 |
| Poids des murs | kN/m² de mur | non | **aucune valeur** : murs non comptés + ALERTE (3,3 kN/m² proposé par un bouton) |
| Part des baies | % | non | 0 % (aucune déduction, prudent) |
| Type de toiture | – | non | dalle |

## 4.3 Formules réellement implémentées [CODE + tests]

### Descente de charges (`descente_charges.py`, `trame._calcul_noeud`)

- **Surface d'influence** d'un poteau :
  `S = (Lg/2 + Ld/2) × (Lav/2 + Lar/2)` [m²]
- **ELU** : `Nu = 1,35 G + 1,5 Q` ; **ELS** : `Ns = G + Q` [kN]
- **Dégression de Q** (habitation et bureaux) : coefficients par étage 1 / 0,9 / 0,8 / 0,7, validés par le technicien.
  - Au-delà, 0,6 avec un plancher à 0,5 : **non validé** (`constantes.py:133-134`).
- **Poids propre** des poteaux et poutres ajouté à G par défaut : 25 kN/m³.
- **Toiture en charpente** : `G = (n − 1) × G plancher + 2,5 × S + n × poids propres`, avec Q toiture = 1,5 kN/m² (ingénieur, 10/10).
- **Murs** :
  - `q_mur = p × (h_étage − h_poutre) × (1 − baies/100)` [kN/m]
  - Le poteau du RDC reçoit `(n − 1) × Σ (l/2) q_mur` sur les tronçons d'étage qui portent un mur.
  - La semelle reçoit en plus `Σ (l/2) q_mur` sur les tronçons du RDC (murs posés sur les longrines, ingénieur 12/10).

**Exemple de référence (test)** — `test_murs_et_portees.py` :

- Données : trame 4 × 4 m, R+1, h = 3 m, p = 3,3 kN/m², sans poids propre.
- Mur d'étage : `q_mur = 3,3 × (3 − 0,5) = 8,25 kN/m`.
- Poteau central : Nu = 332,55 kN, contre 288 kN sans murs.
- Semelle : 377,1 kN.

### Poteaux (`dimensionnement_poteaux.py`)

- **Pré-dimension** : `B_th = Nu / (0,7 × fc28) × 1,3` [cm²]. Le coefficient de sécurité 1,3 est le milieu de la fourchette 1,2 à 1,5 [À CONFIRMER BTP].
  - Côté minimal : 20 cm, arrondi au multiple de 5 cm supérieur.
- **Élancement** : `λ = lf √12 / a`, avec lf = l0 (articulé, hypothèse).
- **Coefficient de flambement** :
  - λ ≤ 50 : `α = 0,85 / (1 + 0,2 (λ/35)²)` ;
  - 50 < λ ≤ 70 : `α = 0,6 (50/λ)²` ;
  - λ > 70 : **refus explicite** (`NotImplementedError`).
- **Acier** : `A_th = [Nu/α − Br fc28 / (0,9 γb)] / (fe/γs)`, avec `Br = (a − 2)(b − 2)` cm².
  - `A_min = max(4 cm²/m de périmètre ; 0,2 % B)` ; `A_max = 5 % B`.
- **Sortie** : section (cm²) et barres. **Pas de poids d'acier total** : le DQE applique alors le ratio (A-03).

### Poutres (`dimensionnement_poutres.py`)

- **Hauteur** : `h = max(L/8 ; 25 cm)`, d'après la règle de l'ingénieur du 12/10 pour une poutre qui reprend un plancher ou un mur. Le minimum de 25 cm est **étendu à toutes les poutres** [À CONFIRMER BTP].
  - Largeur par défaut : 20 cm.
- **Moment** : `M = q L² / 8`. **Toutes les poutres sont calculées comme isostatiques** ; Caquot existe mais n'est pas utilisé.
- **Flexion** : `μ = Mu / (b d² fbu)`, avec d = 0,9 h. Comparé à μ_lim (Pivot B, γ = Mu/Mser **supposé 1,45** si non fourni) ; A_s minimale de non-fragilité.
- **Effort tranchant** : `Vu = pu L / 2` ; `τu = Vu / (b d) ≤ min(0,2 fc28 / γb ; 5 MPa)`.
- **Portées traitées** : de 0,20 m à 15 m. Une portée ≤ 0,20 m désigne des poteaux superposés, signalés.
- **Sortie** : `poids_acier_longitudinal_theorique_kg`. Le DQE ne le lit pas : il lit `poids_acier_total_kg`, donc il applique le ratio (A-03).

### Semelles isolées (`dimensionnement_semelles.dimensionner_semelle`)

1. `A_th = √(N / σ_sol)`, avec N = Nu en méthode **ELU (par défaut, validée par le technicien le 07/10)** ou Ns en méthode ELS (choix du projet).
2. A est arrondi au multiple de 5 cm supérieur.
3. `d ≥ (A − b)/4` (méthode des bielles) ; `h = arrondi5(d + 5 cm)` avec h ≥ 20 cm.
4. Poids propre facultatif : `A² h × 25` (× 1,35 en ELU). On itère tant que la pression dépasse σ_sol.
5. Acier : `As = Nu (A − b) / (8 d fsu)` par direction. Barres HA 12 à 16, espacement ≤ 20 cm. Le **poids d'acier est calculé**.

**Exemple vérifié à la main** (cas d'usage du duplex, 14/10) — semelle S25 :

- Nu = 526,2 kN ; 598,0 kN avec les murs du RDC.
- Côté obtenu : 1,95 m.

### Semelles filantes, longrines, chaînages, dalles

| Élément | Calcul |
|---|---|
| **Semelle filante** | largeur ≥ 40 cm, ≤ 300 cm ; poids d'acier = section × longueur × 7 850 kg/m³ |
| **Longrine** | même physique qu'une poutre (`dimensionner_poutre`) |
| **Chaînage** | **pas de calcul de résistance** : section forfaitaire de 15 × 20 cm et acier de **90 kg/m³** (ratio), voir A-02 |
| **Dalle** | épaisseur = portée/25 à 30 (un sens) ou /35 à 40 (deux sens), entre 12 et 16 cm courants |

### Postes à ratio (`postes_ratio.py`)

- **Maçonnerie** : surface × **0,80** (20 % d'ouvertures supposées) [À CONFIRMER BTP], ou surface nette saisie.
- **Enduit, raidisseur, acrotère** : acier de 90 à 150 kg/m³ et coffrage de 10 à 15 m²/m³ (ratios de référence).

## 4.4 Du résultat validé au DQE (`dqe_calculator.py`)

1. Seuls les éléments **validés** sont chiffrés (`resultat_valide` figé). Un seul élément non validé bloque tout le DQE.
2. Géométrie de chaque élément (`_geometrie_element`) : volume de béton, coffrage et poids d'acier. Une dimension manquante donne `DIMENSION_MANQUANTE`, et non une valeur supposée.
3. Les **dalles** sont diminuées de l'emprise des poutres validées. Faute de dimension, une hypothèse affichée l'indique : « volume surestimé ».
4. **Acier** :
   - si le moteur fournit `poids_acier_total_kg` > 0, la ligne est « calculé » ;
   - sinon, ratio au milieu de la fourchette, ligne « estimé » : poteau 125, poutre et longrine 150, semelle 50, dalle 85, chaînage 90 kg/m³.
5. **Prix** : barème du cabinet. Une clé manquante bloque le DQE (problème listé, aucun prix inventé).
6. **Calculs en `Decimal`**, arrondi au FCFA près (`ROUND_HALF_UP`) en fin de chaîne seulement (`_arrondi_fcfa`), jamais pendant les étapes intermédiaires.
7. **Finances** : vente HT, ou déboursé sec × (1 + marge), puis TVA ; un taux absent laisse un montant vide, avec un message.

## 4.5 Unités et arrondis

| Domaine | Unités |
|---|---|
| Moteur | kN, kN/m, kN/m², m, cm, MPa |
| DQE | m³, m², kg, FCFA |

- Conversions dans `unites.py`, jamais en ligne dans le code.
- Arrondis constructifs au multiple de 5 cm **supérieur** (`arrondi_superieur`), jamais inférieur.
- Les quantités du DQE gardent toute leur précision jusqu'au montant.

## 4.6 Erreurs possibles et comportement

| Situation | Comportement |
|---|---|
| Paramètre de projet manquant | 400 avec la liste des champs (`ParametresIncomplets`) |
| Entrée hors bornes | `EntreeInvalide` → message en français |
| λ > 70 | refus, « vérification détaillée par l'ingénieur nécessaire » |
| Portée hors domaine à l'import | élément non créé et **listé** |
| Prix manquant | DQE bloqué, liste des clés |
| Élément non validé | DQE bloqué, liste des repères |

## 4.7 Où le moteur affiche un résultat plausible sans toutes les données

| Cas | Signalé ? | Commentaire |
|---|---|---|
| Sol non saisi : 180 kN/m² | oui, HYPOTHÈSE dans chaque résultat | Le chiffre reste présent : il faut que le lecteur le remarque. |
| G non saisi : forfait de 5 kN/m² | oui | Contenu validé par le technicien. |
| fc28 non saisi : 25 MPa | oui (hypothèse) | Valeur courante. |
| Acier par ratio (poteaux, poutres, dalles, longrines) | oui, « estimé » | Écart possible important avec la réalité. |
| **Acier des chaînages** | **non** : étiqueté « calculé » | Ratio de 90 kg/m³ présenté comme un calcul (A-02). |
| Maçonnerie × 0,80 | oui (hypothèse du poste) | À valider. |
| Poutre continue calculée en isostatique | non explicité | Méthode prudente sur le moment en travée, mais les moments sur appuis ne sont pas couverts. À documenter dans les hypothèses (A-05). |

## 4.8 Tests du moteur

**`moteur_calcul/tests_moteur_calcul/`** (115 tests) :

| Fichier | Tests |
|---|---|
| `test_trame` | 23 |
| `test_dimensionnement` | 16 |
| `test_methode_caquot` | 15 |
| `test_descente_charges` | 14 |
| `test_projets_reference` | 14 |
| `test_ifc` | 14 |
| `test_complements_plan_coffrage` | 11 |
| `test_postes_ratio` | 8 |

**`projets/tests_projets/`**, pour les tests métier de bout en bout :

- `test_decisions_technicien` (23)
- `test_murs_et_portees`
- `test_hypotheses_dqe` (17)
- `test_calculation`
- `test_dqe`

**Cas de référence chiffrés présents dans les tests** :

- trame 4 × 4 m (murs) ;
- R+1 NEW ERA (`test_projets_reference.py`) ;
- prix de test explicitement nommés « TEST ».


---

# 5. Audit du backend Django et du frontend React

## 5.1 Endpoints (liste obtenue par résolution des routes Django, pas par lecture)

| Groupe | Endpoint | Méthode | Rôle | Appelé par le frontend |
|---|---|---|---|---|
| Auth | `auth/token/`, `auth/token/refresh/`, `auth/logout/` | POST | JWT | oui |
| Auth | `auth/moi/`, `me/` | GET | profil | oui (les deux) |
| Auth | `auth/inscription/`, `auth/inviter/`, `auth/activer/` | POST | comptes | oui |
| Auth | `auth/membres/`, `auth/membres/<id>/desactiver/` | GET, POST | équipe | oui |
| Auth | `auth/mot-de-passe-oublie/`, `auth/reinitialiser-mot-de-passe/` | POST | mot de passe | oui |
| Auth | `auth/changer-mot-de-passe/` | POST | mot de passe | **non (aucun écran)** |
| Auth | `token/`, `token/refresh/`, `token/verify/` (dans `backend/urls.py`) | POST | doublons JWT | non |
| Projets | `projets/` et `projets/<id>/` | CRUD | projets | oui |
| Projets | `projets/<id>/generer_trame/` | POST | trame | oui |
| Projets | `projets/<id>/importer_plan/` | POST multipart ou JSON `{plan}` | IFC, DXF | oui |
| Projets | `projets/<id>/analyser_plan_image/` | POST multipart | Vision IA | oui |
| Projets | `projets/<id>/generer-dqe/` (`?export=pdf\|excel`) | GET, POST | DQE | oui |
| Projets | `projets/<id>/generer_dqe/` | GET, POST | alias | non |
| Projets | `projets/<id>/approvisionnement/` (`?export=excel`) | GET | fiche | oui |
| Projets | `projets/<id>/plan_fondation/` (`?export=pdf\|dxf`), `valider_plan_fondation/` | GET, POST | plan | oui |
| Projets | `projets/<id>/variantes/` | POST | variantes | oui |
| Projets | `projets/<id>/analyse-coherence/` | GET | cohérence | oui |
| Projets | `projets/<id>/recalculer/` | POST | recalcul global | **non** |
| Projets | `projets/<id>/chainage_suggere/` | GET | suggestion de chaînage | **non** |
| Éléments | `elements/` CRUD, puis `calculer/`, `valider/`, `deverrouiller/`, `expliquer-coherence/` | | | oui |
| Charges | `couches-charges/` CRUD | | couches de G par élément | **non (pas d'appel direct)** |
| Postes | `postes-complementaires/` CRUD | | postes | oui |
| Bibliothèque | `ouvrages/` CRUD, `ouvrages/importer/`, `ouvrages/importer/confirmer/` | | bibliothèque | oui |
| Cabinet | `entreprise/` | GET, PUT | paramètres | oui |
| Référentiel | `referentiel/` | GET | lots, usages, références | oui |
| Analytics | `analytics/cabinet/`, `analytics/projets/<id>/`, `analytics/staff/` | GET | tableaux de bord | oui |
| IA | `assistant/structurer-projet/`, `assistant/expliquer-element/`, `assistant/suggerer-poste/` | POST | assistants | oui |
| IA | `assistant/structurer/`, `assistant/expliquer/` | POST | alias | non |

## 5.2 Contrats de données

- **Conversion des noms de champs** : React utilise le camelCase (`porteeX`) et l'API le snake_case (`portee_x`). La conversion est faite **à un seul endroit**, `api/dqeService.js` (par exemple `ouvrageVersApi`, et la correspondance des champs de murs).
  - Toute modification d'un champ côté Django doit être répercutée dans ce fichier.
  - C'est le point de rupture le plus probable entre les deux équipes.
- **Erreurs** :
  - le backend renvoie `{"erreur": ...}`, `{"detail": ...}` ou des erreurs de champ DRF ;
  - `dqeService.messageErreur()` les transforme en message français, avec des textes par code HTTP (le 404 donne « Élément introuvable… ») ;
  - `err.data` conserve le détail (par exemple `lignes` de l'import Excel, `elements_en_attente` du DQE).
- **Aucun contrat typé partagé** (pas de schéma OpenAPI généré, pas de TypeScript). La cohérence repose sur les tests backend et sur des vérifications manuelles.

## 5.3 Validations

| Côté | Ce qui est validé |
|---|---|
| Backend, et lui seul (frontière de sécurité) | serializers (bornes physiques, lots, unités, clés de tronçon par regex `MOTIF_CLE_SEGMENT`, prix ≥ 0, doublons de bibliothèque), `moteur_calcul/validators.py`, `ParametresIncomplets` |
| Frontend (confort) | champs requis, nombres ≥ 0, boutons désactivés tant que le formulaire est incomplet |

## 5.4 Authentification et autorisation [VÉRIFIÉ par les tests]

- La permission par défaut est **fermée** : `EstMembreEntreprise`, c'est-à-dire un utilisateur authentifié ET rattaché à un cabinet (`DEFAULT_PERMISSION_CLASSES`). Les vues publiques (inscription, connexion, mot de passe oublié) déclarent `AllowAny` explicitement.
- Authentification : JWT, plus session (`SessionAuthentication`, utilisée par l'admin Django).
- Limites d'appels (throttling) des assistants IA, par minute : structurer 10, expliquer 20, suggérer un poste 15, vision 5, cohérence 10.
- `test_matrice_securite.py` et `test_securite_routes.py` parcourent les routes avec chaque rôle et vérifient 401, 403 et 404.

## 5.5 Traitements asynchrones

**Aucun** (pas de Celery ni de files de tâches). Les imports de plans, les PDF et les appels IA sont synchrones, avec un délai d'attente de 60 s par défaut pour l'IA.

Un gros IFC ou un gros DXF bloque la requête : limite de taille `TAILLE_MAX_PLAN_OCTETS` = 50 Mo pour les plans, 5 Mo pour les images et pour l'Excel.

## 5.6 Problèmes constatés

| Réf. | Problème | Gravité |
|---|---|---|
| A-07 | Les tests écrivent de vrais fichiers dans `media/imports_ifc/` (`MEDIA_ROOT` non isolé pendant les tests). Sur un poste de développeur, chaque exécution laisse des `.ifc` non suivis. | moyenne |
| A-08 | `README.md` à la racine décrit une session sur le plan de coffrage (« 267/267 tests »). Il ne présente ni le projet ni son installation. | moyenne |
| A-09 | `views.py` fait 1 524 lignes, `Step1_Parametres.jsx` 711 lignes : difficile à faire évoluer à plusieurs | faible |
| A-12 | Routes doublons et fonctions frontend jamais appelées (02, section F) | faible |
| A-13 | Événement « Import IFC confirmé » enregistré pour un DXF | faible |
| A-14 | Aucun test frontend, pas d'intégration continue : une régression d'interface n'est détectée qu'à la main | moyenne |
| A-15 | Le fichier `projets/migrations/0009_alter_elementstructurel_type_element .py` (avec une espace avant `.py`) existe à côté de la vraie migration 0009. Django l'ignore ici (suite de tests verte), mais c'est un doublon à supprimer **après vérification**. | faible |

## 5.7 Zones à ne pas modifier sans le responsable du moteur

- `projets/services/dqe_calculator.py` : quantités, ratios, arrondis, finances.
- `projets/services/trame_service.py` et `moteur_calcul/formules/trame.py` : génération et clés de tronçon (`cle_segment`), dont dépendent les murs enregistrés dans les projets.
- `moteur_calcul/constantes.py` : chaque valeur a une source. Ne pas changer une valeur sans décision tracée.
- Les migrations : lancer `makemigrations` uniquement depuis un dossier à jour de `dev`. Les migrations de suppression de données demandent une validation explicite.

## 5.8 Annexe technique : où trouver quoi

| Sujet | Fichiers et symboles |
|---|---|
| Routes | `api/urls.py`, `backend/urls.py` |
| Cloisonnement | `projets/views.py::FiltreCabinetMixin`, `projets/permissions.py::entreprise_de` |
| Trame | `views.ProjetViewSet.generer_trame` → `services/trame_service.creer_elements_trame` → `moteur_calcul/formules/trame.py` |
| Import de plans | `views.ProjetViewSet.importer_plan`, `_apercu_dxf` ; `moteur_calcul/import_ifc/lecture_ifc.py` ; `moteur_calcul/import_dxf/lecture_dxf.py` |
| Calcul d'un élément | `views.ElementStructurelViewSet.calculer` → `services/calculations.calculer_element` |
| Validation | `ElementStructurelViewSet.valider`, `deverrouiller` ; `permissions.PeutValiderElement` |
| DQE | `ProjetViewSet.generer_dqe`, `_dqe_ou_erreur`, `_exporter_dqe` ; `services/dqe_calculator.calculer_projet_dqe` ; `services/pdf_dqe.py` ; `services/dqe_exporters.py` |
| Approvisionnement | `ProjetViewSet.approvisionnement` ; `services/approvisionnement.calculer_fiche_approvisionnement` |
| Variantes | `ProjetViewSet.variantes` ; `services/variantes.calculer_variantes` |
| Plan de fondation | `services/plan_fondation.py` |
| Bibliothèque | `OuvrageTypeViewSet` (+ `importer`, `confirmer_import`) ; `services/import_bibliotheque.py` |
| IA | `services/assistant_ia/` (client, prompts, parser, schemas, explanations, coherence, coherence_explanations, postes, vision) |
| Analytics | `projets/analytics_views.py`, `services/analytics.py`, `services/evenements.py` |
| Commandes d'administration | `projets/management/commands/audit_donnees_production.py`, `rattacher_projets_orphelins.py` |
| Frontend : appels API | `frontend/src/api/dqeService.js` |
| Frontend : routage des vues | `frontend/src/App.jsx` (`activeView`), `components/Sidebar.jsx` |


---

# 6. Audit du module IA

## 6.1 Ce qui utilise réellement l'IA

| Fonction | Endpoint | Prompt (`services/assistant_ia/prompts.py`) | Sortie autorisée | Effet sur les données |
|---|---|---|---|---|
| Structurer une description de projet | `assistant/structurer-projet/` | `PROMPT_STRUCTURATION` | JSON : niveaux, usage, portée, hauteur, sol, configuration, données manquantes, avertissements | **aucun tant que l'utilisateur ne clique pas sur « Appliquer »** ; recopie ensuite dans le formulaire de l'étape 1 |
| Expliquer un calcul | `assistant/expliquer-element/` | `PROMPT_EXPLICATION` | texte | aucun (lecture de `resultat_calcul`) |
| Suggérer un poste complémentaire | `assistant/suggerer-poste/` | `PROMPT_SUGGESTION_POSTE` | désignation, unité (liste fermée), lot (liste fermée), niveau de confiance. **Ni quantité ni prix.** | pré-remplissage du formulaire de poste |
| Lire une image de plan | `projets/<id>/analyser_plan_image/` | `PROMPT_EXTRACTION_PLAN_2D` | repères et textes lus, dimensions extraites **par un analyseur Python local** | **aperçu seulement, aucun élément créé** |
| Expliquer les signaux de cohérence | `elements/<id>/expliquer-coherence/` | `PROMPT_COHERENCE` | 1 à 2 phrases | aucun (les signaux sont calculés en Python) |

## 6.2 Ce qui n'est PAS de l'IA (automatisation déterministe)

Tout le reste est du Python déterministe :

- le moteur de calcul, les contrôles de plausibilité et les signaux de cohérence (`coherence.py`) ;
- l'import IFC et DXF, l'import Excel de la bibliothèque ;
- la reconnaissance des lots par mots-clés (`import_bibliotheque.reconnaitre_lot`) ;
- les tableaux de bord.

## 6.3 Fournisseur et configuration

| Variable ou élément | Valeur |
|---|---|
| `LLM_PROVIDER` | `gemini`, ou `mock` (tests et démonstration). **Absente : erreur 503 « assistant non configuré »**, sans repli silencieux (`client.get_ai_client`). |
| `LLM_API_KEY` | obligatoire pour gemini |
| `LLM_MODEL` | par défaut « gemini-3.5-flash » ; **nom de modèle à vérifier** auprès du fournisseur |
| `LLM_TIMEOUT_SECONDS` | 60 par défaut |
| Appel | HTTP direct à `generativelanguage.googleapis.com/v1beta/models/<modèle>:generateContent` (clé dans l'en-tête `x-goog-api-key`) |

## 6.4 Garde-fous en place [VÉRIFIÉ par les tests]

**Validation stricte des réponses** (`schemas.py`) :

- types, bornes, listes fermées (unités, lots, niveaux de confiance) ;
- cohérence entre `configuration` et `nombre_niveaux` ;
- une réponse invalide est **rejetée**.

**Explications** (`explanations.py`, `coherence_explanations.py`) :

1. **Termes interdits** : « conforme », « validé », « sûr », « optimal », « respecte toutes les normes ». L'IA ne peut pas certifier.
2. **Contrôle des nombres** : tout nombre présent dans le texte de l'IA et absent des données fournies déclenche le rejet. L'explication est alors remplacée par la version locale (source `FALLBACK_LOCAL`).
3. Message permanent : « Cette analyse nécessite une vérification humaine par l'ingénieur structure ».

**Traçabilité** :

- chaque réponse porte une `source` : `GEMINI`, `MOCK`, `LOCAL` ou `FALLBACK_LOCAL`, affichée par l'interface ;
- chaque appel est journalisé dans `JournalAppelIA` (point d'entrée, source, durée, succès).

**Limites d'appels (throttling)** par assistant ; taille d'image limitée à 5 Mo (`PLAN_IMAGE_MAX_BYTES`), et image vérifiée par Pillow.

**Tests** :

| Fichier | Tests |
|---|---|
| `test_ai.py` | 51 |
| `test_ai_coherence.py` | 44 |
| `test_ai_coherence_api.py` | 16 |
| `test_ai_coherence_explanations.py` | 25 |
| `test_ai_journal.py` | 9 |
| `test_vision.py` | 31 |
| `test_vision_api.py` | 20 |
| **Total** | **196** |

## 6.5 Données simulées

- `MockAIClient` (`client.py`) produit des réponses déterministes, **seulement si `LLM_PROVIDER=mock`**. La source est alors marquée « MOCK ».
- `vision.orchestrer_ocr_local` renvoie toujours `source: "MOCK"`. C'est une fonction de test de l'enrichissement local, non exposée par une route [DÉDUIT par recherche des appels].
- Si Gemini échoue pendant l'analyse d'image, la réponse est **vide** (`annotations_lues: []`) avec le message « L'analyse automatique du plan n'est pas disponible ». **Aucune annotation n'est inventée.**

## 6.6 Risques et limites

| Risque | État |
|---|---|
| Hallucination de valeurs techniques | Limitée par le contrôle des nombres (explications) et par la validation des schémas (structuration). **Mais** une portée ou un sol proposé par l'IA, une fois appliqué par l'utilisateur, devient une **valeur saisie**, et rien ne rappelle ensuite qu'elle venait de l'IA (A-04b). |
| Symétrie implicite | Lors de la reprise, Ly reçoit la portée X si elle est vide (`Step1_Parametres.jsx`, `champsNlp`). Hypothèse non signalée (A-04). |
| Bornes incohérentes | L'IA accepte de 1 à 100 niveaux (`schemas.py`), le moteur 20 au plus (`NB_NIVEAUX_MAX`). Une valeur de 21 à 100 passe l'IA puis est refusée par le projet (A-11). |
| Confidentialité | Les descriptions, les résultats de calcul et les images de plans sont envoyés à Google (Gemini). Aucune mention de ce point dans l'interface (aucun texte d'avertissement trouvé dans `frontend/src`), pas d'option d'anonymisation. |
| Coût | Pas de plafond de coût, seulement les limites d'appels. Le journal permet de compter les appels. |
| Disponibilité | Délai d'attente de 60 s, appels synchrones. |
| Modèle | Nom par défaut non vérifié (« gemini-3.5-flash »). |
| Étiquette de source | Le panneau Vision affiche « Source : GEMINI » quand la réponse n'a pas de source (`Step1_Parametres.jsx:314`, `vision.source \|\| 'GEMINI'`). Étiquette par défaut trompeuse, à remplacer par « inconnue » (A-16). |

## 6.7 Règle d'interaction IA et moteur (proposition à valider en réunion)

1. L'IA **ne produit jamais** une quantité, une dimension, une charge, un coefficient ou un prix qui entre dans un calcul sans action explicite de l'utilisateur. C'est déjà le cas.
2. Une valeur reprise de l'IA doit garder son origine (« proposée par l'IA, acceptée par X le … »), comme `prix_source` pour les prix. **À construire** (origine par champ de projet).
3. Les explications ne citent que les nombres fournis par le moteur. C'est déjà le cas.
4. Tout nouvel assistant passe par `schemas.py` (validation stricte) et `JournalAppelIA`.

## 6.8 Pistes pour le développeur IA (par ordre d'utilité)

1. Origine « IA » conservée sur les champs du projet (point 2 ci-dessus).
2. Aligner les bornes de l'IA sur le moteur (`NB_NIVEAUX_MAX`, portées de 1 à 15 m).
3. Vérifier le nom du modèle et mesurer la latence et le coût réels sur 20 appels.
4. Vision : mesurer la qualité réelle sur 5 plans du cabinet avant d'aller plus loin (aujourd'hui en aperçu seulement).
5. Message de confidentialité avant le premier envoi d'un plan ou d'une description.


---

# 7. Vérifications métier destinées au technicien BTP

> Chaque ligne indique ce que fait le code aujourd'hui. Aucune n'est présentée comme une règle professionnelle validée, sauf mention de l'ingénieur ou du technicien, avec sa date.
> Décisions déjà prises : technicien le 07/10, ingénieur le 10/10 et le 12/10 (documents du projet).

## 7.1 Règles déjà validées (pour mémoire)

| Règle | Source |
|---|---|
| Semelles dimensionnées à l'ELU : A² ≥ Nu / σsol | technicien, 07/10 |
| Dégression de Q : 1 / 0,9 / 0,8 / 0,7 | technicien, 07/10 |
| Q toiture 1,5 kN/m² ; HA12 minimum en semelle ; emprise des poutres déduite des dalles ; agglos pleins au m² | technicien, 07/10 |
| G forfaitaire de 5 kN/m² (contenu validé) | technicien |
| Sol au-delà de 3 bars sans étude : alerte | ingénieur, 10/10 |
| TVA de 18 % (proposée, jamais imposée) | ingénieur, 10/10 |
| Charpente : G = 2,5 kN/m² | ingénieur, 10/10 |
| Pertes de 3 % sur les matériaux, 4 % sur les agglos | ingénieur, 10/10 |
| Mur en agglos de 15 enduit : 3,3 kN/m² | ingénieur, 12/10 |
| Murs du RDC sur les longrines | ingénieur, 12/10 |
| Murs seulement là où ils existent | ingénieur, 12/10 |
| Poutre courte : 20 × 25 cm | ingénieur, 12/10 |

## 7.2 Règles à confirmer

| N° | Ce que fait le code | Unité | Cas limites | Conséquence d'une erreur sur le DQE |
|---|---|---|---|---|
| B1 | Sol non saisi : **180 kN/m²** (signalé comme hypothèse) | kN/m² | sol médiocre (< 100) | Semelles sous-dimensionnées : béton et acier des fondations sous-estimés |
| B2 | Hauteur minimale de poutre de **25 cm appliquée à TOUTES les poutres**, alors que la règle de l'ingénieur visait les poutres qui reprennent un plancher ou un mur | cm | poutres secondaires de moins de 2 m | Béton des poutres légèrement surestimé |
| B3 | Poutres calculées comme **isostatiques** : M = qL²/8 (pas de continuité) | kN·m | poutres continues sur 3 appuis ou plus | Acier sur appui non évalué ; quantité d'acier venant de toute façon du ratio |
| B4 | **Acier par ratio** : poteaux 125, poutres et longrines 150, dalles 85, chaînages 90 kg/m³ (milieux des fourchettes de `constantes.py`) | kg/m³ | R+3 et plus, grandes portées | **Poste acier du DQE potentiellement faux de ±30 %** : c'est l'écart le plus probable |
| B5 | Chaînage forfaitaire de **15 × 20 cm**, sans calcul | cm | – | Béton et acier des chaînages |
| B6 | Maçonnerie : surface × **0,80** (20 % d'ouvertures) quand la surface nette n'est pas saisie | – | façades très vitrées | Agglos, mortier, enduit |
| B7 | Pré-dimension des poteaux : coefficient **1,3** (milieu de 1,2 à 1,5) et côté minimal de 20 cm | – | poteaux peu chargés | Section des poteaux |
| B8 | Rapport γ = Mu/Mser **supposé égal à 1,45** pour la flexion des poutres | – | – | Choix du pivot, donc acier théorique |
| B9 | Dégression **au-delà de 4 étages** : 0,6 puis un minimum de 0,5 (**non validé**) | – | R+4 et plus | Charges des poteaux bas |
| B10 | Approvisionnement : dosages **0,35 T de ciment, 0,45 m³ de sable et 0,85 m³ de gravier** par m³ de béton, **12 agglos/m²** (repris de ton DQE) | – | béton de propreté, dallage | Fiche d'approvisionnement |
| B11 | Hourdis : aucun calcul dans le logiciel ; dans ton DQE, 12 hourdis/m² (même ratio que les agglos) | u/m² | – | Si ajouté, quantité d'hourdis |
| B12 | Dalles : épaisseur = portée/25 à 30 (un sens) ou /35 à 40 (deux sens), entre 12 et 16 cm courants | cm | portée de plus de 5 m | Béton des planchers |
| B13 | fc28 = 25 MPa et fe = 500 MPa par défaut | MPa | béton de chantier non contrôlé | Toutes les sections |
| B14 | Charpente : 2,5 kN/m², supérieur aux charpentes légères en tôle (0,3 à 0,6) | kN/m² | tôle sur charpente bois légère | Sens de la sécurité, à reconfirmer |
| B15 | Un seul plan de murs pour tous les étages | – | R+2 avec des étages différents | Charges des poteaux |

## 7.3 Questions précises à poser en réunion

1. **Acier (B4)** : peux-tu fournir le métré d'acier réel d'un projet déjà construit, pour comparer avec les ratios 125, 150 et 85 kg/m³ ?
2. **Sol (B1)** : faut-il rendre la contrainte du sol **obligatoire** (pas de 180 par défaut), ou garder 180 signalé ?
3. **Poutres (B2, B3)** : 25 cm minimum pour toutes les poutres, ou seulement pour celles qui portent un plancher ou un mur ? La continuité est-elle à prendre en compte dans le pré-dimensionnement ?
4. **Coefficients de ton DQE** (fiche du 02/12/2025, analyse du 16/10) : que représentent **1,02 (ciment), 1,03 (sable), 1,48 (gravier)**, et 1,10 pour la dalle ? Pertes, foisonnement, ou conversion du m³ en tonnes ?
5. **Hourdis (B11)** : combien par m² ? Hauteur du hourdis (12, 16, 20) ?
6. **Maçonnerie (B6)** : 20 % d'ouvertures est-il réaliste pour une villa ? Ou faut-il toujours exiger la surface nette ?
7. **TVA** : 18 % (confirmé le 10/10). Ta fiche affiche « TVA 10 % » : était-ce une erreur ?
8. **Masses volumiques** du sable et du gravier, pour convertir en voyages de 20 T et 30 T.
9. **Semelles de 0,55 m** de ton DQE : le calcul du 10/10 donne 40 à 85 cm (19 semelles sur 28 au-delà de 55 cm). Confirmes-tu le recalcul ?
10. **Contenu exact du G forfaitaire de 5 kN/m²** (dalle, revêtement, cloisons…), pour l'afficher dans le DQE.

## 7.4 Scénarios de test réalistes à proposer par le technicien

- Une **villa R+0** déjà chiffrée par le cabinet, avec son DQE réel en Excel, pour comparer poste par poste.
- Un **R+1 avec plan DXF** réel (ArchiCAD ou AutoCAD) et les murs réels.
- Un **R+2** pour tester la dégression et les murs d'étage.
- Un projet avec **sol faible** (1 bar) pour vérifier les semelles filantes.


---

# 8. Anomalies, risques et fonctionnalités incomplètes

Classées par gravité. « Preuve » renvoie au fichier ou à la ligne constatés pendant l'audit.

## Élevé (confidentialité)

| Réf. | Anomalie | Preuve | Correction proposée |
|---|---|---|---|
| A-22 | **153 fichiers de `media/` sont suivis par git dans un dépôt public** : plans IFC et DXF de projets, dont certains portent le nom d'un client (« Projet_duplex_R1_M._Yebouet_Thomas.ifc »), et logos. `media/` n'est pas dans `.gitignore`. | `git ls-files media` sur `dev` | **Décision du chef de projet, car elle touche des données réelles** : ajouter `media/` au `.gitignore` et retirer les fichiers du suivi (`git rm -r --cached media/`). Rendre le dépôt privé si les clients n'ont pas donné leur accord. Les fichiers restent dans l'historique : seule une réécriture de l'historique les effacerait (opération lourde, à décider à part). |

## Élevé (exactitude du DQE)

| Réf. | Anomalie | Preuve | Correction proposée |
|---|---|---|---|
| A-02 | **Acier des chaînages étiqueté « calculé » alors que c'est un ratio** (90 kg/m³). `dimensionner_chainage` renvoie `poids_acier_total_kg` = volume × ratio ; le DQE prend tout poids > 0 pour un calcul du moteur. | `postes_ratio.py:262-275`, `dqe_calculator.py:406-408`, `calculations.py:210` | Transmettre `hypothese_ratio_acier` et marquer la ligne « estimé ». Ajouter un test. |
| A-03 | **Acier des poteaux, poutres, longrines et dalles par ratio** (125, 150, 150 et 85 kg/m³). Lignes marquées « estimé ». La poutre calcule un poids longitudinal théorique (`poids_acier_longitudinal_theorique_kg`) que le DQE n'utilise pas. | `dqe_calculator.py:77-84`, `:410-417` | Décision d'équipe : ferraillage calculé (barres et cadres) ou ratios validés par le technicien (07, B4). |
| A-05 | Poutres continues calculées comme isostatiques. Caquot est codé et testé mais pas raccordé. Ce n'est pas écrit dans les hypothèses du DQE. | `methode_caquot.py`, aucun appel hors moteur | Écrire l'hypothèse dans les résultats, puis décider s'il faut raccorder Caquot. |
| A-06 | Hauteur minimale de 25 cm étendue à toutes les poutres. | `dimensionnement_poutres.hauteur_poutre_retenue` | Confirmation BTP (07, B2). |

## Moyen

| Réf. | Anomalie | Preuve | Correction proposée |
|---|---|---|---|
| A-04 | Reprise des données de l'IA : Ly reçoit la portée X si elle est vide. Hypothèse de symétrie non signalée. | `Step1_Parametres.jsx`, fonction `champsNlp` | Laisser Ly vide et la demander, ou afficher « Ly = Lx supposée ». |
| A-04b | Une valeur appliquée depuis l'IA devient une saisie sans trace de son origine. | modèle `Projet` (pas de champ d'origine) | Origine par champ (06, section 6.7). |
| A-07 | Les tests écrivent dans le vrai `media/`. | fichiers `media/imports_ifc/plan_*.ifc` non suivis après chaque exécution | `override_settings(MEDIA_ROOT=tempdir)` dans les tests d'import. |
| A-08 | `README.md` obsolète et hors sujet. | `README.md` (« 267/267 tests », plan de coffrage) | Réécrire : présentation, installation, variables d'environnement, tests. |
| A-10 | Jetons JWT en `localStorage` (vol possible en cas de faille XSS). Atténuation : accès de 30 min, rotation, liste noire. | `dqeService.js:21-26` | À discuter : cookie httpOnly pour le refresh. |
| A-14 | Aucun test frontend, pas d'intégration continue. | `package.json` sans script `test` | Vitest sur `dqeService` et les composants critiques, plus un pipeline qui lance `manage.py test` et `npm run build`. |
| A-17 | Mention de responsabilité absente du PDF du DQE (« pré-dimensionnement à faire vérifier par un ingénieur structure »). | recherche dans `pdf_dqe.py` et `dqe_exporters.py` | Ajouter le texte (décision du chef de projet). |
| A-18 | `check --deploy` : HSTS et redirection SSL non activés par défaut. | W004, W008 | Activer sur Railway, en toute connaissance de cause, via les variables `SECURE_SSL_REDIRECT` et `SECURE_HSTS_SECONDS`. |
| A-19 | Confidentialité : plans et descriptions envoyés à Google sans avertissement dans l'interface. | `client.py`, interface | Message et consentement avant le premier envoi. |

## Faible

| Réf. | Anomalie | Preuve |
|---|---|---|
| A-09 | Fichiers très longs : `views.py` (1 524 lignes), `Step1_Parametres.jsx` (711 lignes). | `wc -l` |
| A-11 | Bornes de l'IA (1 à 100 niveaux) différentes de celles du moteur (20 au plus). | `schemas.py`, `constantes.NB_NIVEAUX_MAX` |
| A-12 | Routes doublons, fonctions frontend et routes jamais appelées. | 02, section F ; 05, section 5.1 |
| A-13 | Événement « Import IFC confirmé » enregistré pour un DXF. | `models.py:628`, `views.py:800` |
| A-15 | Doublon de migration `0009_... .py` (nom avec une espace). | `projets/migrations/` |
| A-16 | Étiquette « Source : GEMINI » affichée par défaut quand la source est absente. | `Step1_Parametres.jsx:314` |
| A-20 | Constantes inutilisées et contradictoires (dégression 0,95…, ratio de poutre continue). | `constantes.py:139`, `:164` |
| A-21 | Changement de mot de passe sans écran. | `auth/changer-mot-de-passe/` |
| A-23 | Trois composants inutilisés toujours présents sur `dev` : `DashboardView.jsx`, `FormCouchesCharge.jsx`, `Header.jsx` (aucun import). | recherche sur `dev` |

## Fonctionnalités incomplètes ou limites connues

- **Plan importé** :
  - pas de variantes ;
  - dalles non lues dans le DXF ;
  - poteaux à portée hors domaine non calculés (listés).
- **Murs** : un seul plan pour tous les étages ; maçonnerie et enduit du DQE pas encore tirés de ce plan.
- **Absents** : main-d'œuvre et déboursés détaillés ; historique et comparaison des versions de DQE.
- **Import Excel** : pas testé sur un DQE réel d'un autre bureau d'études.
- **Vision IA** : aperçu seulement, qualité réelle non mesurée.
- **Eurocode 2** : cité, non implémenté.

## Risques projet

| Risque | Impact | Mesure |
|---|---|---|
| Règles BTP non confirmées | DQE faux sans que personne ne le voie | Section 07, validation datée de chaque règle |
| Dépendance au chef de projet pour le moteur | Goulot d'étranglement | Ce document (04) et une revue croisée avec le développeur Django |
| Coût et confidentialité de l'IA | Imprévus | Journal des appels, plafond, consentement |


---

# 9. Support de la réunion technique

Durée conseillée : environ 1 h 15.

| Durée | Séquence |
|---|---|
| 2 min | Introduction |
| 12 à 15 min | Présentation |
| 15 min | Démonstration |
| 25 min | Questions par profil |
| 15 min | Plan d'action et attribution |

---

## A. Introduction (environ 2 minutes, à lire)

> Bonsoir à tous. Si je vous ai réunis ce soir, c'est parce que le projet a beaucoup avancé ces dernières semaines, souvent par petites touches, et que chacun d'entre nous n'en voit qu'une partie.
>
> Avant de continuer à développer, je veux qu'on parte tous de la même photo : ce qui existe vraiment, ce qui fonctionne, ce qui est fragile, et ce qui attend une décision.
>
> J'ai fait auditer le code de bout en bout. Tout ce que je vais vous présenter s'appuie sur ce qui a été vérifié dans le dépôt et sur les 580 tests qui passent aujourd'hui. Quand quelque chose n'est pas vérifié, je le dirai.
>
> À la fin de la réunion, je veux trois choses : que chacun sache ce qu'il doit comprendre, que les règles métier en suspens aient un responsable, et qu'on reparte avec une liste de tâches attribuées.

---

## B. Discours de chef de projet (12 à 15 minutes)

*Texte à dire, en français simple. Les références entre crochets renvoient aux documents de l'audit, pour les questions.*

### 1. La vision (1 min 30)

> Notre logiciel ne doit pas être un simple formulaire qui sort un prix. Il doit aider un bureau d'études à **préparer, contrôler et justifier** un DQE.
>
> Concrètement : on part d'un bâtiment, décrit à la main ou importé depuis un plan. Le logiciel pré-dimensionne la structure en béton armé, un ingénieur valide, et le DQE sort par lots, au prix du cabinet.
>
> Notre règle d'or, c'est **zéro fausse donnée**. Une valeur qui manque, on la demande ou on l'affiche comme hypothèse. On ne l'invente jamais. Et sur chaque ligne du DQE, on sait si la quantité est **calculée, saisie ou estimée**.

### 2. Ce qui a évolué depuis début octobre (2 min)

> Voici les grandes étapes, dans l'ordre :
>
> - **6 et 7 octobre** : on a rendu toutes les hypothèses du moteur explicites. Le PDF du DQE est devenu professionnel. On a intégré les décisions du technicien : semelles à l'ELU, dégression étage par étage, HA12 minimum.
> - **10 octobre** : la toiture en charpente, l'alerte au-delà de 3 bars, la TVA proposée à 18 %, et la **fiche d'approvisionnement** (ciment, sable, gravier, acier, agglos, avec les pertes).
> - **12 octobre** : la **charge des murs**. Les murs sont placés tronçon par tronçon, au RDC et aux étages, baies déduites. Les poutres courtes sont vérifiées à l'effort tranchant.
> - **13 octobre** : l'**import de plans DXF**, depuis AutoCAD ou ArchiCAD.
> - **16 octobre** : les **lots du second œuvre** (09 à 15), la **bibliothèque d'ouvrages** du cabinet, et l'**import d'un DQE Excel** dans cette bibliothèque.

### 3. Les fonctionnalités disponibles aujourd'hui (3 min)

> Je vous fais le tour dans l'ordre où l'utilisateur les rencontre.
>
> - **Comptes** : chaque cabinet a son espace isolé, avec trois rôles. L'admin gère l'équipe et les prix. L'ingénieur valide les calculs. Le technicien prépare.
> - **Étape 1, les paramètres** : niveaux, hauteurs, portées, usage, sol, toiture, poids des murs. On peut aussi importer un plan IFC ou DXF : le logiciel montre un aperçu avant de créer quoi que ce soit.
> - **Étape 2, les calculs** : poteaux, poutres, semelles, longrines, chaînages, avec le plan des murs. Puis les dalles.
> - **Étape 3, la validation** : un ingénieur valide chaque élément. **Tant qu'un élément n'est pas validé, le DQE refuse de se générer.** C'est voulu.
> - **Étape 4, le DQE** : lots 00 à 15, postes complémentaires, marge et TVA si le cabinet les a renseignées. Exports PDF et Excel, plan de fondation en DXF et PDF, fiche d'approvisionnement.
> - **Variantes** : « et si on passait à R+2 ? ». Le moteur recalcule tout sans rien enregistrer.
> - **Tableaux de bord** : pour le cabinet et pour chaque projet.

### 4. Comment marche le moteur de calcul (3 min)

> Le moteur est la partie dont je suis responsable. Il suit le **BAEL 91 modifié 99**.
>
> - D'abord la **descente de charges** : pour chaque poteau, la surface qu'il porte, multipliée par les charges permanentes et d'exploitation. On ajoute le poids propre, la toiture et les murs là où ils existent. ELU = 1,35 G + 1,5 Q.
> - Ensuite le **dimensionnement** :
>   - le poteau, avec la vérification au flambement ; au-delà d'un élancement de 70, le logiciel refuse de conclure et renvoie vers l'ingénieur ;
>   - la poutre, avec une hauteur au moins égale à L/8 et 25 cm, vérifiée en flexion et à l'effort tranchant ;
>   - la semelle, dont l'aire vient de la charge divisée par la contrainte du sol, avec le calcul de ses aciers.
> - Enfin, le **DQE** reprend uniquement les résultats validés : volume de béton, coffrage, acier, multipliés par le barème du cabinet. Les calculs se font en décimal exact, avec un arrondi au franc près seulement à la fin.
>
> **Ce qu'il faut savoir honnêtement** : aujourd'hui, l'acier est **calculé** pour les semelles et les semelles filantes. Pour les poteaux, les poutres, les longrines et les dalles, il est **estimé par un ratio** au kilo par mètre cube. C'est écrit sur la ligne du DQE, mais c'est la principale limite du chiffrage.
>
> Et l'audit a trouvé un cas où ce n'est pas bien étiqueté : l'acier des chaînages est un ratio, mais il est marqué « calculé ». Ce sera corrigé.

### 5. L'architecture (1 min 30)

> Trois couches bien séparées :
>
> 1. React affiche et ne calcule rien de métier ;
> 2. Django vérifie les droits, valide les données et orchestre ;
> 3. le moteur de calcul contient les formules, en Python pur, testées à part.
>
> Toute la conversion des noms de champs entre React et Django passe par un seul fichier, `dqeService.js`. Pour le développeur Django, c'est **le** fichier à surveiller quand on change un champ.

### 6. Le module IA (1 min 30)

> L'IA, c'est Gemini, et elle a un rôle volontairement limité.
>
> - Elle **propose** : elle structure une description en texte libre, suggère la désignation et le lot d'un poste, lit une image de plan en aperçu.
> - Elle **explique** les calculs et les alertes.
> - Elle **ne décide jamais d'un chiffre** : aucune quantité, aucun prix ne vient d'elle sans que l'utilisateur clique sur « Appliquer ».
>
> On a des garde-fous :
>
> - si l'IA écrit un nombre qui n'était pas dans les données, son texte est rejeté ;
> - elle n'a pas le droit d'écrire « conforme » ou « validé » ;
> - chaque appel est journalisé avec sa source.
>
> Ce qui manque : garder la trace qu'une valeur vient de l'IA une fois qu'elle a été appliquée, et prévenir l'utilisateur que ses plans partent chez Google.

### 7. Limites et anomalies (2 min)

> Je préfère qu'on les regarde en face :
>
> - **Nos plans de clients sont publics** : 153 fichiers du dossier media, dont des plans qui portent le nom d'un client, sont dans notre dépôt GitHub public. Il faut décider ce soir quoi faire.
> - **L'acier par ratio**, comme je l'ai dit.
> - **Des règles métier en attente du technicien** : le sol à 180 kN/m² quand il n'est pas saisi, les 25 cm pour toutes les poutres, les 20 % d'ouvertures en maçonnerie, les ratios d'acier, et les coefficients de la fiche d'approvisionnement.
> - **Des fonctions écrites mais pas branchées**, comme le calcul des poutres continues par Caquot. Il faut décider : on branche ou on retire.
> - **Pas de tests automatiques sur l'interface** : 580 tests côté serveur, zéro côté React.
> - Le **README** ne décrit pas le projet.

### 8. Les prochaines étapes (1 min 30)

> Je vous propose trois priorités, à valider ensemble :
>
> 1. **Fiabiliser** : on retire les plans clients du dépôt, on ajoute une intégration continue, et on corrige l'étiquette d'acier des chaînages.
> 2. **Valider le métier** : le technicien confirme ou corrige la liste des règles en suspens, avec un projet réel déjà chiffré pour comparer.
> 3. **Améliorer le chiffrage** : tirer la maçonnerie et l'enduit du plan des murs, puis remplacer progressivement les ratios d'acier par du calcul.
>
> On va maintenant faire un tour de table, puis répartir les tâches.

---

## C. Questions pour l'équipe

### Pour tous

1. Pouvez-vous expliquer, en une phrase, pourquoi le DQE refuse de se générer tant qu'un élément n'est pas validé ?
2. Quelle différence faites-vous entre une ligne « calculée », « saisie » et « estimée » ?

### Développeur Django

3. Quel fichier faut-il modifier en même temps qu'un serializer quand on renomme un champ ?
4. Comment est garanti le cloisonnement entre cabinets ? (`FiltreCabinetMixin`)
5. Pourquoi ne faut-il jamais lancer `makemigrations` sur un dossier non synchronisé ?
6. Comment isolerais-tu `MEDIA_ROOT` dans les tests (A-07) ?

### Développeur IA

7. Que se passe-t-il si Gemini renvoie un nombre absent des données ?
8. Que se passe-t-il si `LLM_PROVIDER` n'est pas défini ?
9. Comment proposerais-tu de conserver l'origine « IA » d'une valeur appliquée ?
10. As-tu vérifié que le modèle « gemini-3.5-flash » existe et à quel coût ?

### Technicien BTP

11. Les questions de la section 7.3 de `07_verifications_btp.md`, de 1 à 10.
12. Peux-tu fournir un DQE réel en Excel et son métré d'acier ?

### Chef de projet (à soi-même)

13. Raccorde-t-on Caquot ou documente-t-on l'hypothèse isostatique ?
14. Quelle mention de responsabilité dans le PDF ?


---

# 10. Répartition des responsabilités et plan d'action

> Les responsables sont **recommandés** : l'attribution finale se fait en réunion.
> Aucune date n'est fixée ici. Les échéances se décident ensemble et se notent dans le compte rendu.

## 10.1 Ce que chacun doit connaître

| Rôle | À lire | Modules à explorer | Décisions à prendre | Livrables attendus |
|---|---|---|---|---|
| **Chef de projet / développeur Python (moteur)** | 01, 04, 08, 09 | `moteur_calcul/`, `services/dqe_calculator.py`, `services/trame_service.py` | Caquot ou hypothèse isostatique ; mention de responsabilité ; priorités | Corrections A-02 et A-05 ; mise à jour des constantes après validation BTP |
| **Développeur Django** | 03, 05, 08 | `projets/views.py`, `serializers.py`, `permissions.py`, `services/`, `api/urls.py`, `frontend/src/api/dqeService.js` | Intégration continue ; découpage de `views.py` | A-07, A-08, A-12, A-13, A-15, A-18 ; pipeline d'intégration continue |
| **Développeur IA** | 06, 08 | `projets/services/assistant_ia/`, `JournalAppelIA`, composants de l'étape 1 | Origine « IA » des valeurs ; consentement ; choix du modèle | A-04, A-04b, A-11, A-16, A-19 ; mesure du coût et de la latence |
| **Technicien BTP** | 01, 07 | Interface : étapes 1 à 4, fiche d'approvisionnement, bibliothèque | Confirmer ou corriger B1 à B15 | Réponses datées ; un projet réel chiffré (Excel et métré d'acier) ; scénarios de test (07, section 7.4) |

## 10.2 Tâches

| N° | Tâche | Problème résolu | Responsable recommandé | Dépend de | Priorité | Résultat attendu | Critère d'acceptation | Risque |
|---|---|---|---|---|---|---|---|---|
| T18 | Sortir les fichiers clients de `media/` du dépôt public (`.gitignore`, `git rm -r --cached media/`) ; décider de rendre le dépôt privé | A-22 | Chef de projet (décision), puis développeur Django | – | **P0** | Plus aucun plan client publié | `git ls-files media` vide ; décision notée | Les fichiers restent dans l'historique ; une réécriture de l'historique est une décision séparée |
| T3 | Intégration continue : `manage.py test` et `npm run build` à chaque envoi | A-14 | Développeur Django | – | P1 | Pipeline au vert | Un test cassé bloque la fusion | – |
| T4 | Étiqueter « estimé » l'acier des chaînages | A-02 | Chef de projet | – | **P1** | Ligne correcte | Nouveau test : chaînage → `ratio_reference` | Change l'affichage de DQE existants (pas leurs montants) |
| T5 | Valider les règles B1 à B15 | Règles non confirmées | Technicien | – | **P1** | Tableau de réponses datées | Chaque règle : « confirmée », « corrigée (valeur) » ou « à étudier » | Réponses partielles : prioriser B4, B1, B2 |
| T6 | Projet réel de comparaison (DQE Excel et métré d'acier) | A-03, test de l'import Excel | Technicien, puis chef de projet | T5 | P1 | Écarts par poste chiffrés | Rapport des écarts ; import Excel réussi sur ce fichier | Données du client : demander l'accord |
| T7 | Isoler `MEDIA_ROOT` dans les tests | A-07 | Développeur Django | – | P2 | Plus de fichiers laissés après les tests | `git status` propre après `manage.py test` | – |
| T8 | Réécrire le README (présentation, installation, environnement, tests) | A-08 | Développeur Django | – | P2 | README utile | Un nouveau membre installe le projet seul | – |
| T9 | Écrire l'hypothèse isostatique dans les résultats, puis décider pour Caquot | A-05 | Chef de projet | T5 (question B3) | P2 | Hypothèse visible, puis décision | Hypothèse présente dans le DQE ; décision notée | Raccorder Caquot change les résultats : à valider |
| T10 | Ne pas copier Lx dans Ly sans le dire ; garder l'origine « IA » | A-04, A-04b | Développeur IA | – | P2 | Valeurs traçables | Test : Ly vide reste vide ou est signalée | – |
| T11 | Aligner les bornes de l'IA sur le moteur ; étiquette « source inconnue » | A-11, A-16 | Développeur IA | – | P3 | Cohérence | Tests mis à jour | – |
| T12 | Avertissement de confidentialité avant un envoi à Gemini | A-19 | Développeur IA | – | P2 | Consentement | Texte validé par le chef de projet | – |
| T13 | Mention de responsabilité dans le PDF | A-17 | Chef de projet | – | P2 | PDF conforme | Texte présent en pied de page | – |
| T14 | Maçonnerie et enduit tirés du plan des murs | Limite connue | Chef de projet | T5 (B6, B10) | P2 | Quantités réelles | Cas de référence vérifié à la main | Double comptage avec les postes de maçonnerie saisis : à prévoir |
| T15 | Nettoyage : routes doublons, fonctions inutilisées, constantes contradictoires, migration en double | A-12, A-15, A-20 | Développeur Django, avec le chef de projet pour les constantes | T3 | P3 | Code plus lisible | Tests verts ; aucune route utilisée supprimée | Clients externes qui utiliseraient un alias : vérifier d'abord |
| T16 | HSTS et redirection SSL en production | A-18 | Développeur Django | – | P2 | `check --deploy` sans avertissement | Variables posées sur Railway | Activer HSTS demande de la prudence (voir la documentation Django) |
| T17 | Écran de changement de mot de passe | A-21 | Développeur Django | – | P3 | Fonction raccordée | Test manuel et test d'API | – |

## 10.3 Ordre recommandé

1. **P0** : T18.
2. **P1, en parallèle** : T3 (Django), T4 (moteur), T5 puis T6 (technicien).
3. **P2** : selon les réponses du technicien (T9, T14) et la disponibilité (T7, T8, T10, T12, T13, T16).
4. **P3** : T11, T15, T17.


---

# Compte rendu — Réunion technique DQE

| Date | Lieu ou outil | Animateur | Secrétaire |
|---|---|---|---|
| | | | |

**Présents** : chef de projet ☐ — développeur Django ☐ — développeur IA ☐ — technicien BTP ☐ — autres :

## 1. Décisions validées

| N° | Décision | Proposée par | Validée par |
|---|---|---|---|
| D1 | | | |
| D2 | | | |
| D3 | | | |

## 2. Erreurs ou incompréhensions corrigées

| Sujet | Ce qu'on croyait | Ce qui est vrai (référence de l'audit) |
|---|---|---|
| | | |

## 3. Règles BTP à confirmer (07, B1 à B15)

| Règle | Réponse du technicien | Statut (confirmée / corrigée / à étudier) | Valeur retenue | Date |
|---|---|---|---|---|
| B1 Sol par défaut 180 kN/m² | | | | |
| B2 25 cm pour toutes les poutres | | | | |
| B3 Poutres isostatiques | | | | |
| B4 Ratios d'acier | | | | |
| B5 Chaînage 15 × 20 | | | | |
| B6 Maçonnerie × 0,80 | | | | |
| B7 Coefficient 1,3 des poteaux | | | | |
| B8 γ = 1,45 | | | | |
| B9 Dégression au-delà de 4 étages | | | | |
| B10 Dosages et 12 agglos/m² | | | | |
| B11 Hourdis/m² | | | | |
| B12 Épaisseur des dalles | | | | |
| B13 fc28 25 MPa, fe 500 MPa | | | | |
| B14 Charpente 2,5 kN/m² | | | | |
| B15 Un plan de murs pour tous les étages | | | | |

## 4. Tâches attribuées

| N° (10.2) | Tâche | Responsable | Échéance convenue | Critère d'acceptation |
|---|---|---|---|---|
| T18 | | | | |
| T4 | | | | |
| | | | | |

## 5. Blocages

| Blocage | Qui peut le lever | Action |
|---|---|---|
| | | |

## 6. Échéances convenues

-

## 7. Points à revoir à la prochaine réunion

-

**Date de la prochaine réunion** :


---

# 12. Couverture de l'audit et limites restantes

| Domaine | Répertoires et fichiers examinés | Fonctionnalités identifiées | Tests consultés ou exécutés | Restant à examiner | Confiance |
|---|---|---|---|---|---|
| Structure et configuration | arborescence, `backend/settings.py`, `backend/urls.py`, `requirements.txt`, `package.json`, `Procfile`, `RAILWAY_DEPLOYMENT.md` (titre seulement) | configuration par variables d'environnement, déploiement Railway | `check`, `check --deploy`, `makemigrations --check` | contenu détaillé de `RAILWAY_DEPLOYMENT.md`, `frontend/Dockerfile`, `frontend/Caddyfile` | élevée |
| Modèles et migrations | `projets/models.py` (lu en entier pour les classes et relations), liste des migrations | 10 modèles, relations | `makemigrations --check` OK | contenu de chaque migration ancienne (0001 à 0023) | élevée |
| Routes et permissions | `api/urls.py`, routes **résolues par Django**, `projets/permissions.py` | 55 routes sous `/api/` (alias compris), 5 permissions métier | `test_matrice_securite`, `test_securite_routes`, `test_permission` (exécutés dans la suite) | – | élevée |
| Vues et serializers | `projets/views.py` (parties : DQE, import, vision, assistants, cabinet, référentiel), `serializers.py` (validations) | voir 02 | suite complète | `auth_views.py` et `analytics_views.py` lus partiellement | moyenne à élevée |
| Moteur de calcul | `constantes.py` (toutes les constantes), `hypotheses.py`, formules poteaux, poutres, semelles (lecture ciblée), carte des fonctions de tous les modules, recherche des appels réels | voir 04 | 115 tests du moteur, plus les tests métier | `complements_plan_coffrage.py`, `tables_acier.py` lus en surface ; formules de dalle et de semelle filante non relues ligne à ligne | élevée sur les flux, moyenne sur le détail de chaque formule |
| Services métier | `dqe_calculator.py` (lecture ciblée : géométrie, acier, finances, conditions), `approvisionnement.py` (en-tête), `variantes.py` (en-tête), `trame_service.py`, `parametres_projet.py` | voir 02 | `test_dqe`, `test_hypotheses_dqe`, `test_approvisionnement`, etc. | `plan_fondation.py` (700 lignes) et `pdf_dqe.py` non relus ligne à ligne ; `analytics.py` non relu | moyenne |
| Import de plans | `lecture_dxf.py`, `lecture_ifc.py` (connus de la session de développement), appels | voir B4 et B5 | `test_import_dxf`, `test_phase_c_dxf`, `test_ifc`, `test_import_plan_api` | IFC d'autres logiciels que ceux testés | moyenne à élevée |
| IA | `assistant_ia/client.py`, `vision.py`, `schemas.py`, `explanations.py`, `coherence_explanations.py`, `prompts.py` (titres), interface de l'étape 1 | voir 06 | 196 tests IA (suite) | `coherence.py` lu partiellement ; **aucun appel réel à Gemini** | moyenne |
| Frontend | liste et tailles des composants, `dqeService.js` (URLs et fonctions utilisées ou non), `Sidebar.jsx`, `App.jsx` (vues), `Step1_Parametres.jsx` (partie IA), bibliothèque | voir 02 | `npm run build` OK ; **0 test** | tableaux de bord, `settingsentreprise.jsx`, `StepPlanFondation.jsx`, `Step4_DQEExport.jsx` non relus en détail pendant cet audit | moyenne |
| Documentation | `README.md`, liste des docs, docs du projet (réponses de l'ingénieur des 10 et 12/10, analyse du 16/10) | contradictions relevées (A-08) | – | `moteur_calcul/README.md`, `projets/readme.md`, `walkthrough_ia.md` non comparés au code | moyenne |
| Historique et branche `dev` | `git log` de la branche `dev` de GitHub (50 derniers commits, du 23/09 au 16/10) ; comparaison fichier par fichier avec le code audité (223 fichiers identiques) | évolutions de la section 9.B.2 ; 5 contributeurs | 580 tests OK sur `dev` | branches `feature/*` non comparées ; historique avant le 23/09 non parcouru | élevée |

## Zones inaccessibles ou impossibles à vérifier

- **Serveur Railway et base de production** : non consultés. Le contenu de la table `Entreprise` dépréciée et les projets orphelins se vérifient avec `python manage.py audit_donnees_production` (lecture seule).
- **Gemini** : pas de clé dans l'environnement d'audit ; comportement vérifié uniquement par des tests avec simulation.
- **Rendu visuel** de toutes les pages : non revérifié pendant cet audit. Les vérifications par navigateur des 14 et 16/10 couvraient le parcours du cas d'usage, la bibliothèque et l'import Excel.

## Conclusion sur la complétude

- Les domaines prioritaires (moteur, DQE, sécurité, IA, contrats d'API) ont été examinés sur leurs chemins d'exécution réels, avec la suite de tests complète exécutée.
- Restent à relire en détail avant de les considérer comme audités :
  - `plan_fondation.py` ;
  - `pdf_dqe.py` ;
  - `analytics.py` ;
  - `coherence.py` ;
  - les composants des tableaux de bord et des paramètres du cabinet.
- **L'audit n'est donc pas exhaustif ligne à ligne**. Ces fichiers n'ont pas d'anomalie connue, mais ils n'ont pas été relus pendant cet audit.


---

