# Mise à jour du 14/10/2026

Ce zip est ton projet du 14/10/2026 au matin, avec toutes les modifications
depuis la fiche d'approvisionnement. Ta base `db.sqlite3`, ton `.env`, ton
`venv`, tes `media` et ton dossier `.git` n'ont pas été touchés.

## Ce qui change

1. **Charge des murs** dans la descente de charges : poids des murs saisi
   (3,3 kN/m² proposé, valeur de l'ingénieur), murs comptés seulement là où
   ils existent (plan des murs, RDC et étages), baies déduites.
2. **Poutres courtes** : section minimale 20 × 25 cm, vérification à
   l'effort tranchant ; poteaux à moins de 1 m désormais calculés.
3. **Import DXF** (AutoCAD, ArchiCAD) : poteaux et murs lus, plans côte à
   côte, poteaux doublés, murs proposés pour le plan des murs. Les formats
   .pln, .pdf et .dwg sont refusés avec un conseil d'export.
4. **Contrôles** : poutres de plus de 8 m signalées, chevauchement des
   semelles vérifié sur leurs positions réelles.
5. Fichier `projets/services/trame_service.py` : tu avais une ancienne
   version (antérieure à la toiture en charpente), remplacée.
6. Supprimés (inutilisés) : `DashboardView.jsx`, `FormCouchesCharge.jsx`,
   `Header.jsx`.

## Contenu de ce zip

Seulement le code à jour. Ne sont PAS dans le zip (inchangés, déjà chez
toi) : `venv`, `frontend/node_modules`, `media`, `staticfiles`, `.git`,
`.env` et `db.sqlite3` -- ta base n'est donc jamais écrasée.

## Installation

1. Ferme `runserver` et `npm run dev`.
2. Décompresse le zip et copie le contenu de son dossier `Projet-DQE` dans
   ton dossier `Projet-DQE` en remplaçant les fichiers existants.
3. Supprime ces 3 fichiers devenus inutiles (un zip ne peut pas supprimer) :
   `frontend/src/components/DashboardView.jsx`,
   `frontend/src/components/FormCouchesCharge.jsx`,
   `frontend/src/components/Header.jsx`.
4. Puis :

```
python manage.py migrate      # applique 0024, 0025, 0026 (ajouts de champs, aucune suppression)
python manage.py test         # 561 tests OK attendus
python manage.py runserver
```

Côté frontend : `npm run dev` (aucune nouvelle dépendance).

Vérifié avant envoi sur une copie : migrations appliquées sur une copie de
ta base (tes projets « yy » et « test » conservés), 561 tests OK, build
du frontend OK.
