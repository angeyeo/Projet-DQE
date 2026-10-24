import React, { createContext, useCallback, useContext, useEffect, useRef, useState } from 'react';

const ConsentementContext = createContext(null);

export function ConsentementGeminiProvider({ children, consentement, onEnregistrer }) {
  const [ouvert, setOuvert] = useState(false);
  const resolveRef = useRef(null);
  const dialogRef = useRef(null);
  const [enregistrement, setEnregistrement] = useState(false);
  const [erreur, setErreur] = useState(null);

  const fermer = useCallback((accord) => {
    setOuvert(false);
    const resolve = resolveRef.current;
    resolveRef.current = null;
    if (resolve) resolve(accord);
  }, []);

  const ouvrirConsentement = useCallback(() => {
    if (ouvert) return Promise.resolve(false);
    setErreur(null);
    setOuvert(true);
    return new Promise((resolve) => { resolveRef.current = resolve; });
  }, [ouvert]);

  const demanderConsentementGemini = useCallback(() => {
    if (consentement?.consentement_ia_valide) return Promise.resolve(true);
    if (consentement?.consentement_ia === 'refuse') return Promise.resolve(false);
    return ouvrirConsentement();
  }, [consentement, ouvrirConsentement]);

  const activerConsentementGemini = useCallback(() => ouvrirConsentement(), [ouvrirConsentement]);
  const assistanceDesactivee = consentement?.consentement_ia === 'refuse'
    && !consentement?.consentement_ia_valide;

  const choisir = async (decision) => {
    setEnregistrement(true);
    setErreur(null);
    try {
      const resultat = await onEnregistrer(decision);
      if (resolveRef.current) {
        const resolve = resolveRef.current;
        resolveRef.current = null;
        setOuvert(false);
        resolve(decision === 'accepte' && resultat?.consentement_ia_valide !== false);
      }
    } catch (err) {
      setErreur(err.message || "Impossible d'enregistrer votre choix.");
    } finally {
      setEnregistrement(false);
    }
  };

  useEffect(() => {
    if (!ouvert) return undefined;
    dialogRef.current?.querySelector('button')?.focus();
    const onKeyDown = (event) => {
      if (event.key === 'Escape') {
        event.preventDefault();
        fermer(false);
        return;
      }
      if (event.key !== 'Tab') return;
      const boutons = [...(dialogRef.current?.querySelectorAll('button') || [])];
      if (!boutons.length) return;
      const index = boutons.indexOf(document.activeElement);
      const prochain = event.shiftKey
        ? boutons[(index - 1 + boutons.length) % boutons.length]
        : boutons[(index + 1) % boutons.length];
      event.preventDefault();
      prochain.focus();
    };
    document.addEventListener('keydown', onKeyDown);
    return () => document.removeEventListener('keydown', onKeyDown);
  }, [fermer, ouvert]);

  useEffect(() => () => {
    const resolve = resolveRef.current;
    resolveRef.current = null;
    if (resolve) resolve(false);
  }, []);

  return (
    <ConsentementContext.Provider value={{ demanderConsentementGemini, activerConsentementGemini, assistanceDesactivee }}>
      {children}
      {ouvert && (
        <div className="consentement-gemini-overlay" role="presentation" onMouseDown={(event) => {
          if (event.target === event.currentTarget) fermer(false);
        }}>
          <section className="consentement-gemini-dialog" role="dialog" aria-modal="true" aria-labelledby="consentement-gemini-titre" ref={dialogRef}>
            <h2 id="consentement-gemini-titre">✨ Besoin d’un coup de pouce ?</h2>
            <p>Avec votre accord, l’assistance IA de DQE s’appuie sur Google pour analyser les éléments de votre demande (description, données techniques ou image de plan) et vous faire <strong>gagner du temps</strong>.</p>
            <p className="consentement-gemini-controle">Vous gardez le contrôle : les résultats vous sont proposés, et vous les vérifiez avant de les utiliser.</p>
            <div className="consentement-gemini-actions">
              {erreur && <p className="consentement-gemini-erreur" role="alert">{erreur}</p>}
              <button type="button" className="btn btn-primary" disabled={enregistrement} onClick={() => choisir('accepte')}>Oui, avec plaisir</button>
              <button type="button" className="btn btn-secondary" disabled={enregistrement} onClick={() => choisir('refuse')}>Non merci</button>
            </div>
            <span className="consentement-gemini-en-savoir-plus">En savoir plus sur le traitement de vos données</span>
          </section>
        </div>
      )}
    </ConsentementContext.Provider>
  );
}

export function useConsentementGemini() {
  const context = useContext(ConsentementContext);
  if (!context) throw new Error('useConsentementGemini doit être utilisé dans ConsentementGeminiProvider');
  return context.demanderConsentementGemini;
}

export function useEtatConsentementGemini() {
  const context = useContext(ConsentementContext);
  if (!context) throw new Error('useEtatConsentementGemini doit être utilisé dans ConsentementGeminiProvider');
  return {
    assistanceDesactivee: context.assistanceDesactivee,
    activerConsentementGemini: context.activerConsentementGemini,
  };
}
