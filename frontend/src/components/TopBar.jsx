import React from 'react';
import { Search, Plus, ShieldCheck, HardHat } from 'lucide-react';

export default function TopBar({ projectName, onNewCalculation, lockedCount, totalCount }) {
  return (
    <header className="topbar">
      <div className="topbar-left">
        <div style={{ display: 'flex', alignItems: 'center', gap: '0.65rem' }}>
          <HardHat size={19} color="var(--accent)" />
          <strong style={{ fontSize: '0.9rem', fontWeight: 600 }}>{projectName}</strong>
        </div>

        <div className="search-box">
          <Search size={15} color="var(--ink-300)" />
          <input type="text" placeholder="Rechercher une section, poteau, poutre..." />
        </div>
      </div>

      <div className="topbar-right">
        {totalCount > 0 && (
          <div className={`badge ${lockedCount === totalCount ? 'badge-locked' : 'badge-unlocked'}`}>
            <ShieldCheck size={13} />
            <span>{lockedCount}/{totalCount} Verrouillées</span>
          </div>
        )}

        <button className="btn btn-primary" onClick={onNewCalculation} style={{ padding: '0.5rem 1rem', fontSize: '0.82rem' }}>
          <Plus size={16} />
          <span>Nouveau Calcul</span>
        </button>
      </div>
    </header>
  );
}