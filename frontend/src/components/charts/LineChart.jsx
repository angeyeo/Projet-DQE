import React from 'react';
import { libelleMois, nf, SERIES } from './palette';

const L = 960;
const H = 220;
const M = { g: 36, d: 12, h: 14, b: 28 };

// Séries mensuelles {mois, valeur}. valeur === null => mois ANTÉRIEUR au
// journal d'événements : zone hachurée « non mesuré », aucun point tracé
// (jamais un zéro inventé).
export default function LineChart({ series = [] }) {
  const mois = series[0]?.points?.map((p) => p.mois) || [];
  if (!mois.length) return <p className="texte-discret">Aucune donnée.</p>;
  const valeurs = series.flatMap((s) => s.points.map((p) => p.valeur)).filter((v) => v !== null);
  const max = Math.max(1, ...valeurs);
  const n = mois.length;
  const x = (i) => M.g + (n === 1 ? 0 : (i * (L - M.g - M.d)) / (n - 1));
  const y = (v) => H - M.b - (v / max) * (H - M.h - M.b);
  const nonMesures = series[0].points.filter((p) => p.valeur === null).length;
  const largeurHachure = nonMesures === n ? L - M.g - M.d : x(nonMesures) - M.g;
  const graduations = [0, Math.round(max / 2), max];

  return (
    <div className="line-chart">
      <ul className="line-legende">
        {series.map((s, i) => (
          <li key={s.cle}>
            <span className="pastille" style={{ background: s.couleur || SERIES[i] }} aria-hidden="true" />
            {s.libelle}
          </li>
        ))}
        {nonMesures > 0 && (
          <li><span className="pastille pastille-hachure" aria-hidden="true" />Non mesuré (avant le journal)</li>
        )}
      </ul>
      <svg viewBox={`0 0 ${L} ${H}`} role="img" aria-label="Activité mensuelle — le détail chiffré est disponible sous le graphique">
        <defs>
          <pattern id="hachures" width="8" height="8" patternUnits="userSpaceOnUse" patternTransform="rotate(45)">
            <line x1="0" y1="0" x2="0" y2="8" stroke="var(--ink-300)" strokeWidth="2" opacity="0.5" />
          </pattern>
        </defs>
        {nonMesures > 0 && (
          <rect x={M.g} y={M.h} width={Math.max(largeurHachure, 0)} height={H - M.h - M.b} fill="url(#hachures)" />
        )}
        {graduations.map((g) => (
          <g key={g}>
            <line x1={M.g} x2={L - M.d} y1={y(g)} y2={y(g)} stroke="var(--core-border)" strokeDasharray="3 4" />
            <text x={M.g - 6} y={y(g) + 4} textAnchor="end" className="axe">{g}</text>
          </g>
        ))}
        {mois.map((m, i) => (
          <text key={m} x={x(i)} y={H - 8} textAnchor="middle" className="axe">{libelleMois(m)}</text>
        ))}
        {series.map((s, si) => {
          const pts = s.points.map((p, i) => (p.valeur === null ? null : [x(i), y(p.valeur)])).filter(Boolean);
          if (!pts.length) return null;
          const couleur = s.couleur || SERIES[si];
          return (
            <g key={s.cle}>
              <polyline points={pts.map((p) => p.join(',')).join(' ')} fill="none" stroke={couleur} strokeWidth="2.5" strokeLinejoin="round" />
              {pts.map(([px, py], i) => <circle key={i} cx={px} cy={py} r="3.5" fill={couleur} />)}
            </g>
          );
        })}
      </svg>
      <details className="line-details">
        <summary>Voir les valeurs</summary>
        <div className="table-scroll">
          <table className="custom-table">
            <thead>
              <tr><th>Mois</th>{series.map((s) => <th key={s.cle}>{s.libelle}</th>)}</tr>
            </thead>
            <tbody>
              {mois.map((m, i) => (
                <tr key={m}>
                  <td>{libelleMois(m)}</td>
                  {series.map((s) => (
                    <td key={s.cle} className="tabular">
                      {s.points[i].valeur === null ? <span className="texte-discret">non mesuré</span> : nf(s.points[i].valeur)}
                    </td>
                  ))}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </details>
    </div>
  );
}
