\# Module Backend \& Sécurité - Sprint 2



\## 📌 Description

Ce sprint se concentre sur le renforcement de la sécurité du backend, la gestion multi-tenant des entreprises, l'authentification robuste par JWT et l'isolation rigoureuse des données par profil utilisateur.



\## 🛠️ Fonctionnalités clés \& Correctifs

\- \*\*Sécurité Multi-Cabinet / Entreprise\*\* : Filtrage dynamique des projets et des données selon le profil et l'entreprise rattachée à l'utilisateur.

\- \*\*Gestion des Superusers\*\* : Accès global prioritaire pour l'administration et les tests techniques.

\- \*\*Authentification JWT\*\* : Sécurisation complète des endpoints de l'API REST.

\- \*\*Tests Automatisés\*\* : Validation de la non-régression et des permissions (267+ tests unitaires et fonctionnels au vert).



\## 🚀 Endpoints et Services Principaux

\- `/api/token/` : Authentification et obtention des jetons JWT.

\- `/api/projets/` : Gestion des projets sécurisée par entreprise et créateur.

