import React from 'react';
import { Building, Layers, Lock, FileSpreadsheet, ArrowRight, ShieldCheck, CheckCircle2, Edit3 } from 'lucide-react';

export default function DashboardView({ projectData, sections, lockedCount, totalCount, onNavigate }) {
  const { poteaux = [], poutres = [], semelles = [] } = sections || {};

  const allElements = [
    ...poteaux.map(p => ({ ...p, category: 'Poteau' })),
    ...poutres.map(p => ({ ...p, category: 'Poutre' })),
    ...semelles.map(s => ({ ...s, category: 'Semelle' })),
  ];

  const percentLocked = totalCount > 0 ? Math.round((lockedCount / totalCount) * 100) : 0;

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '1.75rem' }}>
      {/* Welcome Banner Core 2.0 */}
      <div
        style={{
          background: 'linear-gradient(135deg, rgba(59, 130, 246, 0.12), rgba(99, 102, 241, 0.12))',
          border: '1px solid var(--core-border)',
          borderRadius: 'var(--radius-lg)',
          padding: '1.5rem 2rem',
          display: 'flex',
          justifyContent: 'space-between',
          alignItems: 'center',
        }}
      >
        <div>
          <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', marginBottom: '0.35rem' }}>
            <span className="badge badge-info">Vue Synthétique</span>
            <span style={{ fontSize: '0.8rem', color: 'var(--text-muted)' }}>Normes BAEL 91 / Eurocode 2</span>
          </div>
          <h2 style={{ fontSize: '1.6rem', fontWeight: 700, fontFamily: 'var(--font-heading)' }}>
            {projectData.nomProjet}
          </h2>
          <p style={{ color: 'var(--text-muted)', fontSize: '0.875rem', marginTop: '0.2rem' }}>
            Fichier plan chargé : <strong>{projectData.planFileName}</strong> • Portée max : <strong>{projectData.porteeMax}m</strong>
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

      {/* KPI Stat Cards Grid */}
      <div className="grid-4">
        <div className="kpi-card">
          <div className="kpi-icon blue">
            <Building size={22} />
          </div>
          <div>
            <div className="kpi-lbl">Structure & Usage</div>
            <div className="kpi-val" style={{ fontSize: '1.15rem' }}>R+{projectData.nombreNiveaux} • {projectData.typeUsage}</div>
          </div>
        </div>

        <div className="kpi-card">
          <div className="kpi-icon emerald">
            <Layers size={22} />
          </div>
          <div>
            <div className="kpi-lbl">Total Sections</div>
            <div className="kpi-val">{totalCount} Éléments</div>
          </div>
        </div>

        <div className="kpi-card">
          <div className="kpi-icon amber">
            <Lock size={22} />
          </div>
          <div>
            <div className="kpi-lbl">Taux de Verrouillage</div>
            <div className="kpi-val">{percentLocked}% ({lockedCount}/{totalCount})</div>
          </div>
        </div>

        <div className="kpi-card">
          <div className="kpi-icon indigo">
            <FileSpreadsheet size={22} />
          </div>
          <div>
            <div className="kpi-lbl">Devis Quantitatif</div>
            <div className="kpi-val" style={{ fontSize: '1.15rem', color: 'var(--accent-emerald)' }}>Prêt à l'export</div>
          </div>
        </div>
      </div>

      {/* Tableau Synthétique Épuré des Éléments Structurels */}
      <div className="glass-panel" style={{ padding: '1.75rem' }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '1.25rem' }}>
          <div>
            <h3 style={{ fontSize: '1.15rem', fontWeight: 600, fontFamily: 'var(--font-heading)' }}>
              Synthèse des Éléments & Sections Validées
            </h3>
            <p style={{ fontSize: '0.8rem', color: 'var(--text-muted)' }}>
              État du pré-dimensionnement pour les poteaux, poutres et semelles de l'ouvrage.
            </p>
          </div>

          <button className="btn btn-secondary" onClick={() => onNavigate('step2')} style={{ fontSize: '0.8rem', padding: '0.4rem 0.85rem' }}>
            <Edit3 size={14} />
            <span>Consulter les Calculs</span>
          </button>
        </div>

        {allElements.length > 0 ? (
          <table className="custom-table">
            <thead>
              <tr>
                <th>Catégorie</th>
                <th>Identifiant</th>
                <th>Section Dimensionnée</th>
                <th>Armatures / Feraillage</th>
                <th>Statut Verrouillage</th>
              </tr>
            </thead>
            <tbody>
              {allElements.map((item) => (
                <tr key={item.id}>
                  <td><span className="badge badge-info">{item.category}</span></td>
                  <td style={{ fontWeight: 600 }}>{item.id} — {item.name}</td>
                  <td style={{ fontWeight: 700, color: 'var(--accent-emerald)' }}>{item.section}</td>
                  <td>{item.armatures || item.hauteur || '-'}</td>
                  <td>
                    <span className={item.locked ? 'badge badge-locked' : 'badge badge-unlocked'}>
                      {item.locked ? <Lock size={12} /> : <ShieldCheck size={12} />}
                      {item.locked ? 'SECTION VERROUILLÉE' : 'MODIFIABLE'}
                    </span>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        ) : (
          <div style={{ padding: '2rem', textTransform: 'center', textAlign: 'center', color: 'var(--text-muted)' }}>
            Aucun élément calculé pour le moment.
          </div>
        )}
      </div>
    </div>
  );
}
