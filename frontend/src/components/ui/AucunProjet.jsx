import React from 'react';
import { FolderOpen, Plus } from 'lucide-react';

export default function AucunProjet({ onOuvrir, onNouveau }) {
  return (
    <div className="glass-panel etat-vide">
      <FolderOpen size={36} color="var(--ink-300)" aria-hidden="true" />
      <h2>Aucun projet ouvert</h2>
      <p>Cette étape s'applique à un projet. Ouvrez un projet existant ou démarrez-en un nouveau.</p>
      <div className="etat-vide-actions">
        <button type="button" className="btn btn-secondary" onClick={onOuvrir}>
          <FolderOpen size={16} /> <span>Mes projets</span>
        </button>
        <button type="button" className="btn btn-primary" onClick={onNouveau}>
          <Plus size={16} /> <span>Nouveau projet</span>
        </button>
      </div>
    </div>
  );
}
