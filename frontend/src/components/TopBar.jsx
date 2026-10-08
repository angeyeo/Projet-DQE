import React from 'react';
import { Plus, ShieldCheck, HardHat, FolderKanban } from 'lucide-react';

// La barre de recherche factice (non branchée) a été retirée : un champ
// qui ne fait rien laisse croire à une fonctionnalité inexistante.
export default function TopBar({ projectName, onNewCalculation, onMesProjets, lockedCount, totalCount }) {
  return (
    <header className="topbar">
      <div className="topbar-left">
        <div style={{ display: 'flex', alignItems: 'center', gap: '0.65rem', minWidth: 0 }}>
          <HardHat size={19} color="var(--accent)" aria-hidden="true" />
          <strong className="topbar-projet" title={projectName}>{projectName}</strong>
        </div>
      </div>

      <div className="topbar-right">
        {totalCount > 0 && (
          <div
            className={`badge ${lockedCount === totalCount ? 'badge-locked' : 'badge-unlocked'}`}
            title="Éléments validés par un ingénieur / total"
          >
            <ShieldCheck size={13} aria-hidden="true" />
            <span>{lockedCount}/{totalCount} validés</span>
          </div>
        )}
        <button type="button" className="btn btn-secondary topbar-btn" onClick={onMesProjets}>
          <FolderKanban size={16} aria-hidden="true" />
          <span className="masque-mobile">Mes projets</span>
        </button>
        <button type="button" className="btn btn-primary topbar-btn" onClick={onNewCalculation}>
          <Plus size={16} aria-hidden="true" />
          <span className="masque-mobile">Nouveau projet</span>
        </button>
      </div>
    </header>
  );
}