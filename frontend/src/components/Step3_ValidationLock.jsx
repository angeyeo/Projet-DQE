import React from 'react';
import { Lock, Unlock, CheckCircle, ShieldAlert, ArrowLeft, ArrowRight, Edit3, ShieldCheck } from 'lucide-react';

export default function Step3_ValidationLock({ sections, toggleLock, toggleLockAll, updateSection, onBack, onNext }) {
  const { poteaux = [], poutres = [], semelles = [] } = sections || {};

  const allElements = [
    ...poteaux.map(p => ({ ...p, category: 'Poteau' })),
    ...poutres.map(p => ({ ...p, category: 'Poutre' })),
    ...semelles.map(s => ({ ...s, category: 'Semelle' })),
  ];

  const lockedCount = allElements.filter(e => e.locked).length;
  const isAllLocked = lockedCount === allElements.length;

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

        <button
          className={`btn ${isAllLocked ? 'btn-warning' : 'btn-success'}`}
          onClick={() => toggleLockAll(!isAllLocked)}
        >
          {isAllLocked ? <Unlock size={18} /> : <Lock size={18} />}
          <span>{isAllLocked ? 'Déverrouiller Tout' : 'Verrouiller Toutes les Sections'}</span>
        </button>
      </div>

      {/* Banner de Sécurité */}
      <div
        style={{
          padding: '1.25rem 1.5rem',
          borderRadius: '14px',
          background: isAllLocked ? 'rgba(16, 185, 129, 0.1)' : 'rgba(245, 158, 11, 0.1)',
          border: `1px solid ${isAllLocked ? 'rgba(16, 185, 129, 0.3)' : 'rgba(245, 158, 11, 0.3)'}`,
          marginBottom: '2rem',
          display: 'flex',
          alignItems: 'center',
          gap: '1rem',
        }}
      >
        {isAllLocked ? (
          <ShieldCheck size={28} color="#10b981" />
        ) : (
          <ShieldAlert size={28} color="#f59e0b" />
        )}
        <div>
          <h4 style={{ fontSize: '1rem', fontWeight: 600, color: isAllLocked ? '#6ee7b7' : '#fcd34d' }}>
            {isAllLocked ? 'Projet Intégralement Verrouillé & Validé' : 'Validation Ingénieur en cours'}
          </h4>
          <p style={{ fontSize: '0.85rem', color: 'var(--text-muted)' }}>
            {isAllLocked
              ? 'Toutes les sections sont verrouillées. Aucune modification non autorisée ne peut intervenir lors de l\'exportation du devis.'
              : `${lockedCount} sur ${allElements.length} sections verrouillées. Cliquez sur le cadenas à droite de chaque ligne pour la verrouiller.`}
          </p>
        </div>
      </div>

      {/* Liste interactive des éléments avec Verrouillage */}
      <div style={{ marginBottom: '2.5rem' }}>
        <h3 style={{ fontSize: '1.1rem', fontWeight: 600, marginBottom: '1rem' }}>
          Gestion et Verrouillage Éléments par Éléments
        </h3>

        {allElements.map((item) => (
          <div key={item.id} className={`element-card ${item.locked ? 'is-locked' : ''}`}>
            <div className="element-card-header">
              <div style={{ display: 'flex', alignItems: 'center', gap: '0.75rem' }}>
                <span className="badge badge-info">{item.category}</span>
                <strong style={{ fontSize: '1rem' }}>{item.id} — {item.name}</strong>
              </div>

              <div style={{ display: 'flex', alignItems: 'center', gap: '1rem' }}>
                <span className={item.locked ? 'badge badge-locked' : 'badge badge-unlocked'}>
                  {item.locked ? <Lock size={12} /> : <Unlock size={12} />}
                  {item.locked ? 'SECTION VERROUILLÉE' : 'MODIFIABLE'}
                </span>

                <button
                  className={`btn ${item.locked ? 'btn-secondary' : 'btn-success'}`}
                  style={{ padding: '0.4rem 0.8rem', fontSize: '0.8rem' }}
                  onClick={() => toggleLock(item.id, item.category)}
                >
                  {item.locked ? <Unlock size={14} /> : <Lock size={14} />}
                  <span>{item.locked ? 'Déverrouiller' : 'Valider & Verrouiller'}</span>
                </button>
              </div>
            </div>

            <div className="grid-3" style={{ alignItems: 'center' }}>
              <div>
                <label className="form-label">Section Dimensionnée (b x h)</label>
                <input
                  type="text"
                  className="form-control"
                  value={item.section}
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

              <div style={{ fontSize: '0.85rem', color: 'var(--text-muted)', background: 'rgba(15, 23, 42, 0.4)', padding: '0.75rem', borderRadius: '8px' }}>
                {item.locked ? (
                  <span style={{ color: '#fca5a5', display: 'flex', alignItems: 'center', gap: '0.35rem' }}>
                    <Lock size={14} /> Section figée par l'ingénieur
                  </span>
                ) : (
                  <span style={{ color: '#6ee7b7', display: 'flex', alignItems: 'center', gap: '0.35rem' }}>
                    <Edit3 size={14} /> Saisie manuelle autorisée avant verrou
                  </span>
                )}
              </div>
            </div>
          </div>
        ))}
      </div>

      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
        <button className="btn btn-secondary" onClick={onBack}>
          <ArrowLeft size={18} />
          <span>Retour aux calculs</span>
        </button>

        <button className="btn btn-primary" onClick={onNext}>
          <span>Générer le Devis Quantitatif (DQE)</span>
          <ArrowRight size={18} />
        </button>
      </div>
    </div>
  );
}
