import React from 'react';
import { nf, pct, SERIES } from './palette';

// Barres horizontales : libellé, barre proportionnelle, valeur et part.
// items : [{cle, libelle, valeur, couleur?}]
export default function BarChart({ items = [], unite = 'FCFA', total: totalImpose }) {
  const total = totalImpose ?? items.reduce((s, i) => s + (i.valeur || 0), 0);
  const max = Math.max(...items.map((i) => i.valeur || 0), 0);
  if (!items.length || max <= 0) return <p className="texte-discret">Aucune donnée à représenter.</p>;
  return (
    <ul className="bar-chart">
      {items.map((it, i) => (
        <li key={it.cle || it.libelle} className="bar-ligne">
          <span className="bar-libelle" title={it.libelle}>{it.libelle}</span>
          <span className="bar-piste" aria-hidden="true">
            <span
              className="bar-remplissage"
              style={{ width: `${(it.valeur / max) * 100}%`, background: it.couleur || SERIES[i % SERIES.length] }}
            />
          </span>
          <span className="bar-valeur tabular">
            {nf(it.valeur)} {unite}
            {total > 0 && <span className="bar-part"> · {nf(pct(it.valeur, total), 1)} %</span>}
          </span>
        </li>
      ))}
    </ul>
  );
}
