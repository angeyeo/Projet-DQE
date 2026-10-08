import React from 'react';

// Indicateur chiffré. `valeur` null => « — » + `vide` explique pourquoi
// (jamais un 0 inventé). `type` précise la nature de la donnée.
export default function KPI({ libelle, valeur, unite, detail, vide, icone: Icone, ton = 'neutre', type }) {
  const absent = valeur === null || valeur === undefined;
  return (
    <div className={`kpi kpi-${ton}`}>
      <div className="kpi-entete">
        {Icone && <Icone size={16} aria-hidden="true" />}
        <span>{libelle}</span>
        {type && <span className={`type-donnee type-${type}`}>{type}</span>}
      </div>
      <div className="kpi-valeur tabular">
        {absent ? '—' : valeur}
        {!absent && unite && <span className="kpi-unite"> {unite}</span>}
      </div>
      {(absent ? vide : detail) && <div className="kpi-detail">{absent ? vide : detail}</div>}
    </div>
  );
}
