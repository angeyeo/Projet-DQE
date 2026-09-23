import React, { useState } from 'react';
import { ArrowLeft, ArrowRight, Shield, Layers, Box, Cpu, Sparkles, Loader2, AlertCircle } from 'lucide-react';
import { dqeService } from '../api/dqeService';

// Ligne de tableau générique + bouton "Expliquer (IA)" -- branché sur
// POST /assistant/expliquer-element/ (jamais appelé depuis aucune UI avant).
// L'explication n'est demandée qu'à la demande de l'ingénieur (pas
// automatiquement pour chaque élément) pour respecter le throttling
// backend (assistant_expliquer: 20/min).
function ElementRow({ item, columns, colSpan, explication, onExpliquer }) {
  const isOpen = !!explication;

  return (
    <>
      <tr>
        {columns}
        <td>
          <button
            className="btn btn-secondary"
            style={{ padding: '0.35rem 0.7rem', fontSize: '0.78rem' }}
            disabled={explication?.loading || item.calculIndisponible}
            onClick={() => onExpliquer(item)}
            title={item.calculIndisponible ? 'Aucun calcul disponible à expliquer' : "Demander une explication à l'IA"}
          >
            {explication?.loading ? <Loader2 size={14} className="spin" /> : <Sparkles size={14} />}
            <span>{explication?.loading ? '...' : 'Expliquer (IA)'}</span>
          </button>
        </td>
      </tr>
      {isOpen && (
        <tr>
          <td colSpan={colSpan} style={{ background: 'var(--accent-soft)', borderTop: 'none' }}>
            {explication.error ? (
              <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', color: 'var(--status-critical)', fontSize: '0.85rem' }}>
                <AlertCircle size={16} />
                <span>{explication.error}</span>
              </div>
            ) : (
              <div style={{ fontSize: '0.85rem', color: 'var(--ink-900)' }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: '0.4rem', marginBottom: '0.35rem' }}>
                  <span className="badge badge-info" style={{ fontSize: '0.7rem' }}>
                    {explication.source === 'MOCK' ? 'MODE DÉMO' : explication.source === 'FALLBACK_LOCAL' ? 'FALLBACK LOCAL' : 'GEMINI'}
                  </span>
                  <span style={{ color: 'var(--text-muted)', fontSize: '0.75rem' }}>
                    Validation humaine requise avant toute utilisation.
                  </span>
                </div>
                <p style={{ margin: 0, lineHeight: 1.5 }}>{explication.texte}</p>
              </div>
            )}
          </td>
        </tr>
      )}
    </>
  );
}

export default function Step2_Calculs({ sections, projectData, onBack, onNext }) {
  const { poteaux = [], poutres = [], semelles = [] } = sections || {};
  const totalElements = poteaux.length + poutres.length + semelles.length;

  // Explications IA en cache, indexées par elementId (id numérique réel
  // ElementStructurel, pas le repère P1/S1 affiché).
  const [explications, setExplications] = useState({});

  const handleExpliquer = async (item) => {
    if (!item.elementId) return;
    setExplications((prev) => ({ ...prev, [item.elementId]: { loading: true } }));
    try {
      const res = await dqeService.expliquerElementIA(item.elementId);
      setExplications((prev) => ({
        ...prev,
        [item.elementId]: {
          loading: false,
          texte: res.explication,
          source: res.source,
        },
      }));
    } catch (err) {
      setExplications((prev) => ({
        ...prev,
        [item.elementId]: {
          loading: false,
          error: err.message || "Impossible d'obtenir une explication pour cet élément.",
        },
      }));
    }
  };

  return (
    <div className="glass-panel">
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '2rem' }}>
        <div>
          <h2 style={{ fontSize: '1.5rem', fontWeight: 700, marginBottom: '0.5rem' }}>
            Étape 2 : Descente de charge & Sections proposées
          </h2>
          <p style={{ color: 'var(--text-muted)', fontSize: '0.9rem' }}>
            Calcul automatique des sections normatives ({projectData.norme || 'BAEL 91'}) pour l'ouvrage <strong>{projectData.nomProjet || 'Nouveau Projet'}</strong>.
          </p>
        </div>
        <div className="badge badge-info" style={{ padding: '0.5rem 1rem', fontSize: '0.85rem', display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
          <Cpu size={16} />
          <span>Norme : {projectData.norme || 'BAEL91'}</span>
        </div>
      </div>

      {/* Cartes de synthèse */}
      <div className="grid-3" style={{ marginBottom: '2rem' }}>
        <div style={{ background: 'var(--accent-soft)', border: '1px solid var(--accent-soft-border)', padding: '1.25rem', borderRadius: '14px' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', color: 'var(--accent)', marginBottom: '0.5rem' }}>
            <Layers size={18} />
            <h4 style={{ fontSize: '0.9rem', fontWeight: 600 }}>Combinaison ELU</h4>
          </div>
          <div style={{ fontSize: '1.3rem', fontWeight: 700 }}>
            q_ELU = 1.35 G + 1.5 Q
          </div>
          <div style={{ fontSize: '0.8rem', color: 'var(--text-muted)', marginTop: '0.25rem' }}>
            Charge permanente G = 5.0 kN/m² | Q = {projectData.chargeExploitation || 1.5} kN/m²
          </div>
        </div>

        <div style={{ background: 'var(--status-ok-soft)', border: '1px solid var(--status-ok-soft)', padding: '1.25rem', borderRadius: '14px' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', color: 'var(--status-ok)', marginBottom: '0.5rem' }}>
            <Box size={18} />
            <h4 style={{ fontSize: '0.9rem', fontWeight: 600 }}>Nombre d'Éléments</h4>
          </div>
          <div style={{ fontSize: '1.3rem', fontWeight: 700 }}>
            {totalElements} Éléments Calculés
          </div>
          <div style={{ fontSize: '0.8rem', color: 'var(--text-muted)', marginTop: '0.25rem' }}>
            {poteaux.length} Poteaux | {poutres.length} Poutres | {semelles.length} Semelles
          </div>
        </div>

        <div style={{ background: 'var(--status-warn-soft)', border: '1px solid var(--status-warn-soft)', padding: '1.25rem', borderRadius: '14px' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', color: 'var(--status-warn)', marginBottom: '0.5rem' }}>
            <Shield size={18} />
            <h4 style={{ fontSize: '0.9rem', fontWeight: 600 }}>Validation Humaine</h4>
          </div>
          <div style={{ fontSize: '1.3rem', fontWeight: 700 }}>
            Étape 3 Suivante
          </div>
          <div style={{ fontSize: '0.8rem', color: 'var(--text-muted)', marginTop: '0.25rem' }}>
            Validation obligatoire avant verrouillage final.
          </div>
        </div>
      </div>

      {totalElements === 0 ? (
        <div style={{ padding: '2rem', textAlign: 'center', background: 'rgba(255,255,255,0.02)', borderRadius: '12px', border: '1px dashed var(--core-border)', marginBottom: '2rem' }}>
          <p style={{ color: 'var(--text-muted)', fontSize: '0.95rem' }}>
            Aucun élément structurel calculé pour le moment.
          </p>
        </div>
      ) : (
        <>
          {/* Tableau des Poteaux */}
          <div style={{ marginBottom: '2rem' }}>
            <h3 style={{ fontSize: '1.1rem', fontWeight: 600, marginBottom: '0.75rem' }}>
              Poteaux (Descente de charge axiale N_sd)
            </h3>
            <table className="custom-table">
              <thead>
                <tr>
                  <th>Identifiant</th>
                  <th>Nom de l'Élément</th>
                  <th>Effort Axial (N_sd)</th>
                  <th>Section Proposée (b x h)</th>
                  <th>Armatures (FeE500)</th>
                  <th>IA</th>
                </tr>
              </thead>
              <tbody>
                {poteaux.map((item, idx) => (
                  <ElementRow
                    key={item.id || idx}
                    item={item}
                    colSpan={6}
                    explication={explications[item.elementId]}
                    onExpliquer={handleExpliquer}
                    columns={
                      <>
                        <td style={{ fontWeight: 600, color: 'var(--accent)' }}>{item.id || `P${idx + 1}`}</td>
                        <td>{item.name || `Poteau P${idx + 1}`}</td>
                        <td><span className="badge badge-info">{item.charge || item.effort_axial || '150 kN'}</span></td>
                        <td style={{ fontWeight: 700, color: 'var(--accent-emerald)' }}>{item.section || '20 x 20 cm'}</td>
                        <td>{item.armatures || '4 HA 12'}</td>
                      </>
                    }
                  />
                ))}
              </tbody>
            </table>
          </div>

          {/* Tableau des Poutres */}
          <div style={{ marginBottom: '2rem' }}>
            <h3 style={{ fontSize: '1.1rem', fontWeight: 600, marginBottom: '0.75rem' }}>
              Poutres (Pré-dimensionnement en flexion simple)
            </h3>
            <table className="custom-table">
              <thead>
                <tr>
                  <th>Identifiant</th>
                  <th>Nom de la Poutre</th>
                  <th>Portée L</th>
                  <th>Section Proposée (b x h)</th>
                  <th>Armatures Longitudinales</th>
                  <th>IA</th>
                </tr>
              </thead>
              <tbody>
                {poutres.map((item, idx) => (
                  <ElementRow
                    key={item.id || idx}
                    item={item}
                    colSpan={6}
                    explication={explications[item.elementId]}
                    onExpliquer={handleExpliquer}
                    columns={
                      <>
                        <td style={{ fontWeight: 600, color: 'var(--accent)' }}>{item.id || `R${idx + 1}`}</td>
                        <td>{item.name || `Poutre R${idx + 1}`}</td>
                        <td>{item.portee || '5.0 m'}</td>
                        <td style={{ fontWeight: 700, color: 'var(--accent-emerald)' }}>{item.section || '20 x 40 cm'}</td>
                        <td>{item.armatures || '3 HA 14'}</td>
                      </>
                    }
                  />
                ))}
              </tbody>
            </table>
          </div>

          {/* Tableau des Semelles */}
          <div style={{ marginBottom: '2.5rem' }}>
            <h3 style={{ fontSize: '1.1rem', fontWeight: 600, marginBottom: '0.75rem' }}>
              Semelles de Fondation (Contrainte du sol σ_sol)
            </h3>
            <table className="custom-table">
              <thead>
                <tr>
                  <th>Identifiant</th>
                  <th>Nom de la Semelle</th>
                  <th>Contrainte du Sol</th>
                  <th>Dimensions (A x B)</th>
                  <th>Hauteur h</th>
                  <th>IA</th>
                </tr>
              </thead>
              <tbody>
                {semelles.map((item, idx) => (
                  <ElementRow
                    key={item.id || idx}
                    item={item}
                    colSpan={6}
                    explication={explications[item.elementId]}
                    onExpliquer={handleExpliquer}
                    columns={
                      <>
                        <td style={{ fontWeight: 600, color: 'var(--accent)' }}>{item.id || `S${idx + 1}`}</td>
                        <td>{item.name || `Semelle S${idx + 1}`}</td>
                        <td>{item.contrainteSol || '0.20 MPa'}</td>
                        <td style={{ fontWeight: 700, color: 'var(--accent-emerald)' }}>{item.section || '120 x 120 cm'}</td>
                        <td>{item.hauteur || '35 cm'}</td>
                      </>
                    }
                  />
                ))}
              </tbody>
            </table>
          </div>
        </>
      )}

      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
        <button className="btn btn-secondary" onClick={onBack}>
          <ArrowLeft size={18} />
          <span>Retour aux paramètres</span>
        </button>

        <button className="btn btn-primary" onClick={onNext}>
          <span>Passer à la Validation & Verrouillage</span>
          <ArrowRight size={18} />
        </button>
      </div>
    </div>
  );
}