# Projet DQE — Backend & API REST

Module backend Django dédié au dimensionnement structurel BTP, à l'exécution du moteur de calcul et à la génération automatique de Devis Quantitatifs Estimatifs (DQE).

---

## 🚀 Livrables de la Phase 2 (Backend DRF — Samuel YEO)

Cette mise à jour intègre l'ensemble des fonctionnalités backend requises pour la Phase 2 afin de prendre en charge des cas de calcul BTP complexes.

### 📌 Module 6 : Lien Semelle-Poteau en Base de Données
- **Modèle Data** : Ajout du champ `poteau_associe` (`ForeignKey`) sur `ElementStructurel` pointant vers l'élément poteau supporté.
- **Service Calcul** : Propagation automatique de la dimension calculée du poteau (`cote_cm`) lors du pré-dimensionnement de la semelle associée dans `services/calculations.py`.
- **API Serializer** : Exposition du champ `poteau_associe` dans `ElementStructurelSerializer`.

### 📌 Module 7 : Dalles Pleines à l'API REST
- **Modèle Data** : Ajout du type d'élément `DALLE` (`dalle`) dans l'énumération des choix du modèle.
- **Raccordement Moteur** : Connexion sécurisée de l'action `/calculer/` avec la fonction `predimensionner_dalle()` du moteur de calcul via import dynamique.

### 📌 Module 4 : Semelles Filantes
- **Modèle Data** : Intégration du type d'élément `SEMELLE_FILANTE` (`semelle_filante`).
- **Raccordement Moteur** : Gestion des charges linéaires continues ($kN/m$) via `dimensionner_semelle_filante()` avec gestion d'import sécurisé.

### 📌 Module 2 : Charges Permanentes Composées (Multi-couches)
- **Modèle Data** : Création du modèle `CoucheCharge` (désignation, épaisseur en cm, poids volumique en $kN/m^3$) relié aux projets et éléments.
- **Service Calcul** : Implémentation du calcul automatique de la charge permanente surfacique cumulée $G$ ($kN/m^2$).
- **API REST** : Exposition du ViewSet `/api/couches-charges/` dans `views.py` et enregistrement de la route dans `api/urls.py`.

---

## 🧪 Validation & Suite de Tests
- **Périmètre couvert** : Endpoints REST API, verrous logiciels de validation, génération DQE, Assistant IA et intégration du Moteur BTP.
- **Résultat** : **100 % de réussite (59 tests sur 59 validés au vert — `OK`)**.