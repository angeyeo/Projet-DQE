#!/usr/bin/env bash
# Crée les étiquettes et les 16 issues du plan d'action (audit du 17/10/2026),
# puis les ajoute au projet https://github.com/users/angeyeo/projects/1
# Prérequis : gh installé, puis : gh auth login && gh auth refresh -s project
# Relançable sans doublon : une issue dont le titre existe déjà est ignorée.
set -euo pipefail
REPO="angeyeo/Projet-DQE"; OWNER="angeyeo"; PROJET=1
gh auth status >/dev/null 2>&1 || { echo "Connecte-toi d'abord : gh auth login"; exit 1; }

etiquette() { gh label create "$1" -R "$REPO" --color "$2" --description "$3" --force >/dev/null; }
etiquette P0 B91C1C "Priorité 0 : à traiter tout de suite"
etiquette P1 C2410C "Priorité 1"
etiquette P2 B45309 "Priorité 2"
etiquette P3 78716C "Priorité 3"
etiquette moteur 0F766E "Moteur de calcul et DQE"
etiquette backend 475569 "Django, API, tests, déploiement"
etiquette ia 7C3AED "Assistants IA"
etiquette metier 1D4ED8 "Règles BTP, technicien"
etiquette securite 991B1B "Sécurité et confidentialité"
etiquette audit-2026-10-17 E7E5E4 "Issu de l'audit du 17/10/2026"

creer() {
  local titre="$1" etiquettes="$2" corps; corps="$(cat)"
  local url; url="$(gh issue list -R "$REPO" --state all --search "\"$titre\" in:title" --json url,title -q ".[] | select(.title==\"$titre\") | .url" | head -n1)"
  if [ -z "$url" ]; then url="$(gh issue create -R "$REPO" --title "$titre" --label "$etiquettes" --body "$corps")"; echo "créée   : $url"; else echo "existe  : $url"; fi
  gh project item-add "$PROJET" --owner "$OWNER" --url "$url" >/dev/null && echo "          ajoutée au projet"
}

creer 'T18 · Sortir les fichiers clients de media/ du dépôt public (.gitignore, git rm -r --cached media/) ; décider de rendre le dépôt privé' 'P0,securite,audit-2026-10-17' <<'FIN'
**Problème résolu** : A-22 (références de l'audit du 17/10/2026, livrable 08)
**Responsable recommandé** : Chef de projet (décision), puis développeur Django
**Dépend de** : –
**Priorité** : P0
**Résultat attendu** : Plus aucun plan client publié

### Critère d'acceptation
- [ ] `git ls-files media` vide ; décision notée

### Risque
Les fichiers restent dans l'historique ; une réécriture de l'historique est une décision séparée

_Issue créée depuis l'audit du 17/10/2026 (document « audit-equipe-2026-10-17 »)._
FIN

creer 'T3 · Intégration continue : manage.py test et npm run build à chaque envoi' 'P1,backend,audit-2026-10-17' <<'FIN'
**Problème résolu** : A-14 (références de l'audit du 17/10/2026, livrable 08)
**Responsable recommandé** : Développeur Django
**Dépend de** : –
**Priorité** : P1
**Résultat attendu** : Pipeline au vert

### Critère d'acceptation
- [ ] Un test cassé bloque la fusion

_Issue créée depuis l'audit du 17/10/2026 (document « audit-equipe-2026-10-17 »)._
FIN

creer 'T4 · Étiqueter « estimé » l'\''acier des chaînages' 'P1,moteur,audit-2026-10-17' <<'FIN'
**Problème résolu** : A-02 (références de l'audit du 17/10/2026, livrable 08)
**Responsable recommandé** : Chef de projet
**Dépend de** : –
**Priorité** : P1
**Résultat attendu** : Ligne correcte

### Critère d'acceptation
- [ ] Nouveau test : chaînage → `ratio_reference`

### Risque
Change l'affichage de DQE existants (pas leurs montants)

_Issue créée depuis l'audit du 17/10/2026 (document « audit-equipe-2026-10-17 »)._
FIN

creer 'T5 · Valider les règles B1 à B15' 'P1,metier,audit-2026-10-17' <<'FIN'
**Problème résolu** : Règles non confirmées (références de l'audit du 17/10/2026, livrable 08)
**Responsable recommandé** : Technicien
**Dépend de** : –
**Priorité** : P1
**Résultat attendu** : Tableau de réponses datées

### Critère d'acceptation
- [ ] Chaque règle : « confirmée », « corrigée (valeur) » ou « à étudier »

### Risque
Réponses partielles : prioriser B4, B1, B2

### Règles à confirmer (livrable 07)
Répondre en commentaire, une ligne par règle : confirmée / corrigée (valeur) / à étudier, avec la date.

- [ ] **B1** — Sol non saisi : **180 kN/m²** (signalé comme hypothèse) (unité : kN/m² ; si faux : Semelles sous-dimensionnées : béton et acier des fondations sous-estimés)
- [ ] **B2** — Hauteur minimale de poutre de **25 cm appliquée à TOUTES les poutres**, alors que la règle de l'ingénieur visait les poutres qui reprennent un plancher ou un mur (unité : cm ; si faux : Béton des poutres légèrement surestimé)
- [ ] **B3** — Poutres calculées comme **isostatiques** : M = qL²/8 (pas de continuité) (unité : kN·m ; si faux : Acier sur appui non évalué ; quantité d'acier venant de toute façon du ratio)
- [ ] **B4** — **Acier par ratio** : poteaux 125, poutres et longrines 150, dalles 85, chaînages 90 kg/m³ (milieux des fourchettes de `constantes.py`) (unité : kg/m³ ; si faux : **Poste acier du DQE potentiellement faux de ±30 %** : c'est l'écart le plus probable)
- [ ] **B5** — Chaînage forfaitaire de **15 × 20 cm**, sans calcul (unité : cm ; si faux : Béton et acier des chaînages)
- [ ] **B6** — Maçonnerie : surface × **0,80** (20 % d'ouvertures) quand la surface nette n'est pas saisie (unité : – ; si faux : Agglos, mortier, enduit)
- [ ] **B7** — Pré-dimension des poteaux : coefficient **1,3** (milieu de 1,2 à 1,5) et côté minimal de 20 cm (unité : – ; si faux : Section des poteaux)
- [ ] **B8** — Rapport γ = Mu/Mser **supposé égal à 1,45** pour la flexion des poutres (unité : – ; si faux : Choix du pivot, donc acier théorique)
- [ ] **B9** — Dégression **au-delà de 4 étages** : 0,6 puis un minimum de 0,5 (**non validé**) (unité : – ; si faux : Charges des poteaux bas)
- [ ] **B10** — Approvisionnement : dosages **0,35 T de ciment, 0,45 m³ de sable et 0,85 m³ de gravier** par m³ de béton, **12 agglos/m²** (repris de ton DQE) (unité : – ; si faux : Fiche d'approvisionnement)
- [ ] **B11** — Hourdis : aucun calcul dans le logiciel ; dans ton DQE, 12 hourdis/m² (même ratio que les agglos) (unité : u/m² ; si faux : Si ajouté, quantité d'hourdis)
- [ ] **B12** — Dalles : épaisseur = portée/25 à 30 (un sens) ou /35 à 40 (deux sens), entre 12 et 16 cm courants (unité : cm ; si faux : Béton des planchers)
- [ ] **B13** — fc28 = 25 MPa et fe = 500 MPa par défaut (unité : MPa ; si faux : Toutes les sections)
- [ ] **B14** — Charpente : 2,5 kN/m², supérieur aux charpentes légères en tôle (0,3 à 0,6) (unité : kN/m² ; si faux : Sens de la sécurité, à reconfirmer)
- [ ] **B15** — Un seul plan de murs pour tous les étages (unité : – ; si faux : Charges des poteaux)

_Issue créée depuis l'audit du 17/10/2026 (document « audit-equipe-2026-10-17 »)._
FIN

creer 'T6 · Projet réel de comparaison (DQE Excel et métré d'\''acier)' 'P1,metier,audit-2026-10-17' <<'FIN'
**Problème résolu** : A-03, test de l'import Excel (références de l'audit du 17/10/2026, livrable 08)
**Responsable recommandé** : Technicien, puis chef de projet
**Dépend de** : T5
**Priorité** : P1
**Résultat attendu** : Écarts par poste chiffrés

### Critère d'acceptation
- [ ] Rapport des écarts ; import Excel réussi sur ce fichier

### Risque
Données du client : demander l'accord

_Issue créée depuis l'audit du 17/10/2026 (document « audit-equipe-2026-10-17 »)._
FIN

creer 'T7 · Isoler MEDIA_ROOT dans les tests' 'P2,backend,audit-2026-10-17' <<'FIN'
**Problème résolu** : A-07 (références de l'audit du 17/10/2026, livrable 08)
**Responsable recommandé** : Développeur Django
**Dépend de** : –
**Priorité** : P2
**Résultat attendu** : Plus de fichiers laissés après les tests

### Critère d'acceptation
- [ ] `git status` propre après `manage.py test`

_Issue créée depuis l'audit du 17/10/2026 (document « audit-equipe-2026-10-17 »)._
FIN

creer 'T8 · Réécrire le README (présentation, installation, environnement, tests)' 'P2,backend,audit-2026-10-17' <<'FIN'
**Problème résolu** : A-08 (références de l'audit du 17/10/2026, livrable 08)
**Responsable recommandé** : Développeur Django
**Dépend de** : –
**Priorité** : P2
**Résultat attendu** : README utile

### Critère d'acceptation
- [ ] Un nouveau membre installe le projet seul

_Issue créée depuis l'audit du 17/10/2026 (document « audit-equipe-2026-10-17 »)._
FIN

creer 'T9 · Écrire l'\''hypothèse isostatique dans les résultats, puis décider pour Caquot' 'P2,moteur,audit-2026-10-17' <<'FIN'
**Problème résolu** : A-05 (références de l'audit du 17/10/2026, livrable 08)
**Responsable recommandé** : Chef de projet
**Dépend de** : T5 (question B3)
**Priorité** : P2
**Résultat attendu** : Hypothèse visible, puis décision

### Critère d'acceptation
- [ ] Hypothèse présente dans le DQE ; décision notée

### Risque
Raccorder Caquot change les résultats : à valider

_Issue créée depuis l'audit du 17/10/2026 (document « audit-equipe-2026-10-17 »)._
FIN

creer 'T10 · Ne pas copier Lx dans Ly sans le dire ; garder l'\''origine « IA »' 'P2,ia,audit-2026-10-17' <<'FIN'
**Problème résolu** : A-04, A-04b (références de l'audit du 17/10/2026, livrable 08)
**Responsable recommandé** : Développeur IA
**Dépend de** : –
**Priorité** : P2
**Résultat attendu** : Valeurs traçables

### Critère d'acceptation
- [ ] Test : Ly vide reste vide ou est signalée

_Issue créée depuis l'audit du 17/10/2026 (document « audit-equipe-2026-10-17 »)._
FIN

creer 'T11 · Aligner les bornes de l'\''IA sur le moteur ; étiquette « source inconnue »' 'P3,ia,audit-2026-10-17' <<'FIN'
**Problème résolu** : A-11, A-16 (références de l'audit du 17/10/2026, livrable 08)
**Responsable recommandé** : Développeur IA
**Dépend de** : –
**Priorité** : P3
**Résultat attendu** : Cohérence

### Critère d'acceptation
- [ ] Tests mis à jour

_Issue créée depuis l'audit du 17/10/2026 (document « audit-equipe-2026-10-17 »)._
FIN

creer 'T12 · Avertissement de confidentialité avant un envoi à Gemini' 'P2,ia,audit-2026-10-17' <<'FIN'
**Problème résolu** : A-19 (références de l'audit du 17/10/2026, livrable 08)
**Responsable recommandé** : Développeur IA
**Dépend de** : –
**Priorité** : P2
**Résultat attendu** : Consentement

### Critère d'acceptation
- [ ] Texte validé par le chef de projet

_Issue créée depuis l'audit du 17/10/2026 (document « audit-equipe-2026-10-17 »)._
FIN

creer 'T13 · Mention de responsabilité dans le PDF' 'P2,moteur,audit-2026-10-17' <<'FIN'
**Problème résolu** : A-17 (références de l'audit du 17/10/2026, livrable 08)
**Responsable recommandé** : Chef de projet
**Dépend de** : –
**Priorité** : P2
**Résultat attendu** : PDF conforme

### Critère d'acceptation
- [ ] Texte présent en pied de page

_Issue créée depuis l'audit du 17/10/2026 (document « audit-equipe-2026-10-17 »)._
FIN

creer 'T14 · Maçonnerie et enduit tirés du plan des murs' 'P2,moteur,audit-2026-10-17' <<'FIN'
**Problème résolu** : Limite connue (références de l'audit du 17/10/2026, livrable 08)
**Responsable recommandé** : Chef de projet
**Dépend de** : T5 (B6, B10)
**Priorité** : P2
**Résultat attendu** : Quantités réelles

### Critère d'acceptation
- [ ] Cas de référence vérifié à la main

### Risque
Double comptage avec les postes de maçonnerie saisis : à prévoir

_Issue créée depuis l'audit du 17/10/2026 (document « audit-equipe-2026-10-17 »)._
FIN

creer 'T15 · Nettoyage : routes doublons, fonctions inutilisées, constantes contradictoires, migration en double' 'P3,backend,audit-2026-10-17' <<'FIN'
**Problème résolu** : A-12, A-15, A-20 (références de l'audit du 17/10/2026, livrable 08)
**Responsable recommandé** : Développeur Django, avec le chef de projet pour les constantes
**Dépend de** : T3
**Priorité** : P3
**Résultat attendu** : Code plus lisible

### Critère d'acceptation
- [ ] Tests verts ; aucune route utilisée supprimée

### Risque
Clients externes qui utiliseraient un alias : vérifier d'abord

Inclure aussi la suppression des trois composants inutilisés : `DashboardView.jsx`, `FormCouchesCharge.jsx`, `Header.jsx` (A-23).

_Issue créée depuis l'audit du 17/10/2026 (document « audit-equipe-2026-10-17 »)._
FIN

creer 'T16 · HSTS et redirection SSL en production' 'P2,securite,audit-2026-10-17' <<'FIN'
**Problème résolu** : A-18 (références de l'audit du 17/10/2026, livrable 08)
**Responsable recommandé** : Développeur Django
**Dépend de** : –
**Priorité** : P2
**Résultat attendu** : `check --deploy` sans avertissement

### Critère d'acceptation
- [ ] Variables posées sur Railway

### Risque
Activer HSTS demande de la prudence (voir la documentation Django)

_Issue créée depuis l'audit du 17/10/2026 (document « audit-equipe-2026-10-17 »)._
FIN

creer 'T17 · Écran de changement de mot de passe' 'P3,backend,audit-2026-10-17' <<'FIN'
**Problème résolu** : A-21 (références de l'audit du 17/10/2026, livrable 08)
**Responsable recommandé** : Développeur Django
**Dépend de** : –
**Priorité** : P3
**Résultat attendu** : Fonction raccordée

### Critère d'acceptation
- [ ] Test manuel et test d'API

_Issue créée depuis l'audit du 17/10/2026 (document « audit-equipe-2026-10-17 »)._
FIN

echo; echo "Terminé. Tableau : https://github.com/users/angeyeo/projects/1"
