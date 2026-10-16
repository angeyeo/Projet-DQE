import React from 'react';
import { nf, pct, SERIES } from './palette';

// Anneau de répartition + légende chiffrée (la légende porte l'information,
// la couleur seule ne suffit jamais).
export default function DonutChart({ items = [], centre, sousCentre, unite = 'FCFA' }) {
  const donnees = items.filter((i) => i.valeur > 0);
  const total = donnees.reduce((s, i) => s + i.valeur, 0);
  if (!total) return <p className="texte-discret">Aucune donnée à représenter.</p>;
  const R = 52;
  const C = 2 * Math.PI * R;
  let cumul = 0;
  return (
    <div className="donut">
      <svg viewBox="0 0 140 140" role="img" aria-label={`Répartition : ${donnees.map((d) => `${d.libelle} ${nf(pct(d.valeur, total), 1)} %`).join(', ')}`}>
        <circle cx="70" cy="70" r={R} fill="none" stroke="var(--core-border-subtle)" strokeWidth="18" />
        {donnees.map((d, i) => {
          const longueur = (d.valeur / total) * C;
          const el = (
            <circle
              key={d.cle || d.libelle}
              cx="70" cy="70" r={R} fill="none"
              stroke={d.couleur || SERIES[i % SERIES.length]}
              strokeWidth="18"
              strokeDasharray={`${longueur} ${C - longueur}`}
              strokeDashoffset={-cumul}
              transform="rotate(-90 70 70)"
            />
          );
          cumul += longueur;
          return el;
        })}
        {centre && <text x="70" y="68" textAnchor="middle" className="donut-centre">{centre}</text>}
        {sousCentre && <text x="70" y="86" textAnchor="middle" className="donut-sous-centre">{sousCentre}</text>}
      </svg>
      <ul className="donut-legende">
        {donnees.map((d, i) => (
          <li key={d.cle || d.libelle}>
            <span className="pastille" style={{ background: d.couleur || SERIES[i % SERIES.length] }} aria-hidden="true" />
            <span className="donut-legende-libelle">{d.libelle}</span>
            <span className="tabular">{nf(d.valeur)} {unite}</span>
            <span className="tabular texte-discret">{nf(pct(d.valeur, total), 1)} %</span>
          </li>
        ))}
      </ul>
    </div>
  );
}
