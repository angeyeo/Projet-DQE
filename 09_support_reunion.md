# 9. Support de la réunion technique

Durée conseillée : environ 1 h 15.

| Durée | Séquence |
|---|---|
| 2 min | Introduction |
| 12 à 15 min | Présentation |
| 15 min | Démonstration (si le poste local est réparé, voir A-00) |
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
> - Mon **dossier local est désynchronisé** : le serveur ne démarre pas. C'est la conséquence de nos échanges par zip. Il nous faut un **git partagé**.
> - **L'acier par ratio**, comme je l'ai dit.
> - **Des règles métier en attente du technicien** : le sol à 180 kN/m² quand il n'est pas saisi, les 25 cm pour toutes les poutres, les 20 % d'ouvertures en maçonnerie, les ratios d'acier, et les coefficients de la fiche d'approvisionnement.
> - **Des fonctions écrites mais pas branchées**, comme le calcul des poutres continues par Caquot. Il faut décider : on branche ou on retire.
> - **Pas de tests automatiques sur l'interface** : 580 tests côté serveur, zéro côté React.
> - Le **README** ne décrit pas le projet.

### 8. Les prochaines étapes (1 min 30)

> Je vous propose trois priorités, à valider ensemble :
>
> 1. **Fiabiliser** : un git partagé, une intégration continue, et la correction de l'étiquette d'acier des chaînages.
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
