import React from 'react';
import { AlertCircle, AlertTriangle, CheckCircle2, Info } from 'lucide-react';

const ICONES = { erreur: AlertCircle, attention: AlertTriangle, succes: CheckCircle2, info: Info };

// Message intégré à l'interface (remplace window.alert). `role="alert"`
// pour les erreurs : annoncé immédiatement par les lecteurs d'écran.
export default function Alerte({ type = 'info', titre, children, action, liste }) {
  const Icone = ICONES[type] || Info;
  return (
    <div className={`alerte alerte-${type}`} role={type === 'erreur' ? 'alert' : 'status'}>
      <Icone size={18} className="alerte-icone" aria-hidden="true" />
      <div className="alerte-corps">
        {titre && <strong className="alerte-titre">{titre}</strong>}
        {children && <div>{children}</div>}
        {liste && liste.length > 0 && (
          <ul className="alerte-liste">
            {liste.map((item, i) => <li key={i}>{item}</li>)}
          </ul>
        )}
      </div>
      {action && (
        <button type="button" className="btn btn-secondary alerte-action" onClick={action.onClick}>
          {action.libelle}
        </button>
      )}
    </div>
  );
}
