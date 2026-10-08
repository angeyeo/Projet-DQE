import React, { useRef } from 'react';
import { ArrowLeft, ArrowRight, ShieldAlert, ShieldCheck } from 'lucide-react';
import BlocCoherence from './validation/BlocCoherence';
import ListeElements from './validation/ListeElements';
import PostesComplementaires from './validation/PostesComplementaires';

// Validation ingénieur. Toute action (valider, déverrouiller, ajouter un
// poste) passe par le serveur, puis le projet est relu : l'écran n'affiche
// jamais un état local non confirmé.
export default function Step3_ValidationLock({
  sections,
  projetId,
  postes,
  onBasculerVerrou,
  onBasculerTout,
  validation,
  onAjouterPoste,
  onSupprimerPoste,
  erreurPoste,
  onBack,
  onNext,
}) {
  const coherence = useRef(null);
  const elements = Object.values(sections).flat();
  const valides = elements.filter((e) => e.locked).length;
  const complet = elements.length > 0 && valides === elements.length;

  return (
    <div className="glass-panel etape">
      <header className="etape-entete">
        <div>
          <p className="surtitre">Étape 3</p>
          <h2>Validation ingénieur</h2>
          <p className="texte-discret">
            Seuls les éléments validés entrent au DQE. Un élément déverrouillé perd son résultat validé jusqu'à sa revalidation.
          </p>
        </div>
      </header>

      <div className={`bandeau-etat ${complet ? 'ton-ok' : 'ton-attention'}`} role="status">
        {complet ? <ShieldCheck size={24} aria-hidden="true" /> : <ShieldAlert size={24} aria-hidden="true" />}
        <div>
          <strong>{complet ? 'Projet entièrement validé' : 'Validation en cours'}</strong>
          <p>{complet ? 'Le DQE peut être généré.' : `${valides} élément(s) validé(s) sur ${elements.length}.`}</p>
        </div>
      </div>

      <BlocCoherence ref={coherence} projetId={projetId} />

      <ListeElements
        elements={elements}
        onBasculerVerrou={onBasculerVerrou}
        onBasculerTout={onBasculerTout}
        validation={validation}
        onApresChangement={() => coherence.current?.recharger()}
      />

      <PostesComplementaires postes={postes} onAjouter={onAjouterPoste} onSupprimer={onSupprimerPoste} erreur={erreurPoste} />

      <div className="navigation-etapes">
        <button type="button" className="btn btn-secondary" onClick={onBack}><ArrowLeft size={18} /> <span>Dalles</span></button>
        <button type="button" className="btn btn-primary" onClick={onNext}><span>Plan de fondation</span> <ArrowRight size={18} /></button>
      </div>
    </div>
  );
}