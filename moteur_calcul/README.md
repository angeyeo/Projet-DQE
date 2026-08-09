# Module `moteur_calcul`

Logique de descente de charges et de dimensionnement (poteaux, poutres,
semelles, dalles), selon les formules BAEL 91 mod.99 fournies par le
technicien BTP.

La référence de calcul est le fichier Excel du technicien
(« Mon Métreur » / Metrec) : chaque formule ajoutée ici cite la feuille
d'origine dans sa docstring.

> Le fichier `moteur_calcul/readme` (sans extension) décrit l'état
> « formules en attente » d'avant la réception du document technicien.
> Il est obsolète — ce `README.md` le remplace.

## Organisation

| Fichier | Rôle |
|---|---|
| `constantes.py` | Valeurs normatives et hypothèses de projet (fc28, fe, gammas, charges d'exploitation, ratios de pré-dimensionnement, bornes de validation) |
| `validators.py` | Validation des entrées utilisateur (lève `EntreeInvalide`) |
| `tables_acier.py` | **Nouveau** — table des diamètres HA commerciaux + choix de barres réelles |
| `formules/descente_charges.py` | Surface d'influence → G → Q → ELU/ELS → cumul par niveau |
| `formules/dimensionnement_poteaux.py` | Compression centrée : section béton, flambement, **section d'acier** |
| `formules/dimensionnement_poutres.py` | Flexion simple : hauteur, moment réduit, **Pivot A et B**, **non-fragilité** |
| `formules/dimensionnement_semelles.py` | Semelle isolée : version simple + **version affinée** |
| `formules/dimensionnement_dalles.py` | Pré-dimensionnement des dalles (inchangé) |
| `tests_moteur_calcul/` | Cas de test connus + tests unitaires |

## Ce qui a changé sur cette branche

Objectif : passer d'un pré-dimensionnement purement indicatif à des
résultats exploitables (vraies sections d'acier, vraies barres,
vérifications réglementaires), alignés sur le fichier de référence du
technicien.

### 1. Nouveau : `tables_acier.py`

Table des sections d'acier réelles (feuille « Sections d'aciers ») :
section (cm²) et masse linéique (kg/m) pour les diamètres HA 5 à 40 mm.

- `proposer_barres(section_requise_cm2, ...)` → convertit une section
  théorique en un choix constructif (diamètre + nombre de barres) en
  **minimisant l'excès de matière**, pas en prenant le premier
  diamètre qui dépasse. Retourne `None` si aucune combinaison
  raisonnable ne couvre la section (plage de diamètres / nombre de
  barres bornée).
- `poids_barres(diametre_mm, nombre_barres, longueur_m)` → poids réel
  d'un jeu de barres, pour les futurs métrés.

### 2. Poteaux — calcul de la vraie section d'acier

Avant : section béton + vérification du flambement uniquement.
Maintenant, `dimensionner_poteau()` renvoie en plus le ferraillage
(feuille « Poteau_compression simple ») via la nouvelle fonction
`calculer_section_acier()` :

```
A_théorique = [Nu/α₂ − Br·fc28/(0,9·γb)] / (fe/γs) × 10⁴
A_min       = max(4 × périmètre , 0,2 % × B)
A_max       = 5 % × B
A_retenue   = max(A_théorique, A_min)
```

Nouveaux champs du dict de retour : `section_acier_theorique_cm2`,
`section_acier_min_cm2`, `section_acier_max_cm2`,
`section_acier_retenue_cm2`, `frettage_necessaire` (vrai si la section
retenue dépasse les 5 %), `barres_proposees`.

Le poteau demande au minimum 4 barres (une par angle), d'où
`nb_barres_min=4` passé à `proposer_barres()`.

**Hypothèse** : α₂ = α₁, c'est-à-dire majorité des charges appliquée
après 90 jours (cas courant en bâtiment) —
`constantes.DELAI_APPLICATION_CHARGES_SUPPOSE`. Le document technicien
prévoit trois cas (> 90 j, 28–90 j, < 28 j) ; à ajuster si le
technicien précise un autre cas pour un projet.

### 3. Poutres — Pivot B, non-fragilité, barres

Avant : au-delà de µ = 0,186 (limite Pivot A/B), le calcul levait
`NotImplementedError` et s'arrêtait là. C'était trop restrictif : une
section en Pivot B reste souvent exploitable sans armature comprimée.

- Nouvelle fonction `calculer_moment_critique_pivot_b(gamma, fc28, fe)`
  (feuille « Flexion simple_sect rect ELUR », cas t > 24 h,
  fc28 ≤ 30 MPa) :
  - fe = 500 : `µc = 0,322·γ + 0,0051·fc28 − 0,31`
  - fe = 400 : `µc = 0,344·γ + 0,0049·fc28 − 0,305`
  - lève `NotImplementedError` hors de ce domaine de validité.
- `dimensionner_poutre()` : si µ > 0,186, on compare µ à µc.
  µ ≤ µc → calcul poursuivi normalement (champ `pivot = "B"`).
  µ > µc → `NotImplementedError` avec un message qui dit quoi faire
  (agrandir la section béton, pas ajouter des aciers).
- Condition de non-fragilité ajoutée :
  `A_min = (ftj/fe) × 0,23 × d × b` avec `ftj = 0,6 + 0,06·fc28` →
  champs `section_acier_min_cm2` et `non_fragilite_respectee`.
- `barres_proposees` calculé sur `max(A_théorique, A_min)`.

**Hypothèse** : le Pivot B a besoin de γ = Mu/Mser, or le moteur ne
reçoit aujourd'hui qu'une charge linéaire déjà pondérée ELU (pas G et Q
séparés). Valeur médiane supposée γ = 1,45
(`constantes.GAMMA_ELU_ELS_SUPPOSE`), signalée dans le retour par
`gamma_estime = True`. Le paramètre `gamma_elu_els` permet de passer la
vraie valeur dès qu'elle est disponible.

`poids_acier_longitudinal_theorique_kg` reste volontairement nommé
ainsi : il ne couvre que les aciers longitudinaux tendus (ni cadres,
ni recouvrements), le DQE doit continuer à utiliser le ratio kg/m³.

### 4. Semelles — version affinée

`dimensionner_semelle()` est **inchangée** dans son comportement et
conservée telle quelle : le modèle Django ne stocke aujourd'hui qu'une
`charge_calculee` unique, le reste de l'app continue donc de marcher.

Nouvelle fonction `dimensionner_semelle_affinee()` (feuille « Semelle
isolée_section béton »), à utiliser quand G et Q sont connus
séparément :

1. Aire approchée `Sapp = (G+Q) / (σ_sol − poids du sol au-dessus)`,
   poids volumique du sol supposé 22 kN/m³ ;
2. Côtés B et A au prorata des côtés réels du poteau (semelle
   rectangulaire, pas seulement carrée), arrondis au multiple de 5 cm ;
3. Hauteur : `d = (B − a)/4`, puis `h = arrondi₅(d) + 5` ;
4. Vérification finale : pression réelle **poids propre de la semelle
   inclus** < contrainte admissible (`condition_respectee`).

⚠️ Attention aux unités : `dimensionner_semelle()` prend la contrainte
du sol en **kN/m²**, `dimensionner_semelle_affinee()` en **MPa**
(1 MPa = 1000 kN/m²). Les charges de la version affinée sont des
charges de **service** (G, Q), pas des charges ELU.

### 5. Constantes ajoutées

- `DELAI_APPLICATION_CHARGES_SUPPOSE = "superieur_90_jours"` (poteaux, α₂)
- `GAMMA_ELU_ELS_SUPPOSE = 1.45` (poutres, Pivot B)

### 6. Tests

`tests_moteur_calcul/donnees_test.py` : les cas de test contenaient des
valeurs placeholder qui ne correspondaient plus aux formules réelles.
Ils sont remplacés par des cas calculés et vérifiés à la main :

- descente de charges : 25 m², dalle 20 cm, habitation →
  G = 125 kN, Q = 37,5 kN, ELU = 225 kN, 2 niveaux = 450 kN ;
- poteau : 250 kN / 3 m → 20×20, λ = 52, α = 0,556, A = 3,2 cm² ;
- poutre : 6 m / 15 kN/m → h = 75 cm, µ = 0,0523, Pivot A, A = 2,36 cm² ;
- semelle : 250 kN / 180 kN/m² → 117,9 cm de côté, h = 23,2 cm.

Côté tests :

- `test_descente_charges.py` : `test_cas_1` lisait une clé
  `resultat_attendu` qui n'existe plus. Éclaté en quatre tests, un par
  étape de la descente (G, Q, ELU par niveau, cumul).
- `test_dimensionnement.py` : les résultats sont comparés **champ par
  champ** et non par égalité du dict entier — le moteur gagne
  régulièrement de nouveaux champs (`barres_proposees`,
  `non_fragilite_respectee`…) et une égalité stricte casserait à chaque
  ajout. Tests de comportement ajoutés : montée automatique de la
  section de poteau sous flambement (450 kN → 25×25), minimum de
  4 barres, poutre en Pivot B exploitable, poutre en Pivot B trop
  chargée qui reste bloquante.

```
$ python manage.py test moteur_calcul
Ran 16 tests in 0.002s
OK
```

## Hypothèses en attente de confirmation du technicien

| Hypothèse | Où | À confirmer |
|---|---|---|
| α₂ = α₁ (charges appliquées après 90 j) | poteaux | Cas réel du projet (> 90 j / 28–90 j / < 28 j) |
| γ = Mu/Mser = 1,45 | poutres (Pivot B) | Fournir G et Q séparément à `dimensionner_poutre()` |
| lf/l0 = 1,0 (poteau articulé) | poteaux | 0,7 si encastrement efficace par les planchers |
| Poids volumique du sol 22 kN/m³ | semelle affinée | Étude géotechnique |
| Contrainte du sol par défaut 180 kN/m² | semelles | Étude géotechnique |
| Charge d'exploitation « industriel » | `constantes.py` | Valeur non fournie (`None`) — le calcul lève `NotImplementedError` |
| Pas de dégression des charges d'exploitation | descente de charges | À revoir si le bâtiment dépasse quelques niveaux |
</content>
</invoke>
