import React from 'react';
import { Building, Layers, Lock, FileSpreadsheet, ArrowRight, ShieldCheck, Cpu, CheckCircle2, FileUp, Sparkles } from 'lucide-react';

export default function DashboardView({ projectData, sections, lockedCount, totalCount, onNavigate }) {
  const { poteaux = [], poutres = [], semelles = [] } = sections || {};

  const allElements = [
    ...poteaux.map(p => ({ ...p, category: 'Poteau' })),
    ...poutres.map(p => ({ ...p, category: 'Poutre' })),
    ...semelles.map(s => ({ ...s, category: 'Semelle' })),
  ];

  const percentLocked = totalCount > 0 ? Math.round((lockedCount / totalCount) * 100) : 0;

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '2rem' }}>
      {/* Welcome Banner Core 2.0 */}
      <div
        style={{
          background: 'linear-gradient(135deg, rgba(59, 130, 246, 0.12), rgba(99, 102, 241, 0.12))',
          border: '1px solid var(--core-border)',
          borderRadius: 'var(--radius-lg)',
          padding: '1.75rem 2rem',
          display: 'flex',
          justifyContent: 'space-between',
          alignItems: 'center',
        }}
      >
        <div>
          <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', marginBottom: '0.35rem' }}>
            <span className="badge badge-info">Ingénierie BTP & SaaS</span>
            <span style={{ fontSize: '0.8rem', color: 'var(--text-muted)' }}>• Normes BAEL 91 / Eurocode 2</span>
          </div>
          <h2 style={{ fontSize: '1.6rem', fontWeight: 700, fontFamily: 'var(--font-heading)' }}>
            Tableau de Bord — {projectData.nomProjet}
          </h2>
          <p style={{ color: 'var(--text-muted)', fontSize: '0.9rem', marginTop: '0.25rem' }}>
            Synthèse du pré-dimensionnement, état de la descente de charge et génération du devis quantitatif (DQE).
          </p>
        </div>

        <button className="btn btn-primary" onClick={() => onNavigate('step1')}>
          <span>Lancer un Calcul</span>
          <ArrowRight size={16} />
        </button>
      </div>

      {/* KPI Stat Cards Grid */}
      <div className="grid-4">
        <div className="kpi-card" onClick={() => onNavigate('step1')} style={{ cursor: 'pointer' }}>
          <div className="kpi-icon blue">
            <Building size={22} />
          </div>
          <div>
            <div className="kpi-lbl">Bâtiment / Usage</div>
            <div className="kpi-val" style={{ fontSize: '1.2rem' }}>R+{projectData.nombreNiveaux} • {projectData.typeUsage}</div>
          </div>
        </div>

        <div className="kpi-card" onClick={() => onNavigate('step2')} style={{ cursor: 'pointer' }}>
          <div className="kpi-icon emerald">
            <Layers size={22} />
          </div>
          <div>
            <div className="kpi-lbl">Sections Calculées</div>
            <div className="kpi-val">{totalCount} Éléments</div>
          </div>
        </div>

        <div className="kpi-card" onClick={() => onNavigate('step3')} style={{ cursor: 'pointer' }}>
          <div className="kpi-icon amber">
            <Lock size={22} />
          </div>
          <div>
            <div className="kpi-lbl">Verrouillage Ingénieur</div>
            <div className="kpi-val">{percentLocked}% ({lockedCount}/{totalCount})</div>
          </div>
        </div>

        <div className="kpi-card" onClick={() => onNavigate('step4')} style={{ cursor: 'pointer' }}>
          <div className="kpi-icon indigo">
            <FileSpreadsheet size={22} />
          </div>
          <div>
            <div className="kpi-lbl">Estimation DQE</div>
            <div className="kpi-val" style={{ fontSize: '1.25rem' }}>Devis DEK Prêt</div>
          </div>
        </div>
      </div>

      {/* Grid 2 colonnes : Raccourcis du parcours & Aperçu des éléments */}
      <div className="grid-2">
        {/* Raccourcis des 4 Étapes */}
        <div className="glass-panel" style={{ padding: '1.5rem' }}>
          <h3 style={{ fontSize: '1.1rem', fontWeight: 600, marginBottom: '1.25rem', fontFamily: 'var(--font-heading)' }}>
            Parcours de Conception & Validation BTP
          </h3>

          <div style={{ display: 'flex', flexDirection: 'column', gap: '0.85rem' }}>
            <div
              style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', padding: '0.85rem 1rem', background: 'var(--core-surface)', border: '1px solid var(--core-border)', borderRadius: 'var(--radius-md)', cursor: 'pointer' }}
              onClick={() => onNavigate('step1')}
            >
              <div style={{ display: 'flex', alignItems: 'center', gap: '0.75rem' }}>
                <FileUp size={18} color="var(--accent-primary)" />
                <div>
                  <strong style={{ fontSize: '0.9rem' }}>1. Plans & Saisie des paramètres</strong>
                  <div style={{ fontSize: '0.75rem', color: 'var(--text-muted)' }}>{projectData.planFileName} • {projectData.porteeMax}m portée</div>
                </div>
              </div>
              <ArrowRight size={16} color="var(--text-muted)" />
            </div>

            <div
              style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', padding: '0.85rem 1rem', background: 'var(--core-surface)', border: '1px solid var(--core-border)', borderRadius: 'var(--radius-md)', cursor: 'pointer' }}
              onClick={() => onNavigate('step2')}
            >
              <div style={{ display: 'flex', alignItems: 'center', gap: '0.75rem' }}>
                <Cpu size={18} color="var(--accent-emerald)" />
                <div>
                  <strong style={{ fontSize: '0.9rem' }}>2. Calculs Structurels (BAEL 91)</strong>
                  <div style={{ fontSize: '0.75rem', color: 'var(--text-muted)' }}>Descente de charge q_ELU = 1.35G + 1.5Q</div>
                </div>
              </div>
              <ArrowRight size={16} color="var(--text-muted)" />
            </div>

            <div
              style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', padding: '0.85rem 1rem', background: 'var(--core-surface)', border: '1px solid var(--core-border)', borderRadius: 'var(--radius-md)', cursor: 'pointer' }}
              onClick={() => onNavigate('step3')}
            >
              <div style={{ display: 'flex', alignItems: 'center', gap: '0.75rem' }}>
                <Lock size={18} color="var(--accent-amber)" />
                <div>
                  <strong style={{ fontSize: '0.9rem' }}>3. Validation & Verrouillage</strong>
                  <div style={{ fontSize: '0.75rem', color: 'var(--text-muted)' }}>{lockedCount} sections verrouillées par l'ingénieur</div>
                </div>
              </div>
              <ArrowRight size={16} color="var(--text-muted)" />
            </div>

            <div
              style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', padding: '0.85rem 1rem', background: 'var(--core-surface)', border: '1px solid var(--core-border)', borderRadius: 'var(--radius-md)', cursor: 'pointer' }}
              onClick={() => onNavigate('step4')}
            >
              <div style={{ display: 'flex', alignItems: 'center', gap: '0.75rem' }}>
                <Sparkles size={18} color="var(--accent-indigo)" />
                <div>
                  <strong style={{ fontSize: '0.9rem' }}>4. Devis Quantitatif DQE & Couche IA</strong>
                  <div style={{ fontSize: '0.75rem', color: 'var(--text-muted)' }}>Bordereau des matériaux et assistant IA</div>
                </div>
              </div>
              <ArrowRight size={16} color="var(--text-muted)" />
            </div>
          </div>
        </div>

        {/* Aperçu rapide des éléments structurels */}
        <div className="glass-panel" style={{ padding: '1.5rem' }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '1.25rem' }}>
            <h3 style={{ fontSize: '1.1rem', fontWeight: 600, fontFamily: 'var(--font-heading)' }}>
              Aperçu des Éléments Dimensionnés
            </h3>
            <button className="btn btn-secondary" style={{ padding: '0.35rem 0.75rem', fontSize: '0.75rem' }} onClick={() => onNavigate('step3')}>
              Gérer le verrouillage
            </button>
          </div>

          {allElements.length > 0 ? (
            <table className="custom-table">
              <thead>
                <tr>
                  <th>Catégorie</th>
                  <th>Identifiant</th>
                  <th>Section</th>
                  <th>Verrou</th>
                </tr>
              </thead>
              <tbody>
                {allElements.slice(0, 5).map((item) => (
                  <tr key={item.id}>
                    <td><span className="badge badge-info">{item.category}</span></td>
                    <td style={{ fontWeight: 600 }}>{item.id}</td>
                    <td style={{ fontWeight: 700, color: 'var(--accent-emerald)' }}>{item.section}</td>
                    <td>
                      <span className={item.locked ? 'badge badge-locked' : 'badge badge-unlocked'}>
                        {item.locked ? 'VERROUILLÉ' : 'LIBRE'}
                      </span>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          ) : (
            <p style={{ color: 'var(--text-muted)', fontSize: '0.85rem' }}>Aucun élément dimensionné. Lancez les calculs à l'Étape 1.</p>
          )}
        </div>
      </div>
    </div>
  );
}
