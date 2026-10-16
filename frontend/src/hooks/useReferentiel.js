import { dqeService } from '../api/dqeService';
import useRessource from './useRessource';

// Référentiel technique servi par le backend (usages et charges
// normatives, lots, types de postes à ratio et leur géométrie, clés de
// prix). Le frontend n'en garde AUCUNE copie codée en dur.
let cache = null;

export default function useReferentiel() {
  return useRessource(async () => {
    if (!cache) cache = await dqeService.getReferentiel();
    return cache;
  }, []);
}
