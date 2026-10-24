// Uniquement les valeurs explicitement proposées ; une portée sans axe
// reste dans l'aperçu et ne permet pas de déduire X ou Y.
export function champsNlp(d) {
  if (!d) return {};
  const champs = {
    nombre_niveaux: 'nombreNiveaux', usage_batiment: 'typeUsage',
    portee_x_m: 'porteeX', portee_y_m: 'porteeY',
    hauteur_niveau_m: 'hauteurEtage', contrainte_sol_kn_m2: 'contrainteSol',
  };
  return Object.fromEntries(Object.entries(champs)
    .filter(([cle]) => d[cle] != null && String(d[cle]).trim() !== '')
    .map(([cle, champ]) => [champ, String(d[cle])]));
}
