import { useCallback, useEffect, useRef, useState } from 'react';
import { dqeService, elementsParType } from '../api/dqeService';

// Seul l'IDENTIFIANT du projet courant est conservé localement : le
// contenu (paramètres, éléments, postes) est toujours relu depuis le
// backend. Un F5 ne fait donc plus perdre le projet, et l'écran ne peut
// jamais afficher une copie locale périmée.
const CLE_PROJET = 'dqe_projet_courant';

const lireId = () => {
  try {
    const v = localStorage.getItem(CLE_PROJET);
    return v ? Number(v) : null;
  } catch {
    return null;
  }
};
const ecrireId = (id) => {
  try {
    if (id) localStorage.setItem(CLE_PROJET, String(id));
    else localStorage.removeItem(CLE_PROJET);
  } catch { /* stockage indisponible : le projet ne survivra pas au F5 */ }
};

const SECTIONS_VIDES = { poteaux: [], poutres: [], semelles: [], dalles: [], autres: [] };

export default function useProjetCourant(actif) {
  const [projetId, setProjetId] = useState(lireId);
  const idRef = useRef(projetId);
  const [projet, setProjet] = useState(null);
  // Vrai dès le départ si un projet est mémorisé : évite de monter l'écran
  // d'étape une première fois sans projet, puis une seconde après chargement.
  const [chargement, setChargement] = useState(() => !!lireId());
  const [erreur, setErreur] = useState(null);

  const charger = useCallback(async (id) => {
    if (!id) {
      setProjet(null);
      return null;
    }
    setChargement(true);
    setErreur(null);
    try {
      const data = await dqeService.getProjet(id);
      setProjet(data);
      return data;
    } catch (err) {
      if (err.status === 404) {
        // Projet supprimé ou d'un autre cabinet : on l'oublie explicitement.
        ecrireId(null);
        idRef.current = null;
        setProjetId(null);
        setProjet(null);
        setErreur("Le projet mémorisé n'existe plus ou n'est pas accessible avec ce compte.");
      } else {
        setErreur(`Impossible de charger le projet : ${err.message}`);
      }
      return null;
    } finally {
      setChargement(false);
    }
  }, []);

  // Au montage (ou à la reconnexion) : relecture du projet mémorisé.
  useEffect(() => {
    if (actif && idRef.current) charger(idRef.current);
  }, [actif, charger]);

  // Ouvre un projet ET le charge immédiatement (promesse résolue avec le projet).
  const ouvrir = useCallback((id) => {
    ecrireId(id);
    idRef.current = id;
    setProjetId(id);
    if (id !== projet?.id) setProjet(null);
    return charger(id);
  }, [charger, projet?.id]);

  const fermer = useCallback(() => {
    ecrireId(null);
    idRef.current = null;
    setProjetId(null);
    setProjet(null);
    setErreur(null);
  }, []);

  // Relit TOUJOURS l'identifiant courant (ref), même juste après ouvrir().
  const recharger = useCallback(() => charger(idRef.current), [charger]);

  const sections = projet ? elementsParType(projet.elements) : SECTIONS_VIDES;

  return {
    projetId,
    projet,
    sections,
    postes: projet?.postes_complementaires || [],
    chargement,
    erreur,
    ouvrir,
    fermer,
    recharger,
  };
}
