// Accrochage des positions de poteaux (issue #94) -- fonctions pures.
// Toutes les distances sont en mètres, dans le repère du plan.

export const PAS_GRILLE_M = [0.05, 0.1, 0.25, 0.5, 1];
export const DISTANCE_MIN_M = 0.3; // même règle que le serveur (doublon probable)

const arrondir3 = (v) => Math.round(v * 1000) / 1000;

export function accrocherGrille({ x, y }, pas) {
  return { x: arrondir3(Math.round(x / pas) * pas), y: arrondir3(Math.round(y / pas) * pas) };
}

// Aligne X et/ou Y sur ceux d'un poteau existant quand l'écart est inférieur
// à la tolérance (chaque axe séparément : on peut s'aligner sur la file d'un
// poteau et sur la rangée d'un autre). `ignorer` : index du poteau déplacé.
export function accrocherPoteaux({ x, y }, poteaux, tolerance, ignorer = -1) {
  let bx = x;
  let by = y;
  let ex = tolerance;
  let ey = tolerance;
  poteaux.forEach((p, i) => {
    if (i === ignorer) return;
    if (Math.abs(p.x - x) < ex) { ex = Math.abs(p.x - x); bx = p.x; }
    if (Math.abs(p.y - y) < ey) { ey = Math.abs(p.y - y); by = p.y; }
  });
  return { x: arrondir3(bx), y: arrondir3(by) };
}

export function accrocher(point, mode, { pas, poteaux, tolerance, ignorer }) {
  if (mode === 'grille') return accrocherGrille(point, pas);
  if (mode === 'poteaux') return accrocherPoteaux(point, poteaux, tolerance, ignorer);
  return { x: arrondir3(point.x), y: arrondir3(point.y) };
}

export function doublon(poteaux, x, y, ignorer = -1) {
  return poteaux.findIndex((p, i) => i !== ignorer && Math.hypot(p.x - x, p.y - y) < DISTANCE_MIN_M);
}

// Emprise commune du fond, des traits de structure et des poteaux (boucle :
// un fond de 40 000 traits dépasserait la limite d'arguments de Math.min).
export function emprise(segments, poteaux) {
  const e = { xmin: Infinity, ymin: Infinity, xmax: -Infinity, ymax: -Infinity };
  const etendre = (x, y) => {
    if (x < e.xmin) e.xmin = x;
    if (x > e.xmax) e.xmax = x;
    if (y < e.ymin) e.ymin = y;
    if (y > e.ymax) e.ymax = y;
  };
  segments.forEach(([x1, y1, x2, y2]) => { etendre(x1, y1); etendre(x2, y2); });
  poteaux.forEach((p) => etendre(p.x, p.y));
  if (!Number.isFinite(e.xmin)) return { xmin: 0, ymin: 0, xmax: 10, ymax: 10 };
  if (e.xmax - e.xmin < 1) e.xmax = e.xmin + 1;
  if (e.ymax - e.ymin < 1) e.ymax = e.ymin + 1;
  return e;
}
