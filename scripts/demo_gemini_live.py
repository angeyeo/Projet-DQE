import os
import sys
import json

# Setup Django environment
sys.path.insert(0, '/home/zraysec/Documents/Developpement Personnel/Moi/Les projets en cours /architecture Ange/ProjetGit/projet-DQE')
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "backend.settings")

import django
django.setup()

from projets.services.assistant_ia.parser import structurer_description_projet
from projets.services.assistant_ia.explanations import expliquer_resultat_element

print("=================================================================")
print("          ASSISTANT IA INTERACTIF (TEST GEMINI LIVE)             ")
print("=================================================================")
print("Ce script interroge directement l'API Gemini réelle configurée.")
print("Tapez 'quitter' ou 'exit' pour arrêter le script.\n")

import time

try:
    while True:
        print("-" * 65)
        description = input("Entrez la description de votre projet BTP :\n> ")
        if not description or description.strip().lower() in ["quitter", "exit"]:
            print("\nArrêt du script interactif. À bientôt !")
            break

        description_clean = description.strip()
        print("\nPour cette analyse, DQE transmettra la description à Google Gemini.")
        print("Assurez-vous d'être autorisé à transmettre ces informations.")
        print("Le résultat est une proposition à vérifier par un ingénieur.")
        if input("Acceptez-vous cette transmission ? Tapez OUI pour continuer :\n> ").strip().upper() != "OUI":
            print("Transmission refusée : aucune donnée n'a été envoyée à Gemini.")
            continue
        print("\n[Gemini] Analyse en cours...")

        try:
            res = structurer_description_projet(description_clean)
            print("\n[Résultat] Données structurées extraites avec succès :")
            print(json.dumps(res, indent=2, ensure_ascii=False))
        except Exception as e:
            print(f"\n[Erreur] L'appel à l'API Gemini a échoué : {e}")

        # Petite pause pour éviter de dépasser le quota de requêtes par minute
        time.sleep(2)
        print()
except KeyboardInterrupt:
    print("\nArrêt du script interactif. À bientôt !")
