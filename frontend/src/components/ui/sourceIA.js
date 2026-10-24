const LIBELLES = {
  GEMINI: 'Gemini',
  MOCK: 'MOCK (simulation)',
  FALLBACK_LOCAL: 'Traitement local (sans IA)',
  LOCAL: 'Traitement local (sans IA)',
};

export function etiquetteSourceIA(source) {
  const libelle = LIBELLES[source];
  return libelle ? `Source : ${libelle}` : 'Source inconnue';
}

export function classeSourceIA(source) {
  if (source === 'GEMINI') return 'gemini';
  if (source === 'MOCK') return 'mock';
  if (source === 'FALLBACK_LOCAL' || source === 'LOCAL') return 'locale';
  return 'inconnue';
}
