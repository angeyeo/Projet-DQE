import React from 'react';
import { Building2, GitBranch, ShieldCheck, User } from 'lucide-react';

export default function Header({ projectName, lockedCount, totalCount }) {
  return (
    <header className="app-header">
      <div className="brand-logo">
        <div className="brand-icon">
          <Building2 size={24} />
        </div>
        <div>
          <h1 className="brand-title">Projet DQE</h1>
          <p className="brand-subtitle">Pré-dimensionnement Structurel Assisté & DEK</p>
        </div>
      </div>

      <div style={{ display: 'flex', alignItems: 'center', gap: '1rem' }}>
        <div className="badge badge-info" style={{ gap: '0.4rem', padding: '0.4rem 0.8rem' }}>
          <GitBranch size={14} />
          <span>branche: feature/frontend-ui</span>
        </div>

        {totalCount > 0 && (
          <div className={`badge ${lockedCount === totalCount ? 'badge-locked' : 'badge-unlocked'}`}>
            <ShieldCheck size={14} />
            <span>{lockedCount} / {totalCount} Sections Verrouillées</span>
          </div>
        )}

        <div className="user-badge">
          <div className="avatar">YA</div>
          <div>
            <div className="user-name">Yves Arthur Ané</div>
            <div className="user-role">Ingénieur Frontend / Dev</div>
          </div>
        </div>
      </div>
    </header>
  );
}
