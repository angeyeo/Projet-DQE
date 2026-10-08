import React from 'react';
import { dateHeure, fcfa } from './palette';

// Journal d'activité réel (EvenementProduit), événements consécutifs
// identiques déjà regroupés par le serveur (champ `nombre`).
export default function ActivityTimeline({ evenements = [], onOuvrirProjet, afficherProjet = true }) {
  if (!evenements.length) return <p className="texte-discret">Aucune activité journalisée pour l'instant.</p>;
  return (
    <ol className="timeline">
      {evenements.map((ev, i) => (
        <li key={`${ev.type}-${ev.date}-${i}`} className={`timeline-item timeline-${ev.type}`}>
          <span className="timeline-point" aria-hidden="true" />
          <div className="timeline-corps">
            <div>
              <strong>{ev.libelle}</strong>
              {ev.nombre > 1 && <span className="timeline-nombre"> ×{ev.nombre}</span>}
              {afficherProjet && ev.projet_nom && (
                onOuvrirProjet ? (
                  <> — <button type="button" className="lien" onClick={() => onOuvrirProjet(ev.projet_id, 'analyse')}>{ev.projet_nom}</button></>
                ) : <> — {ev.projet_nom}</>
              )}
            </div>
            <div className="timeline-meta">
              {dateHeure(ev.date)}{ev.nombre > 1 && ' (dernier)'}
              {ev.utilisateur && ` · ${ev.utilisateur}`}
              {ev.donnees?.total_general != null && ` · ${fcfa(ev.donnees.total_general)}`}
              {ev.donnees?.format && ` · ${ev.donnees.format.toUpperCase()}`}
            </div>
          </div>
        </li>
      ))}
    </ol>
  );
}
