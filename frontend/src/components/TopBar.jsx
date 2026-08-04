import React from 'react';
import { Search, GitBranch, Plus, Bell, ShieldCheck, HardHat } from 'lucide-react';

export default function TopBar({ projectName, onNewCalculation, lockedCount, totalCount }) {
  return (
    <header className="topbar">
      <div className="topbar-left">
        <div style={{ display: 'flex', alignItems: 'center', gap: '0.65rem' }}>
          <HardHat size={20} color="var(--accent-primary)" />
          <strong style={{ fontSize: '0.95rem', fontWeight: 600 }}>{projectName}</strong>
        </div>

        <div className="search-box">
          <Search size={16} color="var(--text-dim)" />
          <input type="text" placeholder="Rechercher une section, poteau, poutre..." />
        </div>
      </div>

      <div className="topbar-right">
        <div className="badge badge-info" style={{ padding: '0.4rem 0.8rem', fontSize: '0.75rem' }}>
          <GitBranch size={13} />
          <span>feature/frontend-ui</span>
        </div>

        {totalCount > 0 && (
          <div className={`badge ${lockedCount === totalCount ? 'badge-locked' : 'badge-unlocked'}`}>
            <ShieldCheck size={13} />
            <span>{lockedCount}/{totalCount} Verrouillées</span>
          </div>
        )}

        <button className="btn btn-primary" onClick={onNewCalculation} style={{ padding: '0.5rem 1rem', fontSize: '0.825rem' }}>
          <Plus size={16} />
          <span>Nouveau Calcul</span>
        </button>
      </div>
    </header>
  );
}
