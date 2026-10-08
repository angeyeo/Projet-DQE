import React from 'react';
import { AlertCircle, AlertTriangle, Info, RefreshCw } from 'lucide-react';

const NIVEAUX = {
  CRITIQUE: { icone: AlertCircle, classe: 'critique', libelle: 'Critique' },
  CALCUL_A_REFAIRE: { icone: RefreshCw, classe: 'attention', libelle: 'À recalculer' },
  ALERTE: { icone: AlertTriangle, classe: 'attention', libelle: 'Valeur inhabituelle' },
  ATTENTION: { icone: AlertTriangle, classe: 'attention', libelle: 'Attention' },
  INFORMATION: { icone: Info, classe: 'info', libelle: 'Information' },
};

// Alerte groupée : un signal, son message et la liste des éléments concernés.
export default function AlertCard({ niveau, message, elements = [], action }) {
  const cfg = NIVEAUX[niveau] || NIVEAUX.INFORMATION;
  const Icone = cfg.icone;
  return (
    <div className={`alert-card alert-card-${cfg.classe}`}>
      <Icone size={18} aria-hidden="true" className="alert-card-icone" />
      <div className="alert-card-corps">
        <div className="alert-card-titre">
          <span className="alert-card-niveau">{cfg.libelle}</span>
          {elements.length > 0 && <span className="texte-discret"> · {elements.length} élément(s)</span>}
        </div>
        <p>{message}</p>
        {elements.length > 0 && (
          <p className="alert-card-elements">{elements.slice(0, 12).join(', ')}{elements.length > 12 ? ` … (+${elements.length - 12})` : ''}</p>
        )}
      </div>
      {action && (
        <button type="button" className="btn btn-secondary btn-compact" onClick={action.onClick}>{action.libelle}</button>
      )}
    </div>
  );
}
