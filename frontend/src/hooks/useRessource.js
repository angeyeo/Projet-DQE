import { useCallback, useEffect, useRef, useState } from 'react';

// Chargement d'une ressource API avec états explicites (chargement /
// erreur / données). Aucune donnée de remplacement en cas d'échec :
// `data` reste null et `erreur` porte le message à afficher.
export default function useRessource(chargeur, deps = [], { actif = true } = {}) {
  const [data, setData] = useState(null);
  const [erreur, setErreur] = useState(null);
  const [detail, setDetail] = useState(null); // err.data : détails structurés du serveur
  const [chargement, setChargement] = useState(actif);
  const requete = useRef(0);

  const recharger = useCallback(async () => {
    const id = ++requete.current;
    setChargement(true);
    setErreur(null);
    setDetail(null);
    try {
      const res = await chargeur();
      if (id === requete.current) setData(res);
    } catch (err) {
      if (id === requete.current) {
        setData(null);
        setErreur(err.message || 'Erreur inconnue.');
        setDetail(err.data || null);
      }
    } finally {
      if (id === requete.current) setChargement(false);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, deps);

  useEffect(() => {
    if (actif) recharger();
  }, [actif, recharger]);

  return { data, erreur, detail, chargement, recharger };
}
