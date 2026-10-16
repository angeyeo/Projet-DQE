# Audit mathématique, traçabilité et DQE professionnel — 06/10/2026

## 1. Chaîne de calcul (après correction)

couches/G saisi/forfait → descente de charges (surface d'influence, dégression NF P06-001) → combinaisons ELU 1,35G+1,5Q et ELS G+Q → poteau (BAEL, flambement) → semelle (bielles, méthode ELU ou ELS choisie) → poutres (q·L²/8, γ = pu/pser réel) → quantités (× nombre de niveaux) → DQE (barème daté du cabinet, marge, TVA).

Chaque résultat d'élément contient `trace` (étape, formule, valeurs, résultat, unité) et `hypotheses_calcul` (G et son origine, Q, σsol, méthode des semelles, poids propre).

## 2. Constats de l'audit (cause → correction)

| # | Constat | Gravité | Correction |
|---|---------|---------|-----------|
| A1 | **Poteaux et poutres comptés pour UN seul niveau au DQE** quel que soit `nb_niveaux` (trame générée sur un seul niveau) | Critique (DQE sous-estimé ~×n sur ces ouvrages) | Champ `nombre_identiques` (= nb_niveaux), quantités × n, affiché dans la formule |
| A2 | Hauteur de semelle isolée = d (sans enrobage) et côté non arrondi | Moyenne | h = arrondi5(d + 5 cm) ≥ 20 cm, côté arrondi au 5 cm supérieur ; valeurs théoriques conservées |
| A3 | Semelles dimensionnées avec Nu (ELU) contre σsol admissible, sans le dire | Décision métier | Méthode explicite par projet (`ELU` = historique, `ELS` = usage courant), tracée |
| A4 | G = 5 kN/m² forfaitaire codé en dur | Moyenne | G par projet : composition > saisie > forfait signalé « HYPOTHÈSE » |
| A5 | Poids propre des poutres/poteaux/semelles jamais compté | Décision métier | Option projet `inclure_poids_propre_ossature` (b·h·25 ; itération sur la section du poteau) |
| A6 | γ = Mu/Mser des poutres supposé 1,45 | Faible | γ = pu/pser réel transmis par la trame |
| A7 | Acier des semelles toujours estimé au ratio | Faible | As = Nu(A−b)/(8·d·fsu) par direction, barres (espacement ≤ 20 cm), poids calculé |
| A8 | Facteurs d'unités dispersés (0.1, 1000, 1e4) | Faible | `moteur_calcul/unites.py` (conversions nommées, exactes) |
| A9 | Recalcul isolé d'une semelle ignorait méthode et Ns | Moyenne | Ns stocké (`charge_service`), même méthode qu'à la génération |

Vérifié conforme (aucune modification) : surface d'influence, dégression (égale à Q0+Q1+0,9Q2+… pour étages identiques), formules poteau (Br, α(λ), A min/max), flexion (fbu, µ, α, z, As, non-fragilité, µlu Fe500), dalles (α = Lx/Ly, L/35 et L/25, min 12 cm).

## 3. Projets de référence (calculs manuels, `test_projets_reference.py`)

12 cas : villa plain-pied, R+1, R+2 (dégression), immeuble R+4 bureaux, commercial sans dégression, grande portée 8 m (pivot B), sols faible / normal / très résistant (ELU et ELS), plancher composé + poids propre, dalles 1 et 2 sens, traçabilité. Tolérances : efforts 0,5 %, dimensions retenues exactes (valeurs discrètes), aciers 1 %.

## 4. Plausibilité (signaler, jamais modifier)

`moteur_calcul/plausibilite.py` : portée, hauteur d'étage, G, Q, σsol, nombre de niveaux, côté de poteau, côté de semelle, semelles jointives (côté ≥ entraxe), épaisseur de dalle, acier > 5 %. Messages « ALERTE — valeur inhabituelle … (plage courante …) ».

## 5. DQE professionnel

Lignes : formule de métré, type de donnée (calculé / estimé / saisi), renvoi d'hypothèse, prix avec source et date (traçage serveur à chaque changement). Lots → sous-lots (fondations, poteaux, poutres, dalles, ratio, postes saisis). Finances : nature du barème (prix de vente HT ou déboursé sec), marge, TVA, TTC — un taux non renseigné n'est jamais supposé (montant « non calculé » + message). Exports PDF/Excel alignés. Les prix « fourni-posé » ne permettent pas de séparer matériaux / main-d'œuvre / matériel : c'est dit, rien n'est inventé.

## 6. Variantes

`POST /api/projets/{id}/variantes/` : chaque variante (σsol, G, Q, portées, niveaux, méthode des semelles, poids propre) est recalculée par le moteur complet dans une transaction annulée. Rien n'est enregistré ; écarts vs projet actuel.

## 7. Décisions métier requises

1. Méthode des semelles par défaut : ELU (historique, plus prudent) ou ELS (usage courant).
2. Poids propre de l'ossature : l'ajouter par défaut ? (G forfaitaire 5 kN/m² ne l'inclut pas.)
3. Valeur et contenu du forfait G = 5 kN/m².
4. Sections du niveau le plus chargé reprises à tous les niveaux (métré prudent) : acceptable ?
5. Métré des intersections poutre/poteau/dalle (longueur entre axes aujourd'hui) : passer « entre nus » ?
6. Espacement maximal des barres de semelle (20 cm retenu).
7. Q de toiture distincte de Q d'étage.
8. `agglos_pleins_m3` à 9 000 FCFA/m³ : unité à confirmer.
9. Plages de plausibilité (`PLAGES`).

## 8. Données de production (rien n'a été modifié)

`python manage.py audit_donnees_production [--json]` (lecture seule) chiffre : orphelins, lignes `Entreprise` dépréciées, sols < 25 kN/m² (MPa/bar probables), projets multi-niveaux à régénérer (DQE sous-estimé), semelles à l'ancienne formule, résultats sans trace, barèmes incomplets ou non datés, prix agglos au m³. Migrations 0019/0020 : additives, défauts = comportement historique (ELU, sans poids propre, n = 1) ; testées sur une base au schéma 0018 contenant des données anciennes.

Procédure proposée : sauvegarde → migrate → audit → décision projet par projet (régénérer la trame, convertir un sol, rattacher un orphelin) → revalidation ingénieur.

## 9. Sécurité

`test_matrice_securite.py` : anonyme / technicien / ingénieur / admin du cabinet A / cabinet B / staff × projets, éléments, postes, variantes, analytics, paramètres, équipe. Autre cabinet → 404 ; validation/déverrouillage/suppression → ingénieur ou admin ; paramètres et équipe → admin ; analytics staff → staff.
