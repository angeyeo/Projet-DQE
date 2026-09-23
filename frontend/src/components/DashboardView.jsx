import React from 'react';
import { Building, Layers, Lock, FileSpreadsheet, ShieldCheck, Edit3 } from 'lucide-react';

export default function DashboardView({ projectData, sections, lockedCount, totalCount, onNavigate }) {
  const { poteaux = [], poutres = [], semelles = [] } = sections || {};

  const allElements = [
    ...poteaux.map((p) => ({ ...p, category: 'Poteau' })),
    ...poutres.map((p) => ({ ...p, category: 'Poutre' })),
    ...semelles.map((s) => ({ ...s, category: 'Semelle' })),
  ];

  const percentLocked = totalCount > 0 ? Math.round((lockedCount / totalCount) * 100) : 0;

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '1.75rem' }}>
      {/* Bandeau projet */}
      <div
        className="fade-in-up"
        style={{
          background: 'linear-gradient(135deg, var(--accent-soft), var(--core-surface))',
          border: '1px solid var(--core-border)',
          borderRadius: 'var(--radius-lg)',
          padding: '1.5rem 2rem',
          display: 'flex',
          justifyContent: 'space-between',
          alignItems: 'center',
          flexWrap: 'wrap',
          gap: '1rem',
        }}
      >
        <div>
          <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', marginBottom: '0.35rem' }}>
            <span className="badge badge-info">Vue Synthétique</span>
            <span style={{ fontSize: '0.8rem', color: 'var(--ink-500)' }}>Normes {projectData.norme || 'BAEL 91'}</span>
          </div>
          <h2 style={{ fontSize: '1.6rem', fontWeight: 700, fontFamily: 'var(--font-heading)' }}>
            {projectData.nomProjet || 'Nouveau Projet BTP'}
          </h2>
          <p style={{ color: 'var(--ink-500)', fontSize: '0.875rem', marginTop: '0.2rem' }}>
            {projectData.planFileName ? (
              <>Fichier plan chargé : <strong>{projectData.planFileName}</strong></>
            ) : (
              'Aucun plan chargé pour le moment'
            )}
          </p>
        </div>

        <div style={{ display: 'flex', gap: '0.75rem' }}>
          <button className="btn btn-secondary" onClick={() => onNavigate('step3')}>
            <Lock size={16} />
            <span>Gérer les Verrous</span>
          </button>
          <button className="btn btn-primary" onClick={() => onNavigate('step4')}>
            <FileSpreadsheet size={16} />
            <span>Voir le Devis DQE</span>
          </button>
        </div>
      </div>

      {/* KPI */}
      <div className="grid-4 stagger">
        <div className="kpi-card">
          <div className="kpi-icon blue"><Building size={20} /></div>
          <div>
            <div className="kpi-value tabular" style={{ fontSize: '1.05rem' }}>
              R+{projectData.nombreNiveaux || 0} · {projectData.typeUsage || '—'}
            </div>
            <div className="kpi-label">Structure & usage</div>
          </div>
        </div>

        <div className="kpi-card">
          <div className="kpi-icon green"><Layers size={20} /></div>
          <div>
            <div className="kpi-value tabular">{totalCount}</div>
            <div className="kpi-label">Éléments calculés</div>
          </div>
        </div>

        <div className="kpi-card">
          <div className="kpi-icon amber"><Lock size={20} /></div>
          <div>
            <div className="kpi-value tabular">{percentLocked}%</div>
            <div className="kpi-label">Verrouillé ({lockedCount}/{totalCount})</div>
          </div>
        </div>

        <div className="kpi-card">
          <div className="kpi-icon orange"><FileSpreadsheet size={20} /></div>
          <div>
            <div className="kpi-value" style={{ fontSize: '1.05rem' }}>
              {totalCount > 0 && lockedCount === totalCount ? 'Prêt à l\'export' : 'En cours'}
            </div>
            <div className="kpi-label">Devis quantitatif</div>
          </div>
        </div>
      </div>

      {/* Synthèse des éléments */}
      <div className="glass-panel fade-in-up">
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '1.25rem', flexWrap: 'wrap', gap: '0.75rem' }}>
          <div>
            <h3 style={{ fontSize: '1.1rem', fontWeight: 600, fontFamily: 'var(--font-heading)' }}>
              Synthèse des éléments & sections validées
            </h3>
            <p style={{ fontSize: '0.8rem', color: 'var(--ink-500)' }}>
              État du pré-dimensionnement pour les poteaux, poutres et semelles de l'ouvrage.
            </p>
          </div>

          <button className="btn btn-secondary" onClick={() => onNavigate('step2')} style={{ fontSize: '0.8rem', padding: '0.4rem 0.85rem' }}>
            <Edit3 size={14} />
            <span>Consulter les calculs</span>
          </button>
        </div>

        {allElements.length > 0 ? (
          <table className="custom-table">
            <thead>
              <tr>
                <th>Catégorie</th>
                <th>Identifiant</th>
                <th>Section dimensionnée</th>
                <th>Armatures / Ferraillage</th>
                <th>Statut verrouillage</th>
              </tr>
            </thead>
            <tbody>
              {allElements.map((item) => (
                <tr key={item.id}>
                  <td><span className="badge badge-info">{item.category}</span></td>
                  <td style={{ fontWeight: 600 }}>{item.id} — {item.name}</td>
                  <td style={{ fontWeight: 700, color: 'var(--status-ok)' }}>{item.section}</td>
                  <td>{item.armatures || item.hauteur || '-'}</td>
                  <td>
                    <span className={item.locked ? 'badge badge-locked' : 'badge badge-unlocked'}>
                      {item.locked ? <Lock size={12} /> : <ShieldCheck size={12} />}
                      {item.locked ? 'Verrouillée' : 'Modifiable'}
                    </span>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        ) : (
          <div style={{ padding: '2rem', textAlign: 'center', color: 'var(--ink-500)' }}>
            Aucun élément calculé pour le moment.
          </div>
        )}
      </div>
    </div>
  );
}