// Palette des graphiques : une couleur FIXE par catégorie de coût, pour
// qu'une même catégorie garde sa couleur d'un écran à l'autre.
export const COULEURS_CATEGORIES = {
  beton: '#2a78d6',
  acier: '#eb6834',
  coffrage: '#1baf7a',
  maconnerie: '#eda100',
  enduit: '#e87ba4',
  main_doeuvre: '#008300',
  autre: '#4a3aa7',
};

export const LIBELLES_CATEGORIES = {
  beton: 'Béton',
  acier: 'Acier',
  coffrage: 'Coffrage',
  maconnerie: 'Maçonnerie',
  enduit: 'Enduit',
  main_doeuvre: 'Postes saisis',
  autre: 'Autres',
};

// Couleurs de séries génériques (lots, courbes) -- ordre stable.
export const SERIES = ['#2a78d6', '#eb6834', '#1baf7a', '#eda100', '#e87ba4', '#008300', '#4a3aa7', '#7a6f63'];

export const couleurCategorie = (cle, i = 0) =>
  COULEURS_CATEGORIES[(cle || '').toLowerCase()] || SERIES[i % SERIES.length];

export const libelleCategorie = (cle) =>
  LIBELLES_CATEGORIES[(cle || '').toLowerCase()] || cle;

export const nf = (n, decimales = 0) =>
  n === null || n === undefined || Number.isNaN(Number(n))
    ? '—'
    : Number(n).toLocaleString('fr-FR', { maximumFractionDigits: decimales, minimumFractionDigits: 0 });

export const fcfa = (n) => (n === null || n === undefined ? '—' : `${nf(n)} FCFA`);

export const pct = (part, total) => (total > 0 ? Math.round((part / total) * 1000) / 10 : null);

export const LIBELLES_MOIS = ['janv.', 'févr.', 'mars', 'avr.', 'mai', 'juin', 'juil.', 'août', 'sept.', 'oct.', 'nov.', 'déc.'];
export const libelleMois = (iso) => {
  const [a, m] = (iso || '').split('-').map(Number);
  return a && m ? `${LIBELLES_MOIS[m - 1]} ${String(a).slice(2)}` : iso;
};

export const dateCourte = (d) =>
  d ? new Date(d).toLocaleDateString('fr-FR', { day: '2-digit', month: 'short', year: 'numeric' }) : '—';

export const dateHeure = (d) =>
  d ? new Date(d).toLocaleString('fr-FR', { day: '2-digit', month: 'short', hour: '2-digit', minute: '2-digit' }) : '—';
