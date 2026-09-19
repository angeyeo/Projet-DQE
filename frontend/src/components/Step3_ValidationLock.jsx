import React, { useState, useEffect } from 'react';
import { Lock, Unlock, ShieldAlert, ArrowLeft, ArrowRight, Edit3, ShieldCheck, HardHat, Plus, Trash2, Sparkles, Loader2, AlertCircle, Activity, AlertTriangle, CheckCircle2, Info, RefreshCw } from 'lucide-react';
import { dqeService } from '../api/dqeService';

const STATUTS_AVEC_EXPLICATION_IA = ['CRITIQUE', 'ATTENTION', 'INFORMATION'];

const STATUT_ANALYSIS_MAP = {
  CRITIQUE: { label: 'CRITIQUE', color: 'var(--status-critical)', bg: 'var(--status-critical-soft)', border: 'var(--status-critical-soft)' },
  ATTENTION: { label: 'ATTENTION', color: 'var(--status-warn)', bg: 'var(--status-warn-soft)', border: 'var(--status-warn-soft)' },
  INFORMATION: { label: 'INFORMATION', color: 'var(--accent)', bg: 'var(--accent-soft)', border: 'var(--accent-soft-border)' },
  AUCUN_SIGNAL: { label: 'AUCUN SIGNAL', color: 'var(--status-ok)', bg: 'var(--status-ok-soft)', border: 'var(--status-ok-soft)' },
  CALCUL_A_VALIDER: { label: 'À VALIDER', color: 'var(--status-warn)', bg: 'var(--status-warn-soft)', border: 'var(--status-warn-soft)' },
  CALCUL_A_REFAIRE: { label: 'À RECALCULER', color: 'var(--accent)', bg: 'var(--accent-soft)', border: 'var(--accent-soft-border)' },
  CALCUL_NON_DISPONIBLE: { label: 'SANS RÉSULTAT', color: 'var(--ink-500)', bg: 'var(--status-neutral-soft)', border: 'var(--core-border)' },
};

export default function Step3_ValidationLock({
  sections,
  projetId,
  toggleLock,
  toggleLockAll,
  updateSection,
  validationError,
  validatingId,
  postesMainDoeuvre = [],
  onAddPosteMainDoeuvre,
  onRemovePosteMainDoeuvre,
  mainDoeuvreError,
  onBack,
  onNext,
}) {
  const { poteaux = [], poutres = [], semelles = [] } = sections || {};

  const activeProjetId = projetId || sections?.projetId;

  const [coherenceData, setCoherenceData] = useState(null);
  const [loadingCoherence, setLoadingCoherence] = useState(false);
  const [coherenceError, setCoherenceError] = useState(null);

  const fetchCoherence = async () => {
    if (!activeProjetId) return;
    setLoadingCoherence(true);
    setCoherenceError(null);
    try {
      const res = await dqeService.analyserCoherenceProjet(activeProjetId);
      setCoherenceData(res);
    } catch (err) {
      setCoherenceError(err.message || "Impossible de charger l'analyse de cohérence.");
    } finally {
      setLoadingCoherence(false);
    }
  };

  useEffect(() => {
    if (activeProjetId) {
      fetchCoherence();
    }
  }, [activeProjetId]);

  const handleToggleLock = async (id, category) => {
    const ok = await toggleLock(id, category);
    if (ok && activeProjetId) {
      await fetchCoherence();
    }
  };

  const handleToggleLockAll = async (targetState) => {
    const ok = await toggleLockAll(targetState);
    if (ok && activeProjetId) {
      await fetchCoherence();
    }
  };

  const [explicationsMap, setExplicationsMap] = useState({});
  const [loadingExplications, setLoadingExplications] = useState({});
  const [errorExplications, setErrorExplications] = useState({});

  const handleExpliquerElement = async (elementId) => {
    if (!elementId || loadingExplications[elementId]) return;

    setLoadingExplications((prev) => ({ ...prev, [elementId]: true }));
    setErrorExplications((prev) => ({ ...prev, [elementId]: null }));

    try {
      const res = await dqeService.expliquerCoherenceElement(elementId);
      setExplicationsMap((prev) => ({ ...prev, [elementId]: res }));
    } catch (err) {
      setErrorExplications((prev) => ({
        ...prev,
        [elementId]: "Impossible d'obtenir l'explication IA pour le moment."
      }));
    } finally {
      setLoadingExplications((prev) => ({ ...prev, [elementId]: false }));
    }
  };

  const [nouveauPoste, setNouveauPoste] = useState({
    lot: 'lot_02_gros_oeuvre_superstructure',
    mode: 'simple',
    designation: '',
    unite: 'forfait',
    quantite: '',
    prixUnitaire: '',
    typePoste: 'maconnerie_creuse',
    valeurGeometrie: '',
  });
  const [posteEnCours, setPosteEnCours] = useState(false);

  // Suggestion de poste par Assistant IA (POST /assistant/suggerer-poste/) --
  // n'existait ni côté service ni côté UI avant.
  const [posteIADescription, setPosteIADescription] = useState('');
  const [posteIALoading, setPosteIALoading] = useState(false);
  const [posteIAError, setPosteIAError] = useState(null);
  const [posteIAConfiance, setPosteIAConfiance] = useState(null);

  const handleSuggererPoste = async () => {
    if (!posteIADescription.trim()) return;
    setPosteIALoading(true);
    setPosteIAError(null);
    setPosteIAConfiance(null);
    try {
      const res = await dqeService.suggererPosteIA(posteIADescription.trim());
      setNouveauPoste((p) => ({
        ...p,
        mode: 'simple',
        designation: res.designation,
        unite: res.unite,
        lot: res.lot_suggere,
      }));
      setPosteIAConfiance(res.confiance);
    } catch (err) {
      setPosteIAError(err.message || "Impossible de suggérer ce poste.");
    } finally {
      setPosteIALoading(false);
    }
  };

  const handleAjouterPoste = async () => {
    if (nouveauPoste.mode === 'simple') {
      const quantite = parseFloat(nouveauPoste.quantite);
      const prixUnitaire = parseFloat(nouveauPoste.prixUnitaire);
      if (!nouveauPoste.designation.trim() || !quantite || quantite <= 0 || !prixUnitaire || prixUnitaire <= 0) {
        return;
      }
      setPosteEnCours(true);
      await onAddPosteMainDoeuvre({ ...nouveauPoste, quantite, prixUnitaire });
    } else {
      const valGeo = parseFloat(nouveauPoste.valeurGeometrie);
      if (!valGeo || valGeo <= 0) return;
      setPosteEnCours(true);
      await onAddPosteMainDoeuvre({
        lot: nouveauPoste.lot,
        mode: 'ratio',
        type_poste: nouveauPoste.typePoste,
        geometrie: (nouveauPoste.typePoste || '').includes('chainage') ? { longueur_ml: valGeo } : { surface_m2: valGeo },
      });
    }
    setPosteEnCours(false);
    setNouveauPoste((p) => ({ ...p, designation: '', quantite: '', prixUnitaire: '', valeurGeometrie: '' }));
  };

  const totalMainDoeuvre = postesMainDoeuvre.reduce(
    (sum, p) => sum + (p.montant ?? ((p.quantite || 0) * (p.prix_unitaire || 0))),
    0
  );

  const allElements = [
    ...poteaux.map(p => ({ ...p, category: 'Poteau' })),
    ...poutres.map(p => ({ ...p, category: 'Poutre' })),
    ...semelles.map(s => ({ ...s, category: 'Semelle' })),
  ];

  const lockedCount = allElements.filter(e => e.locked).length;
  const isAllLocked = allElements.length > 0 && lockedCount === allElements.length;

  return (
    <div className="glass-panel">
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '2rem' }}>
        <div>
          <h2 style={{ fontSize: '1.5rem', fontWeight: 700, marginBottom: '0.5rem' }}>
            Étape 3 : Validation Ingénieur & Système de Verrouillage
          </h2>
          <p style={{ color: 'var(--text-muted)', fontSize: '0.9rem' }}>
            Ajustez les dimensions si nécessaire et <strong>verrouillez les sections</strong> pour garantir l'intégrité avant génération du devis.
          </p>
        </div>

        {allElements.length > 0 && (
          <button
            className={`btn ${isAllLocked ? 'btn-warning' : 'btn-success'}`}
            onClick={() => handleToggleLockAll(!isAllLocked)}
          >
            {isAllLocked ? <Unlock size={18} /> : <Lock size={18} />}
            <span>{isAllLocked ? 'Déverrouiller Tout' : 'Verrouiller Toutes les Sections'}</span>
          </button>
        )}
      </div>

      {validationError && (
        <div style={{ padding: '1rem 1.25rem', borderRadius: '12px', background: 'var(--status-critical-soft)', border: '1px solid var(--status-critical-soft)', marginBottom: '1.5rem', display: 'flex', alignItems: 'flex-start', gap: '0.75rem' }}>
          <ShieldAlert size={20} color="var(--status-critical)" style={{ flexShrink: 0, marginTop: '0.1rem' }} />
          <span style={{ fontSize: '0.88rem', color: 'var(--status-critical)' }}>{validationError}</span>
        </div>
      )}

      {/* Banner de Sécurité */}
      <div
        style={{
          padding: '1.25rem 1.5rem',
          borderRadius: '14px',
          background: isAllLocked ? 'var(--status-ok-soft)' : 'var(--status-warn-soft)',
          border: `1px solid ${isAllLocked ? 'var(--status-ok-soft)' : 'var(--status-warn-soft)'}`,
          marginBottom: '2rem',
          display: 'flex',
          alignItems: 'center',
          gap: '1rem',
        }}
      >
        {isAllLocked ? (
          <ShieldCheck size={28} color="var(--status-ok)" />
        ) : (
          <ShieldAlert size={28} color="var(--status-warn)" />
        )}
        <div>
          <h4 style={{ fontSize: '1rem', fontWeight: 600, color: isAllLocked ? 'var(--status-ok)' : 'var(--status-warn)' }}>
            {isAllLocked ? 'Projet Intégralement Verrouillé & Validé' : 'Validation Ingénieur en cours'}
          </h4>
          <p style={{ fontSize: '0.85rem', color: 'var(--text-muted)' }}>
            {isAllLocked
              ? 'Toutes les sections sont verrouillées. Aucune modification non autorisée ne peut intervenir lors de l\'exportation du devis.'
              : `${lockedCount} sur ${allElements.length} sections verrouillées. Cliquez sur le cadenas à droite de chaque ligne pour la verrouiller.`}
          </p>
        </div>
      </div>

      {/* BLOC 2: Contrôle de Cohérence Structurelle (Assistant IA) */}
      <div style={{ padding: '1.5rem', borderRadius: '14px', background: 'var(--core-bg)', border: '1px solid var(--accent-soft-border)', marginBottom: '2.5rem' }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '1.25rem', flexWrap: 'wrap', gap: '0.75rem' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '0.75rem' }}>
            <Activity size={24} color="var(--accent)" />
            <div>
              <h3 style={{ fontSize: '1.15rem', fontWeight: 700, margin: 0, color: 'var(--ink-900)' }}>
                Contrôle de cohérence structurelle
              </h3>
              <p style={{ fontSize: '0.85rem', color: 'var(--ink-500)', margin: 0 }}>
                Analyse automatique des résultats validés
              </p>
            </div>
          </div>

          <button
            className="btn btn-secondary"
            style={{ padding: '0.45rem 0.85rem', fontSize: '0.85rem' }}
            disabled={loadingCoherence || !activeProjetId}
            onClick={fetchCoherence}
          >
            {loadingCoherence ? <Loader2 size={16} className="spin" /> : <RefreshCw size={16} />}
            <span>{loadingCoherence ? 'Analyse...' : 'Analyser la cohérence'}</span>
          </button>
        </div>

        {loadingCoherence && (
          <div style={{ padding: '1.5rem', textAlign: 'center', color: 'var(--accent)', display: 'flex', alignItems: 'center', justifyContent: 'center', gap: '0.6rem' }}>
            <Loader2 size={20} className="spin" />
            <span>Analyse de cohérence en cours...</span>
          </div>
        )}

        {coherenceError && (
          <div style={{ padding: '0.85rem 1rem', borderRadius: '10px', background: 'var(--status-critical-soft)', border: '1px solid var(--status-critical-soft)', color: 'var(--status-critical)', fontSize: '0.88rem', display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
            <AlertTriangle size={18} color="var(--status-critical)" />
            <span>Impossible de charger l'analyse de cohérence. {coherenceError}</span>
          </div>
        )}

        {coherenceData && !loadingCoherence && (
          <div>
            {/* Panneau de Synthèse (Resume) */}
            {coherenceData.resume && (
              <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(130px, 1fr))', gap: '0.75rem', marginBottom: '1.5rem' }}>
                <div style={{ padding: '0.75rem', borderRadius: '10px', background: 'var(--status-critical-soft)', border: '1px solid var(--status-critical-soft)', textAlign: 'center' }}>
                  <div style={{ fontSize: '1.4rem', fontWeight: 800, color: 'var(--status-critical)' }}>{coherenceData.resume.critiques || 0}</div>
                  <div style={{ fontSize: '0.78rem', color: 'var(--status-critical)', fontWeight: 600 }}>🔴 Critiques</div>
                </div>
                <div style={{ padding: '0.75rem', borderRadius: '10px', background: 'var(--status-warn-soft)', border: '1px solid var(--status-warn-soft)', textAlign: 'center' }}>
                  <div style={{ fontSize: '1.4rem', fontWeight: 800, color: 'var(--status-warn)' }}>{coherenceData.resume.attentions || 0}</div>
                  <div style={{ fontSize: '0.78rem', color: 'var(--status-warn)', fontWeight: 600 }}>🟠 Attentions</div>
                </div>
                <div style={{ padding: '0.75rem', borderRadius: '10px', background: 'var(--accent-soft)', border: '1px solid var(--accent-soft-border)', textAlign: 'center' }}>
                  <div style={{ fontSize: '1.4rem', fontWeight: 800, color: 'var(--accent)' }}>{coherenceData.resume.informations || 0}</div>
                  <div style={{ fontSize: '0.78rem', color: 'var(--accent)', fontWeight: 600 }}>🔵 Informations</div>
                </div>
                <div style={{ padding: '0.75rem', borderRadius: '10px', background: 'var(--status-ok-soft)', border: '1px solid var(--status-ok-soft)', textAlign: 'center' }}>
                  <div style={{ fontSize: '1.4rem', fontWeight: 800, color: 'var(--status-ok)' }}>{coherenceData.resume.aucun_signal || 0}</div>
                  <div style={{ fontSize: '0.78rem', color: 'var(--status-ok)', fontWeight: 600 }}>🟢 Aucun signal</div>
                </div>
                <div style={{ padding: '0.75rem', borderRadius: '10px', background: 'var(--status-warn-soft)', border: '1px solid var(--status-warn-soft)', textAlign: 'center' }}>
                  <div style={{ fontSize: '1.4rem', fontWeight: 800, color: 'var(--status-warn)' }}>{coherenceData.resume.calculs_a_valider || 0}</div>
                  <div style={{ fontSize: '0.78rem', color: 'var(--status-warn)', fontWeight: 600 }}>🟡 À valider</div>
                </div>
                <div style={{ padding: '0.75rem', borderRadius: '10px', background: 'var(--accent-soft)', border: '1px solid var(--accent-soft-border)', textAlign: 'center' }}>
                  <div style={{ fontSize: '1.4rem', fontWeight: 800, color: 'var(--accent)' }}>{coherenceData.resume.calculs_a_refaire || 0}</div>
                  <div style={{ fontSize: '0.78rem', color: 'var(--status-warn-soft)', fontWeight: 600 }}>🟠 À recalculer</div>
                </div>
                <div style={{ padding: '0.75rem', borderRadius: '10px', background: 'var(--status-neutral-soft)', border: '1px solid var(--core-border)', textAlign: 'center' }}>
                  <div style={{ fontSize: '1.4rem', fontWeight: 800, color: 'var(--ink-500)' }}>{coherenceData.resume.calculs_non_disponibles || 0}</div>
                  <div style={{ fontSize: '0.78rem', color: 'var(--core-border)', fontWeight: 600 }}>⚪ Sans résultat</div>
                </div>
              </div>
            )}

            {/* Banner de statut de cohérence */}
            {coherenceData.resume && (() => {
              const r = coherenceData.resume;
              const hasNoSignalOnly = (
                (r.critiques || 0) === 0 &&
                (r.attentions || 0) === 0 &&
                (r.informations || 0) === 0 &&
                (r.calculs_a_valider || 0) === 0 &&
                (r.calculs_a_refaire || 0) === 0 &&
                (r.calculs_non_disponibles || 0) === 0 &&
                (r.aucun_signal || 0) > 0
              );

              if (hasNoSignalOnly) {
                return (
                  <div style={{ padding: '1rem 1.25rem', borderRadius: '10px', background: 'var(--status-ok-soft)', border: '1px solid var(--status-ok-soft)', display: 'flex', alignItems: 'center', gap: '0.75rem', color: 'var(--status-ok)', fontSize: '0.9rem', marginBottom: '1.5rem' }}>
                    <CheckCircle2 size={20} color="var(--status-ok)" />
                    <span>Aucun signal de cohérence détecté parmi les contrôles disponibles.</span>
                  </div>
                );
              }

              if ((r.calculs_a_valider || 0) > 0) {
                return (
                  <div style={{ padding: '1rem 1.25rem', borderRadius: '10px', background: 'var(--status-warn-soft)', border: '1px solid var(--status-warn-soft)', display: 'flex', alignItems: 'center', gap: '0.75rem', color: 'var(--status-warn)', fontSize: '0.9rem', marginBottom: '1.5rem' }}>
                    <Info size={20} color="var(--status-warn)" />
                    <span>Certains éléments doivent encore être validés avant que leur cohérence puisse être analysée.</span>
                  </div>
                );
              }

              if ((r.calculs_a_refaire || 0) > 0) {
                return (
                  <div style={{ padding: '1rem 1.25rem', borderRadius: '10px', background: 'var(--accent-soft)', border: '1px solid var(--accent-soft-border)', display: 'flex', alignItems: 'center', gap: '0.75rem', color: 'var(--status-warn-soft)', fontSize: '0.9rem', marginBottom: '1.5rem' }}>
                    <AlertTriangle size={20} color="var(--accent)" />
                    <span>Certains éléments ont été modifiés et doivent être recalculés.</span>
                  </div>
                );
              }

              if ((r.calculs_non_disponibles || 0) > 0) {
                return (
                  <div style={{ padding: '1rem 1.25rem', borderRadius: '10px', background: 'var(--status-neutral-soft)', border: '1px solid var(--core-border)', display: 'flex', alignItems: 'center', gap: '0.75rem', color: 'var(--core-border)', fontSize: '0.9rem', marginBottom: '1.5rem' }}>
                    <Info size={20} color="var(--ink-500)" />
                    <span>Certains éléments ne disposent pas encore d'un résultat de calcul exploitable.</span>
                  </div>
                );
              }

              return null;
            })()}

            {/* Liste des Éléments et de leurs Signaux */}
            {Array.isArray(coherenceData.elements) && coherenceData.elements.length > 0 ? (
              <div style={{ display: 'flex', flexDirection: 'column', gap: '1rem' }}>
                {coherenceData.elements.map((el) => {
                  const styleCfg = STATUT_ANALYSIS_MAP[el.statut_analyse] || STATUT_ANALYSIS_MAP.CALCUL_NON_DISPONIBLE;
                  const canExplain = STATUTS_AVEC_EXPLICATION_IA.includes(el.statut_analyse);
                  const explicationResult = explicationsMap[el.element_id];
                  const isLoadingExpl = !!loadingExplications[el.element_id];
                  const errExpl = errorExplications[el.element_id];
                  return (
                    <div key={el.element_id} style={{ padding: '1rem 1.25rem', borderRadius: '12px', background: 'var(--core-bg)', border: `1px solid ${styleCfg.border}` }}>
                      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '0.5rem', flexWrap: 'wrap', gap: '0.5rem' }}>
                        <div style={{ display: 'flex', alignItems: 'center', gap: '0.75rem' }}>
                          <strong style={{ fontSize: '1rem', color: 'var(--ink-900)' }}>{el.identifiant || `Élément #${el.element_id}`}</strong>
                          <span style={{ fontSize: '0.75rem', textTransform: 'capitalize', color: 'var(--ink-500)', background: 'rgba(255,255,255,0.05)', padding: '0.2rem 0.5rem', borderRadius: '4px' }}>
                            {(el.type_element || '').replace('_', ' ')}
                          </span>
                        </div>
                        <span style={{ fontSize: '0.75rem', fontWeight: 700, padding: '0.25rem 0.65rem', borderRadius: '12px', background: styleCfg.bg, color: styleCfg.color, border: `1px solid ${styleCfg.border}` }}>
                          {styleCfg.label}
                        </span>
                      </div>

                      {el.message_local && (
                        <p style={{ fontSize: '0.85rem', color: 'var(--core-border)', marginBottom: '0.5rem' }}>{el.message_local}</p>
                      )}

                      {/* Signaux de l'élément */}
                      {Array.isArray(el.signaux) && el.signaux.length > 0 && (
                        <div style={{ marginTop: '0.75rem', display: 'flex', flexDirection: 'column', gap: '0.5rem' }}>
                          {el.signaux.map((sig, sIdx) => {
                            const sigCfg = STATUT_ANALYSIS_MAP[sig.categorie] || STATUT_ANALYSIS_MAP.INFORMATION;
                            return (
                              <div key={sIdx} style={{ padding: '0.65rem 0.85rem', borderRadius: '8px', background: 'var(--core-bg)', border: `1px solid ${sigCfg.border}` }}>
                                <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '0.25rem' }}>
                                  <span style={{ fontSize: '0.8rem', fontWeight: 700, color: sigCfg.color }}>{sig.code}</span>
                                  <span style={{ fontSize: '0.7rem', fontWeight: 600, color: sigCfg.color }}>{sig.categorie}</span>
                                </div>
                                <p style={{ fontSize: '0.83rem', color: 'var(--ink-900)', margin: '0.2rem 0 0.4rem 0' }}>{sig.message_local}</p>
                                {(sig.valeur_mesuree != null || sig.valeur_limite != null) && (
                                  <div style={{ fontSize: '0.78rem', color: 'var(--ink-500)', display: 'flex', gap: '1rem', flexWrap: 'wrap', fontWeight: 600 }}>
                                    {sig.valeur_mesuree != null && <span>Mesuré : {sig.valeur_mesuree} {sig.unite || ''}</span>}
                                    {sig.valeur_limite != null && <span>Limite : {sig.valeur_limite} {sig.unite || ''}</span>}
                                  </div>
                                )}
                              </div>
                            );
                          })}
                        </div>
                      )}

                      {el.validation_humaine_requise && !explicationResult && (
                        <div style={{ marginTop: '0.75rem', fontSize: '0.78rem', color: 'var(--ink-500)', fontStyle: 'italic', display: 'flex', alignItems: 'center', gap: '0.4rem' }}>
                          <Info size={14} color="var(--accent)" />
                          <span>Une vérification humaine par l’ingénieur structure est requise.</span>
                        </div>
                      )}

                      {/* Section Explication IA (si éligible : CRITIQUE, ATTENTION, INFORMATION) */}
                      {canExplain && (
                        <div style={{ marginTop: '0.75rem' }}>
                          {!explicationResult && (
                            <button
                              className="btn btn-secondary"
                              style={{
                                padding: '0.4rem 0.85rem',
                                fontSize: '0.8rem',
                                display: 'inline-flex',
                                alignItems: 'center',
                                gap: '0.4rem',
                                border: '1px solid var(--accent-soft-border)',
                                background: 'var(--accent-soft)',
                                color: 'var(--accent)',
                              }}
                              disabled={isLoadingExpl}
                              onClick={() => handleExpliquerElement(el.element_id)}
                            >
                              {isLoadingExpl ? <Loader2 size={14} className="spin" /> : <Sparkles size={14} color="var(--accent)" />}
                              <span>{isLoadingExpl ? 'Explication en cours...' : 'Expliquer avec l’IA'}</span>
                            </button>
                          )}

                          {errExpl && (
                            <div style={{ marginTop: '0.5rem', padding: '0.6rem 0.85rem', borderRadius: '8px', background: 'var(--status-critical-soft)', border: '1px solid var(--status-critical-soft)', color: 'var(--status-critical)', fontSize: '0.82rem', display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: '0.5rem' }}>
                              <span>{errExpl}</span>
                              <button
                                className="btn btn-secondary"
                                style={{ padding: '0.2rem 0.5rem', fontSize: '0.75rem' }}
                                onClick={() => handleExpliquerElement(el.element_id)}
                              >
                                Réessayer
                              </button>
                            </div>
                          )}

                          {explicationResult && (
                            <div style={{ marginTop: '0.75rem', padding: '0.85rem 1rem', borderRadius: '10px', background: 'var(--core-bg)', border: '1px solid var(--accent-soft-border)' }}>
                              <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '0.5rem' }}>
                                <div style={{ display: 'flex', alignItems: 'center', gap: '0.4rem', color: 'var(--accent-soft-border)', fontWeight: 700, fontSize: '0.85rem' }}>
                                  <Sparkles size={16} color="var(--accent)" />
                                  <span>Explication IA</span>
                                </div>
                                {explicationResult.source_explication === 'GEMINI' && (
                                  <span style={{ fontSize: '0.72rem', fontWeight: 600, padding: '0.15rem 0.5rem', borderRadius: '10px', background: 'var(--status-ok-soft)', color: 'var(--status-ok)', border: '1px solid var(--status-ok-soft)' }}>
                                    Source : Gemini
                                  </span>
                                )}
                                {explicationResult.source_explication === 'MOCK' && (
                                  <span style={{ fontSize: '0.72rem', fontWeight: 600, padding: '0.15rem 0.5rem', borderRadius: '10px', background: 'var(--accent-soft)', color: 'var(--accent)', border: '1px solid var(--accent-soft-border)' }}>
                                    Source : Simulation locale
                                  </span>
                                )}
                              </div>

                              {explicationResult.explication_ia ? (
                                <p style={{ fontSize: '0.85rem', color: 'var(--ink-900)', lineHeight: '1.45', margin: '0 0 0.5rem 0' }}>
                                  {explicationResult.explication_ia}
                                </p>
                              ) : (
                                <p style={{ fontSize: '0.83rem', color: 'var(--ink-500)', fontStyle: 'italic', margin: '0 0 0.5rem 0' }}>
                                  L'explication IA n'est pas disponible pour le moment. Le contrôle de cohérence reste disponible ci-dessus.
                                </p>
                              )}

                              {explicationResult.validation_humaine_requise && (
                                <div style={{ marginTop: '0.4rem', fontSize: '0.78rem', color: 'var(--ink-500)', fontStyle: 'italic', display: 'flex', alignItems: 'center', gap: '0.35rem' }}>
                                  <Info size={14} color="var(--accent)" />
                                  <span>{explicationResult.message_validation || "Cette analyse nécessite une vérification humaine par l’ingénieur structure."}</span>
                                </div>
                              )}
                            </div>
                          )}
                        </div>
                      )}
                    </div>
                  );
                })}
              </div>
            ) : (
              <p style={{ fontSize: '0.85rem', color: 'var(--ink-500)', margin: 0 }}>Aucun élément trouvé pour l'analyse de cohérence.</p>
            )}
          </div>
        )}
      </div>

      {/* Liste interactive des éléments */}
      <div style={{ marginBottom: '2.5rem' }}>
        <h3 style={{ fontSize: '1.1rem', fontWeight: 600, marginBottom: '1rem' }}>
          Gestion et Verrouillage Éléments par Éléments
        </h3>

        {allElements.length === 0 ? (
          <div style={{ padding: '1.5rem', textAlign: 'center', background: 'rgba(255,255,255,0.02)', borderRadius: '12px', border: '1px dashed var(--core-border)' }}>
            <p style={{ color: 'var(--text-muted)', fontSize: '0.9rem' }}>
              Aucun élément structurel à verrouiller. Veuillez vérifier l'étape précédente.
            </p>
          </div>
        ) : (
          allElements.map((item) => (
            <div key={item.id} className={`element-card ${item.locked ? 'is-locked' : ''}`} style={{ marginBottom: '1rem', padding: '1rem', background: 'rgba(255,255,255,0.03)', borderRadius: '12px', border: '1px solid var(--core-border)' }}>
              <div className="element-card-header" style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '0.75rem' }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: '0.75rem' }}>
                  <span className="badge badge-info">{item.category}</span>
                  <strong style={{ fontSize: '1rem' }}>{item.id} — {item.name || `${item.category} ${item.id}`}</strong>
                </div>

                <div style={{ display: 'flex', alignItems: 'center', gap: '1rem' }}>
                  <span className={item.locked ? 'badge badge-locked' : 'badge badge-unlocked'}>
                    {item.locked ? <Lock size={12} /> : <Unlock size={12} />}
                    {item.locked ? 'SECTION VERROUILLÉE' : 'MODIFIABLE'}
                  </span>

                  <button
                    className={`btn ${item.locked ? 'btn-secondary' : 'btn-success'}`}
                    style={{ padding: '0.4rem 0.8rem', fontSize: '0.8rem' }}
                    disabled={validatingId === item.id}
                    onClick={() => handleToggleLock(item.id, item.category)}
                  >
                    {item.locked ? <Unlock size={14} /> : <Lock size={14} />}
                    <span>
                      {validatingId === item.id
                        ? 'Validation...'
                        : item.locked
                        ? 'Déverrouiller'
                        : 'Valider & Verrouiller'}
                    </span>
                  </button>
                </div>
              </div>

              <div className="grid-3" style={{ alignItems: 'center' }}>
                <div>
                  <label className="form-label">Section Dimensionnée (b x h)</label>
                  <input
                    type="text"
                    className="form-control"
                    value={item.section || ''}
                    disabled={item.locked}
                    onChange={(e) => updateSection(item.id, item.category, 'section', e.target.value)}
                  />
                </div>

                <div>
                  <label className="form-label">Dispositions de Ferraillage</label>
                  <input
                    type="text"
                    className="form-control"
                    value={item.armatures || item.hauteur || ''}
                    disabled={item.locked}
                    onChange={(e) => updateSection(item.id, item.category, 'armatures', e.target.value)}
                  />
                </div>

                <div style={{ fontSize: '0.85rem', color: 'var(--text-muted)', background: 'var(--core-bg)', padding: '0.75rem', borderRadius: '8px' }}>
                  {item.locked ? (
                    <span style={{ color: 'var(--status-critical)', display: 'flex', alignItems: 'center', gap: '0.35rem' }}>
                      <Lock size={14} /> Section figée par l'ingénieur
                    </span>
                  ) : (
                    <span style={{ color: 'var(--status-ok)', display: 'flex', alignItems: 'center', gap: '0.35rem' }}>
                      <Edit3 size={14} /> Saisie manuelle autorisée avant verrou
                    </span>
                  )}
                </div>
              </div>
            </div>
          ))
        )}
      </div>

      {/* Postes Complémentaires */}
      <div style={{ marginBottom: '2.5rem' }}>
        <h3 style={{ fontSize: '1.1rem', fontWeight: 600, marginBottom: '1rem', display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
          <HardHat size={20} />
          <span>Postes Complémentaires & Prestations par Lot</span>
        </h3>

        {mainDoeuvreError && (
          <div style={{ padding: '0.85rem 1.1rem', borderRadius: '10px', background: 'var(--status-critical-soft)', border: '1px solid var(--status-critical-soft)', marginBottom: '1rem', fontSize: '0.85rem', color: 'var(--status-critical)' }}>
            {mainDoeuvreError}
          </div>
        )}

        {postesMainDoeuvre.length > 0 && (
          <table className="custom-table" style={{ marginBottom: '1rem' }}>
            <thead>
              <tr>
                <th>Lot</th>
                <th>Mode</th>
                <th>Désignation / Type</th>
                <th>Quantité / Géométrie</th>
                <th>Prix Unitaire</th>
                <th>Montant Total</th>
                <th>Action</th>
              </tr>
            </thead>
            <tbody>
              {postesMainDoeuvre.map((poste) => (
                <tr key={poste.id}>
                  <td><span className="badge badge-info">{poste.lot || 'Généralités'}</span></td>
                  <td><span className="badge badge-warning">{poste.mode || 'simple'}</span></td>
                  <td style={{ fontWeight: 600 }}>{poste.designation || poste.type_poste || 'Poste complémentaire'}</td>
                  <td>{poste.mode === 'ratio' ? JSON.stringify(poste.geometrie || {}) : `${poste.quantite} ${poste.unite || ''}`}</td>
                  <td>{poste.prix_unitaire ? `${Number(poste.prix_unitaire).toLocaleString()} FCFA` : '—'}</td>
                  <td style={{ fontWeight: 700, color: 'var(--accent-emerald)' }}>
                    {Number(poste.montant ?? ((poste.quantite || 0) * (poste.prix_unitaire || 0))).toLocaleString()} FCFA
                  </td>
                  <td>
                    <button
                      className="btn btn-secondary"
                      style={{ padding: '0.35rem 0.6rem' }}
                      onClick={() => onRemovePosteMainDoeuvre(poste.id)}
                      title="Supprimer ce poste"
                    >
                      <Trash2 size={14} color="var(--status-critical)" />
                    </button>
                  </td>
                </tr>
              ))}
              <tr>
                <td colSpan={5} style={{ textAlign: 'right', fontWeight: 600 }}>Sous-total Postes Complémentaires</td>
                <td style={{ fontWeight: 700, color: 'var(--accent-emerald)' }}>
                  {totalMainDoeuvre.toLocaleString()} FCFA
                </td>
                <td></td>
              </tr>
            </tbody>
          </table>
        )}

        {/* Suggestion IA -- décrire le poste en langage naturel */}
        <div style={{ background: 'var(--accent-soft)', border: '1px solid var(--accent-soft-border)', borderRadius: '12px', padding: '1.1rem', marginBottom: '1rem' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', marginBottom: '0.6rem' }}>
            <Sparkles size={16} color="var(--accent)" />
            <span style={{ fontSize: '0.9rem', fontWeight: 600, color: 'var(--accent)' }}>Suggestion IA du poste</span>
          </div>
          <div style={{ display: 'flex', gap: '0.6rem', flexWrap: 'wrap' }}>
            <input
              type="text"
              className="form-control"
              style={{ flex: 1, minWidth: '240px' }}
              placeholder="ex : installation et repli de chantier pour la durée des travaux"
              value={posteIADescription}
              onChange={(e) => setPosteIADescription(e.target.value)}
            />
            <button
              className="btn btn-secondary"
              disabled={posteIALoading || !posteIADescription.trim()}
              onClick={handleSuggererPoste}
            >
              {posteIALoading ? <Loader2 size={16} className="spin" /> : <Sparkles size={16} />}
              <span>{posteIALoading ? 'Analyse...' : 'Suggérer avec l\'IA'}</span>
            </button>
          </div>
          {posteIAError && (
            <div style={{ display: 'flex', alignItems: 'center', gap: '0.4rem', color: 'var(--status-critical)', fontSize: '0.82rem', marginTop: '0.5rem' }}>
              <AlertCircle size={14} />
              <span>{posteIAError}</span>
            </div>
          )}
          {posteIAConfiance && (
            <p style={{ fontSize: '0.8rem', color: 'var(--text-muted)', marginTop: '0.5rem' }}>
              Désignation, unité et lot pré-remplis ci-dessous (confiance IA : {posteIAConfiance}). Complétez quantité et prix unitaire, puis vérifiez avant ajout.
            </p>
          )}
        </div>

        {/* Formulaire Bi-mode */}
        <div style={{ background: 'rgba(255,255,255,0.02)', border: '1px solid var(--core-border)', borderRadius: '12px', padding: '1.25rem' }}>
          <div className="grid-2" style={{ marginBottom: '1rem' }}>
            <div>
              <label className="form-label">Lot d'Ouvrage</label>
              <select
                className="form-select"
                value={nouveauPoste.lot}
                onChange={(e) => setNouveauPoste((p) => ({ ...p, lot: e.target.value }))}
              >
                <option value="lot_00_generalites">Lot 00 — Généralités</option>
                <option value="lot_01_terrassement">Lot 01 — Terrassement</option>
                <option value="lot_02_gros_oeuvre_infrastructure">Lot 02a — Gros Œuvre Infrastructure</option>
                <option value="lot_02_gros_oeuvre_superstructure">Lot 02b — Gros Œuvre Superstructure</option>
                <option value="lot_03_etancheite">Lot 03 — Étanchéité</option>
                <option value="lot_04_plomberie">Lot 04 — Plomberie</option>
                <option value="lot_05_assainissement">Lot 05 — Assainissement</option>
                <option value="lot_06_electricite">Lot 06 — Électricité</option>
                <option value="lot_07_charpente">Lot 07 — Charpente</option>
                <option value="lot_08_couverture">Lot 08 — Couverture</option>
              </select>
            </div>

            <div>
              <label className="form-label">Mode de Saisie</label>
              <select
                className="form-select"
                value={nouveauPoste.mode}
                onChange={(e) => setNouveauPoste((p) => ({ ...p, mode: e.target.value }))}
              >
                <option value="simple">Mode Simple (Désignation, Quantité, Prix)</option>
                <option value="ratio">Mode Ratio (Choix du Type + Géométrie)</option>
              </select>
            </div>
          </div>

          {nouveauPoste.mode === 'simple' ? (
            <div className="grid-4" style={{ alignItems: 'end', gap: '0.75rem' }}>
              <div>
                <label className="form-label">Désignation du Poste</label>
                <input
                  type="text"
                  className="form-control"
                  placeholder="ex : Installation de chantier"
                  value={nouveauPoste.designation}
                  onChange={(e) => setNouveauPoste((p) => ({ ...p, designation: e.target.value }))}
                />
              </div>
              <div>
                <label className="form-label">Unité</label>
                <select
                  className="form-select"
                  value={nouveauPoste.unite}
                  onChange={(e) => setNouveauPoste((p) => ({ ...p, unite: e.target.value }))}
                >
                  <option value="forfait">Forfait</option>
                  <option value="ens.">Ensemble (ens.)</option>
                  <option value="m²">m²</option>
                  <option value="m³">m³</option>
                  <option value="kg">kg</option>
                  <option value="ml">Mètre linéaire (ml)</option>
                  <option value="jour">Jour</option>
                  <option value="unité">Unité</option>
                  <option value="u">Unité (u)</option>
                </select>
              </div>
              <div>
                <label className="form-label">Quantité</label>
                <input
                  type="number"
                  min="0"
                  step="0.01"
                  className="form-control"
                  placeholder="ex : 1"
                  value={nouveauPoste.quantite}
                  onChange={(e) => setNouveauPoste((p) => ({ ...p, quantite: e.target.value }))}
                />
              </div>
              <div>
                <label className="form-label">Prix Unitaire (FCFA)</label>
                <input
                  type="number"
                  min="0"
                  step="1"
                  className="form-control"
                  placeholder="ex : 150000"
                  value={nouveauPoste.prixUnitaire}
                  onChange={(e) => setNouveauPoste((p) => ({ ...p, prixUnitaire: e.target.value }))}
                />
              </div>
            </div>
          ) : (
            <div className="grid-2" style={{ alignItems: 'end', gap: '1rem' }}>
              <div>
                <label className="form-label">Type de Prestation Ratio</label>
                <select
                  className="form-select"
                  value={nouveauPoste.typePoste}
                  onChange={(e) => setNouveauPoste((p) => ({ ...p, typePoste: e.target.value }))}
                >
                  <option value="maconnerie_creuse">Maçonnerie agglos creux (Surface m²)</option>
                  <option value="maconnerie_pleine">Maçonnerie agglos pleins (Surface m²)</option>
                  <option value="enduit_interieur">Enduit ciment intérieur (Surface m²)</option>
                  <option value="enduit_exterieur">Enduit ciment extérieur (Surface m²)</option>
                  <option value="chainage_linteau">Chaînage / Linteau (Longueur ml)</option>
                  <option value="chape_mortier">Chape mortier de lissage (Surface m²)</option>
                </select>
              </div>
              <div>
                <label className="form-label">
                  {(nouveauPoste.typePoste || '').includes('chainage') ? 'Longueur (ml)' : 'Surface (m²)'}
                </label>
                <input
                  type="number"
                  min="0"
                  step="0.1"
                  className="form-control"
                  placeholder="ex : 45.0"
                  value={nouveauPoste.valeurGeometrie}
                  onChange={(e) => setNouveauPoste((p) => ({ ...p, valeurGeometrie: e.target.value }))}
                />
              </div>
            </div>
          )}

          <button
            className="btn btn-success"
            style={{ marginTop: '1.1rem' }}
            disabled={posteEnCours}
            onClick={handleAjouterPoste}
          >
            <Plus size={16} />
            <span>{posteEnCours ? 'Ajout...' : 'Ajouter ce Poste Complémentaire'}</span>
          </button>
        </div>
      </div>

      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
        <button className="btn btn-secondary" onClick={onBack}>
          <ArrowLeft size={18} />
          <span>Retour aux calculs</span>
        </button>

        <button className="btn btn-primary" onClick={onNext}>
          <span>Passer au Plan de Fondation & Exports DQE</span>
          <ArrowRight size={18} />
        </button>
      </div>
    </div>
  );
}