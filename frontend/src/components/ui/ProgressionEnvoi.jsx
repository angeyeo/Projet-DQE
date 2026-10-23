import React from 'react';

const mo = (o) => (o / 1048576).toLocaleString('fr-FR', { maximumFractionDigits: 1 });

// Avancement d'un dépôt de fichier (issue #90) : barre pendant l'envoi,
// puis barre indéterminée pendant la lecture par le serveur.
export default function ProgressionEnvoi({ progression, libelleLecture = 'Lecture du fichier par le serveur…' }) {
  if (!progression) return null;
  const envoi = progression.phase === 'envoi';
  const pct = envoi && progression.total ? Math.round((progression.envoye / progression.total) * 100) : null;
  return (
    <div className="progression-envoi" role="status" aria-live="polite">
      <div className="progression-envoi-barre" role="progressbar" aria-label={envoi ? 'Envoi du fichier' : libelleLecture}
        aria-valuemin={0} aria-valuemax={100} aria-valuenow={pct ?? undefined}>
        <span className={pct == null ? 'indeterminee' : ''} style={pct == null ? undefined : { width: `${pct}%` }} />
      </div>
      <p className="texte-discret tabular">
        {envoi
          ? `Envoi : ${pct ?? 0} % (${mo(progression.envoye)} / ${mo(progression.total)} Mo)`
          : libelleLecture}
      </p>
    </div>
  );
}
