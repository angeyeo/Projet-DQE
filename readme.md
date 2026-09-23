# Comment passer de l'aperçu actuel à un rendu façon plan de coffrage professionnel

## Le point de départ à corriger d'abord : deux rendus différents

Il y a deux choses distinctes dans l'app, à ne pas confondre :
1. **L'aperçu SVG dans le navigateur** (ce que montre ta capture) -- une vue rapide et volontairement
   simplifiée, jamais destinée à remplacer un plan technique.
2. **Le vrai fichier DXF téléchargé** -- ouvrable dans AutoCAD/DraftSight, qui contenait déjà, avant
   même cette session, des éléments professionnels que l'aperçu web ne montre pas : cotations réelles
   (entités DXF, pas du texte), joints de dilatation, contour du dallage avec épaisseur pré-dimensionnée,
   calques séparés par type d'ouvrage.

Ce qui manquait pour se rapprocher de ton exemple (`01-ENSEMBLE_FONDATION_COFFRAGE_GENERAL.pdf`) :
**le système d'axes de repère** (lettres A à O en bordure verticale, chiffres 1 à 11 en bordure
horizontale, avec bulles aux extrémités) -- l'élément le plus immédiatement reconnaissable d'un plan
de coffrage professionnel, et celui qui permet à un maçon de se repérer sur le chantier ("le poteau
en C-4").

## Ce que j'ai fait

Ajouté `_dessiner_axes_reperes()` dans `projets/services/plan_fondation.py` : elle regroupe les
positions réelles des semelles par alignement (comme le fait déjà `detecter_parametres_trame()` pour
la trame, mais avec une tolérance plus large et purement pour l'annotation visuelle), trace une ligne
de grille par alignement, et place des bulles numérotées (colonnes) ou lettrées (lignes) à leurs
extrémités -- exactement la convention de ton exemple.

**Testé sur ton vrai fichier IFC**, DXF régénéré et converti en image pour vérification :

- Avant : semelles et chaînage seuls, sans aucun repère de position
- Après : voir `avant_apres_axes_reperes.png` -- axes A à G et 1 à 7 apparaissent, avec les cotations
  déjà existantes maintenant bien plus lisibles en contexte

267/267 tests Django toujours au vert après l'ajout (aucun test existant ne portait sur les axes, donc
aucune régression possible ; à compléter par un nouveau test dédié si vous voulez figer ce
comportement).

## Fichier modifié

| Fichier fourni | Chemin de destination |
|---|---|
| `plan_fondation.py` | `projets/services/plan_fondation.py` |

Nouveau paramètre exposé sur `generer_plan_fondation_dxf()` : `dessiner_axes_reperes=True` (par
défaut) et `tolerance_axe_reperes_m=0.4` (ajustable si un bâtiment très irrégulier génère trop d'axes
pour rester lisible -- voir docstring de la fonction).

## Ce qu'il reste pour se rapprocher encore plus de ton exemple

Par ordre d'impact visuel probable :

1. **Identifiants trop verbeux** -- le plan actuel affiche des identifiants générés automatiquement
   du type `S_2VVrsGkR196O0CK5J8YgjG`, alors que ton exemple utilise des labels courts et groupés par
   taille (`S1`, `S2`, `S3`...). Sur le rendu de test, ça surcharge visiblement le plan et fait se
   chevaucher les textes. Piste : grouper les semelles par plage de dimensions (ex. arrondir `cote_cm`
   au multiple de 10 supérieur) et leur donner un nom de type court (S1, S2, S3...) plutôt qu'un nom
   individuel par semelle -- garder l'identifiant complet uniquement dans le tableau de coordonnées,
   pas sur le dessin.
2. **Cartouche (titre, échelle, date, numéro de plan)** -- absent du DXF actuel, présent dans tout
   plan professionnel déposé.
3. **Repères sur les poteaux également**, pas seulement sur les axes de la grille (ton exemple nomme
   aussi chaque poteau : P1, P2, P3 groupés par type).

Je peux implémenter le point 1 (regroupement des labels par taille) dès que vous voulez -- c'est le
changement qui rapprocherait le plus visiblement le rendu de ton exemple, plus encore que les axes.

---

## Mise à jour -- point 1 fait : regroupement des labels par taille (S1, S2, S3... / P1, P2...)

Ajouté `_grouper_par_type()` dans le même fichier : arrondit chaque dimension au pas supérieur
(configurable), regroupe les semelles/poteaux par taille standardisée, et attribue un label court
(la plus grande en premier -- même convention que ton exemple). Le dessin affiche maintenant
`S1(160x160x35)` au lieu de `S_2VVrsGkR196O0CK5J8YgjG` -- l'identifiant complet reste disponible dans
le tableau de coordonnées de l'app pour la traçabilité, il n'encombre plus le dessin.

Une nomenclature (légende) est ajoutée en bas du plan, listant chaque type avec ses dimensions et le
nombre d'éléments concernés -- équivalent simplifié d'une nomenclature de plan de coffrage.

**Nouveau paramètre à régler avec un technicien** : `pas_cm_regroupement_semelles` (5 cm par défaut).
Sur ton fichier de test, un pas de 5 cm donne 14 types différents (matériellement optimal, mais
visuellement chargé) ; un pas de 20 cm ramène à 7 types, très proche des 5 de ton exemple -- au prix
d'un léger surdimensionnement de certaines semelles (arrondi plus généreux). C'est un vrai choix de
compromis matière/simplicité de chantier, pas une valeur techniquement "correcte" en soi -- à trancher
avec un technicien BTP avant de fixer une valeur par défaut définitive en production.

Testé sur ton vrai fichier IFC avec les deux pas (voir `avant_apres_labels_groupes.png` pour la
comparaison GUID vs labels groupés, `apercu_plan_final.png` pour le rendu avec pas=20cm). 267/267
tests Django toujours au vert.