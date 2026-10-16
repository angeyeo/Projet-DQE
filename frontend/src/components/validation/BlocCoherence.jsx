import React, { forwardRef, useCallback, useEffect, useImperativeHandle, useState } from 'react';
import { Activity, Info, Loader2, RefreshCw, Sparkles } from 'lucide-react';
import { dqeService } from '../../api/dqeService';
import Alerte from '../ui/Alerte';

const STATUTS_AVEC_EXPLICATION_IA = ['CRITIQUE', 'ATTENTION', 'INFORMATION'];

const STATUTS = {
  CRITIQUE: { libelle: 'Critique', classe: 'critique' },
  ATTENTION: { libelle: 'Attention', classe: 'attention' },
  INFORMATION: { libelle: 'Information', classe: 'info' },
  AUCUN_SIGNAL: { libelle: 'Aucun signal', classe: 'ok' },
  CALCUL_A_VALIDER: { libelle: 'À valider', classe: 'attention' },
  CALCUL_A_REFAIRE: { libelle: 'À recalculer', classe: 'info' },
  CALCUL_NON_DISPONIBLE: { libelle: 'Sans résultat', classe: 'neutre' },
};

const RESUME = [
  ['critiques', 'Critiques', 'critique'],
  ['attentions', 'Attentions', 'attention'],
  ['informations', 'Informations', 'info'],
  ['aucun_signal', 'Aucun signal', 'ok'],
  ['calculs_a_valider', 'À valider', 'attention'],
  ['calculs_a_refaire', 'À recalculer', 'info'],
  ['calculs_non_disponibles', 'Sans résultat', 'neutre'],
];

const SOURCES_IA = { GEMINI: 'Source : Gemini', MOCK: 'SIMULATION (non IA)' };

// Contrôle de cohérence DÉTERMINISTE (serveur), plus explication IA à la
// demande. L'IA explique un signal existant ; elle ne calcule rien et ne
// modifie aucune valeur. `ref.recharger()` relance l'analyse (après une
// validation ou un déverrouillage).
const BlocCoherence = forwardRef(function BlocCoherence({ projetId }, ref) {
  const [donnees, setDonnees] = useState(null);
  const [chargement, setChargement] = useState(false);
  const [erreur, setErreur] = useState(null);
  const [tousVisibles, setTousVisibles] = useState(false);
  const [explications, setExplications] = useState({});

  const recharger = useCallback(async () => {
    if (!projetId) return;
    setChargement(true);
    setErreur(null);
    try {
      setDonnees(await dqeService.analyserCoherenceProjet(projetId));
    } catch (err) {
      setErreur(err.message);
    } finally {
      setChargement(false);
    }
  }, [projetId]);

  useImperativeHandle(ref, () => ({ recharger }), [recharger]);
  useEffect(() => { recharger(); }, [recharger]);

  const expliquer = async (elementId) => {
    setExplications((p) => ({ ...p, [elementId]: { chargement: true } }));
    try {
      const res = await dqeService.expliquerCoherenceElement(elementId);
      setExplications((p) => ({ ...p, [elementId]: { res } }));
    } catch (err) {
      setExplications((p) => ({ ...p, [elementId]: { erreur: err.message } }));
    }
  };

  const elements = donnees?.elements || [];
  const sansSignal = elements.filter((e) => e.statut_analyse === 'AUCUN_SIGNAL').length;
  const visibles = tousVisibles ? elements : elements.filter((e) => e.statut_analyse !== 'AUCUN_SIGNAL');

  return (
    <section className="bloc-coherence" aria-labelledby="titre-coherence">
      <div className="bloc-entete">
        <div className="bloc-titre">
          <Activity size={22} color="var(--accent)" aria-hidden="true" />
          <div>
            <h3 id="titre-coherence">Contrôle de cohérence structurelle</h3>
            <p className="texte-discret">Contrôles déterministes sur les résultats du moteur (aucune IA dans le diagnostic).</p>
          </div>
        </div>
        <button type="button" className="btn btn-secondary btn-compact" disabled={chargement} onClick={recharger}>
          {chargement ? <Loader2 size={16} className="spin" /> : <RefreshCw size={16} />}
          <span>{chargement ? 'Analyse…' : 'Relancer'}</span>
        </button>
      </div>

      {erreur && <Alerte type="erreur" action={{ libelle: 'Réessayer', onClick: recharger }}>Analyse de cohérence indisponible : {erreur}</Alerte>}

      {donnees?.resume && (
        <div className="resume-coherence">
          {RESUME.map(([cle, libelle, classe]) => (
            <div key={cle} className={`resume-case ton-${classe} ${donnees.resume[cle] ? '' : 'resume-vide'}`}>
              <span className="tabular">{donnees.resume[cle] ?? 0}</span>
              <span>{libelle}</span>
            </div>
          ))}
        </div>
      )}

      {donnees && elements.length === 0 && <p className="texte-discret">Aucun élément à analyser.</p>}
      {donnees && elements.length > 0 && visibles.length === 0 && (
        <Alerte type="succes">Aucun signal de cohérence détecté parmi les contrôles disponibles ({sansSignal} élément(s)).</Alerte>
      )}

      <div className="liste-coherence">
        {visibles.map((el) => {
          const cfg = STATUTS[el.statut_analyse] || STATUTS.CALCUL_NON_DISPONIBLE;
          const expl = explications[el.element_id];
          return (
            <article key={el.element_id} className={`carte-coherence bord-${cfg.classe}`}>
              <div className="carte-coherence-entete">
                <strong>{el.identifiant || `Élément #${el.element_id}`}</strong>
                <span className="texte-discret">{(el.type_element || '').replace('_', ' ')}</span>
                <span className={`statut-pastille ton-${cfg.classe}`}>{cfg.libelle}</span>
              </div>
              {el.message_local && <p className="texte-discret">{el.message_local}</p>}
              {el.signaux?.map((sig, i) => (
                <div key={i} className={`signal bord-${(STATUTS[sig.categorie] || STATUTS.INFORMATION).classe}`}>
                  <div className="signal-entete"><code>{sig.code}</code><span>{sig.categorie}</span></div>
                  <p>{sig.message_local}</p>
                  {(sig.valeur_mesuree != null || sig.valeur_limite != null) && (
                    <p className="signal-valeurs tabular">
                      {sig.valeur_mesuree != null && <span>Mesuré : {sig.valeur_mesuree} {sig.unite || ''}</span>}
                      {sig.valeur_limite != null && <span>Limite : {sig.valeur_limite} {sig.unite || ''}</span>}
                    </p>
                  )}
                </div>
              ))}
              {el.validation_humaine_requise && (
                <p className="note-validation"><Info size={14} aria-hidden="true" /> Vérification humaine par l'ingénieur structure requise.</p>
              )}
              {STATUTS_AVEC_EXPLICATION_IA.includes(el.statut_analyse) && (
                <div className="explication-ia">
                  {!expl?.res && (
                    <button type="button" className="btn btn-ia btn-compact" disabled={expl?.chargement} onClick={() => expliquer(el.element_id)}>
                      {expl?.chargement ? <Loader2 size={14} className="spin" /> : <Sparkles size={14} />}
                      <span>{expl?.chargement ? 'Explication…' : expl?.erreur ? 'Réessayer' : "Expliquer avec l'IA"}</span>
                    </button>
                  )}
                  {expl?.erreur && <p className="texte-erreur">Explication IA indisponible : {expl.erreur}</p>}
                  {expl?.res && (
                    <div className="explication-ia-corps">
                      <div className="explication-ia-entete">
                        <span><Sparkles size={14} aria-hidden="true" /> RECOMMANDATION IA — n'est pas une donnée calculée</span>
                        {SOURCES_IA[expl.res.source_explication] && <span className="type-donnee">{SOURCES_IA[expl.res.source_explication]}</span>}
                      </div>
                      <p>{expl.res.explication_ia || "L'explication IA n'est pas disponible ; le contrôle ci-dessus reste valable."}</p>
                      {expl.res.validation_humaine_requise && (
                        <p className="note-validation"><Info size={14} aria-hidden="true" /> {expl.res.message_validation || 'Vérification humaine requise.'}</p>
                      )}
                    </div>
                  )}
                </div>
              )}
            </article>
          );
        })}
      </div>

      {sansSignal > 0 && (
        <button type="button" className="lien" onClick={() => setTousVisibles((v) => !v)}>
          {tousVisibles ? `Masquer les ${sansSignal} élément(s) sans signal` : `Afficher aussi les ${sansSignal} élément(s) sans signal`}
        </button>
      )}
    </section>
  );
});

export default BlocCoherence;
