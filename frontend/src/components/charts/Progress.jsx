import React from 'react';

export default function Progress({ valeur, total, libelle, couleur = 'var(--status-ok)' }) {
  const taux = total > 0 ? Math.min(100, Math.round((valeur / total) * 100)) : 0;
  return (
    <div className="progress">
      {libelle && (
        <div className="progress-entete">
          <span>{libelle}</span>
          <span className="tabular">{valeur}/{total} · {taux} %</span>
        </div>
      )}
      <div
        className="progress-piste"
        role="progressbar"
        aria-valuemin={0}
        aria-valuemax={total}
        aria-valuenow={valeur}
        aria-label={libelle}
      >
        <div className="progress-barre" style={{ width: `${taux}%`, background: couleur }} />
      </div>
    </div>
  );
}
