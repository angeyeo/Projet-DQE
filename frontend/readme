# Corrections v2 — Import IFC, Descente de charge, Plan de fondation, Export DXF

Suite du travail précédent (`README_Corrections.md`). Cette fois, **j'ai réellement fait tourner
l'application** (backend Django + frontend Vite) dans mon environnement, avec ton vrai fichier
`Projet_duplex_R_1_M__Yebouet_Thomas.ifc`, pilotée par un navigateur automatisé (Playwright), du
dépôt du fichier jusqu'au téléchargement du DXF. Ça a permis de confirmer les correctifs précédents
ET de découvrir 2 bugs supplémentaires bien plus importants que prévu, maintenant corrigés.

**Aucun fichier backend n'a été modifié dans toute cette session** — uniquement le frontend.

---

## Fichiers modifiés (cumulés v1 + v2)

| Fichier fourni | Chemin de destination dans le dépôt |
|---|---|
| `dqeService.js` | `frontend/src/api/dqeService.js` |
| `Step1_Parametres.jsx` | `frontend/src/components/Step1_Parametres.jsx` |
| `App.jsx` | `frontend/src/App.jsx` |
| `StepPlanFondation.jsx` | `frontend/src/components/StepPlanFondation.jsx` |

---

## Nouveaux bugs trouvés et corrigés dans cette session

### 4. L'Effort Axial (N_sd), la Portée des poutres et la Contrainte du sol étaient TOUJOURS des valeurs codées en dur

**Découverte** : en comparant l'affichage de l'Étape 2 aux vraies charges calculées par le backend
(12,5 à 363,2 kN selon mes propres calculs sur ton fichier), j'ai remarqué que l'écran affichait
"150 kN" pour **chaque poteau**, sans exception. Idem pour "Portée L" des poutres (toujours "5.0 m")
et "Contrainte du Sol" des semelles.

**Cause** : `Step2_Calculs.jsx` lit `item.charge`, `item.effort_axial`, `item.portee`,
`item.contrainteSol` -- mais `formatElement()` dans `dqeService.js` ne produisait jamais ces champs.
Le composant retombait donc systématiquement sur ses valeurs par défaut codées en dur, quelle que
soit la vraie charge calculée. **Les calculs backend étaient corrects depuis le début** -- le
problème était uniquement que le frontend ne les affichait jamais.

**Correctif** : `formatElement()` expose maintenant `charge` (depuis `charge_calculee`), `portee`
(depuis `portee`) et `contrainteSol` (depuis `taux_travail_sol`) -- des champs qui existaient déjà
dans la réponse API (le modèle Django les sérialise via `fields = "__all__"`), simplement jamais lus
côté frontend.

**Vérifié en conditions réelles** (voir capture `t3_step2_calculs.png`) : les efforts axiaux affichent
maintenant `19.8 kN, 19.7 kN, 78.3 kN, 14.1 kN, ..., 363.2 kN` (18 valeurs distinctes sur 21 poteaux),
les portées de poutres varient de `1.31 m` à `10.78 m`. La contrainte du sol reste identique
(`0.20 MPa`) pour toutes les semelles -- **c'est normal et pas un bug** : c'est une constante de
projet unique (`taux_travail_sol=0.2` dans `projets/views.py`) tant qu'aucune étude géotechnique par
zone n'est intégrée, pas une valeur par défaut frontend.

### 5. Le rendu graphique du plan de fondation (SVG) était toujours vide

**Découverte** : sur ta capture d'écran, l'aperçu graphique du plan de fondation n'affichait qu'un
rectangle gris vide, sans aucune semelle visible.

**Cause** : `StepPlanFondation.jsx` positionnait chaque semelle avec `position_x * 40` directement,
sans tenir compte du fait que les coordonnées réelles issues de l'IFC peuvent être exprimées dans un
repère de site géoréférencé avec de grands offsets (ex. `-234.18 m, -44.29 m` sur ton fichier -- visible
dans le tableau de coordonnées). Résultat : `-234.18 * 40 = -9367`, très largement en dehors du
`viewBox` du SVG (`-30 -30 360 240`) -- toutes les semelles étaient dessinées hors champ, d'où le
rectangle vide.

**Correctif** : le composant calcule maintenant le rectangle englobant réel de toutes les semelles
(min/max X et Y), puis choisit une échelle qui fait tenir tout le bâtiment dans le `viewBox`, quelle
que soit l'origine du repère de coordonnées.

**Vérifié en conditions réelles** : 28 rectangles (semelles) sont maintenant dessinés et visibles,
répartis selon la vraie forme irrégulière du bâtiment (voir `t5_plan_fondation.png`).

### 6. La colonne "Dimensions (A x B)" des semelles affichait toujours "n/d"

**Découverte** : en vérifiant la correction du point 4, j'ai remarqué que la colonne dimensions des
semelles à l'Étape 2 restait vide ("n/d") pour toutes les lignes.

**Cause** : `dimensionner_semelle()` (semelle carrée isolée, utilisée par défaut) renvoie un champ
`cote_cm`, pas `largeur_cm`/`hauteur_cm`. `formatSection()` ne testait ce cas que pour le type
`poteau`, pas pour `semelle` -- qui tombait donc toujours sur `'n/d'`.

**Correctif** : `formatSection()` gère maintenant aussi `cote_cm` pour les semelles (et
`grand_cote_cm`/`petit_cote_cm` pour une éventuelle semelle rectangulaire affinée, déjà présents dans
le code backend mais pas encore utilisés par la vue actuelle).

**Vérifié en conditions réelles** : la colonne affiche maintenant des dimensions réelles et variées
(`33.1 x 33.1 cm`, `60.3 x 60.3 cm`, `120.7 x 120.7 cm`, etc. selon la charge de chaque semelle).

---

## Résultat du test de bout en bout (Playwright, sur ton vrai fichier IFC)

| Vérification | Résultat |
|---|---|
| Avertissements de trame irrégulière affichés à l'Étape 1 | ✅ OK |
| Effort axial des poteaux : valeurs réelles et variées (plus jamais "150 kN" fixe) | ✅ OK (12.5 à 363.2 kN) |
| Portée des poutres : valeurs réelles et variées | ✅ OK (1.31 à 10.78 m) |
| Dimensions des semelles calculées et affichées | ✅ OK |
| Rendu graphique du plan de fondation (semelles visibles) | ✅ OK (28 semelles dessinées) |
| Téléchargement du plan DXF | ✅ OK (fichier valide de 75 Ko) |
| Erreurs JavaScript bloquantes en console | Aucune (2 erreurs 403 sur Google Fonts, dues au réseau de mon environnement de test, sans rapport avec l'app) |

Build frontend (`npm run build`) vérifié sans erreur après chaque correctif.

---

## Comment vérifier de ton côté

1. Remplacer les 4 fichiers listés en haut de ce document aux chemins indiqués.
2. `cd frontend && npm run build` -- doit passer sans erreur.
3. Relancer les 267 tests Django (`python manage.py test`) -- aucun fichier backend touché, donc
   aucune régression attendue côté API.
4. Reproduire le scénario complet avec `Projet_duplex_R_1_M__Yebouet_Thomas.ifc` : Étape 1 (import,
   vérifier les avertissements) → Dalles → Étape 2 (vérifier que les efforts axiaux varient d'un
   poteau à l'autre) → Validation → Plan de Fondation (vérifier que les semelles sont visibles sur le
   dessin) → télécharger le DXF.

## Ce qui n'est toujours PAS couvert par ces correctifs

- La logique de `detecter_parametres_trame()` (grille approximative affichée à l'Étape 1) n'a pas été
  modifiée -- seul l'affichage de ses avertissements l'est.
- Les constantes provisoires de `postes_ratio.py` -- toujours non validées par un technicien.
- La contrainte du sol reste une constante unique de projet (0.20 MPa partout) -- correcte pour le
  MVP actuel, mais à faire évoluer si une étude géotechnique par zone doit être intégrée un jour.
- Je n'ai pas testé le générateur de DQE (Étape 4, Excel/PDF) ni le module IA (`assistant_ia`) dans
  cette session -- à couvrir dans un prochain passage si vous voulez que je les vérifie aussi de la
  même façon (test réel automatisé plutôt qu'une lecture de code).