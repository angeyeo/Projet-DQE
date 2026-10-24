import React from 'react';
import { useEtatConsentementGemini } from './ConsentementGemini';

export default function AssistanceIADesactivee({ className = '', compact = false, label = "L'assistance IA est désactivée pour votre compte.", buttonLabel = "Activer l'IA" }) {
  const { assistanceDesactivee, activerConsentementGemini } = useEtatConsentementGemini();
  if (!assistanceDesactivee) return null;
  const texte = compact && label === "L'assistance IA est désactivée pour votre compte."
    ? 'Assistance IA désactivée'
    : label;

  return (
    <div className={`assistance-ia-desactivee${compact ? ' assistance-ia-desactivee-compact' : ''} ${className}`.trim()} role="status">
      <p>{texte}</p>
      <button type="button" className="btn btn-ia btn-compact" onClick={() => activerConsentementGemini()}>
        {buttonLabel}
      </button>
    </div>
  );
}
