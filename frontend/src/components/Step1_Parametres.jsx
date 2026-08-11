import React, { useState } from 'react';
import { UploadCloud, FileText, ArrowRight, Layers, Building, HelpCircle } from 'lucide-react';

export default function Step1_Parametres({ projectData, updateProjectData, onNext }) {
  const [dragActive, setDragActive] = useState(false);

  const handleFileUpload = (e) => {
    const files = e.target.files || e.dataTransfer.files;
    if (files && files[0]) {
      const file = files[0];
      const ext = file.name.split('.').pop().toLowerCase();
      if (['pln', 'pl', 'pdf'].includes(ext)) {
        updateProjectData({ planFileName: file.name, planFileSize: (file.size / (1024 * 1024)).toFixed(2) + ' MB' });
      } else {
        alert("Veuillez sélectionner un fichier au format .PLN ou .PL (ou archive associée).");
      }
    }
  };

  return (
    <div className="glass-panel">
      <div style={{ marginBottom: '2rem' }}>
        <h2 style={{ fontSize: '1.5rem', fontWeight: 700, marginBottom: '0.5rem' }}>
          Étape 1 : Chargement des plans & Saisie des paramètres
        </h2>
        <p style={{ color: 'var(--text-muted)', fontSize: '0.9rem' }}>
          Importez les plans d'architecture (`.PLN`, `.PL`) et renseignez les hypothèses de calcul de l'ouvrage.
        </p>
      </div>

      {/* Upload Zone */}
      <div
        className="dropzone"
        onDragOver={(e) => { e.preventDefault(); setDragActive(true); }}
        onDragLeave={() => setDragActive(false)}
        onDrop={(e) => { e.preventDefault(); setDragActive(false); handleFileUpload(e); }}
        style={{ borderColor: dragActive ? 'var(--accent-primary)' : undefined, marginBottom: '2rem' }}
      >
        <div className="dropzone-icon">
          <UploadCloud size={30} />
        </div>
        {projectData.planFileName ? (
          <div>
            <div style={{ display: 'inline-flex', alignItems: 'center', gap: '0.5rem', background: 'rgba(16, 185, 129, 0.15)', color: '#6ee7b7', padding: '0.5rem 1rem', borderRadius: '20px', fontWeight: 600 }}>
              <FileText size={16} />
              <span>{projectData.planFileName} ({projectData.planFileSize})</span>
            </div>
            <p style={{ fontSize: '0.8rem', color: 'var(--text-muted)', marginTop: '0.75rem' }}>
              Plan prêt pour l'assistance à la saisie. Glissez un nouveau fichier pour le remplacer.
            </p>
          </div>
        ) : (
          <div>
            <h3 style={{ fontSize: '1.1rem', fontWeight: 600, marginBottom: '0.5rem' }}>
              Déposez votre fichier de plan ici (.PLN / .PL)
            </h3>
            <p style={{ fontSize: '0.85rem', color: 'var(--text-muted)', marginBottom: '1.25rem' }}>
              Fichiers ArchiCAD .PLN ou archives de projets .PL supportés.
            </p>
            <label className="btn btn-secondary">
              Parcourir les fichiers
              <input type="file" accept=".pln,.pl,.pdf" onChange={handleFileUpload} style={{ display: 'none' }} />
            </label>
          </div>
        )}
      </div>

      {/* Form Fields */}
      <div className="grid-2" style={{ marginBottom: '2rem' }}>
        <div className="form-group">
          <label className="form-label">Nom du Projet BTP</label>
          <input
            type="text"
            className="form-control"
            value={projectData.nomProjet}
            onChange={(e) => updateProjectData({ nomProjet: e.target.value })}
            placeholder="ex: Immeuble R+3 Résidence des Palmes"
          />
        </div>

        <div className="form-group">
          <label className="form-label">Usage principal du Bâtiment</label>
          <select
            className="form-select"
            value={projectData.typeUsage}
            onChange={(e) => updateProjectData({ typeUsage: e.target.value })}
          >
            <option value="habitation">Bâtiment d'Habitation (Q = 1.5 kN/m²)</option>
            <option value="bureau">Bureaux / Tertiaire (Q = 2.5 kN/m²)</option>
            <option value="commercial">Local Commercial / Stockage (Q = 4.0 kN/m²)</option>
          </select>
        </div>

        <div className="form-group">
          <label className="form-label">Nombre de Niveaux (Étages)</label>
          <input
            type="number"
            min="1"
            max="20"
            className="form-control"
            value={projectData.nombreNiveaux}
            onChange={(e) => updateProjectData({ nombreNiveaux: e.target.value })}
          />
        </div>

        <div className="form-group">
          <label className="form-label">Portée Maximale des Poutres (<i>L</i> en m)</label>
          <input
            type="number"
            step="0.1"
            className="form-control"
            value={projectData.porteeMax}
            onChange={(e) => updateProjectData({ porteeMax: e.target.value })}
            placeholder="ex: 5.5"
          />
        </div>

        <div className="form-group">
          <label className="form-label">Charge d'Exploitation (<i>Q</i> en kN/m²)</label>
          <input
            type="number"
            step="0.1"
            className="form-control"
            value={projectData.chargeExploitation}
            onChange={(e) => updateProjectData({ chargeExploitation: e.target.value })}
          />
        </div>

        <div className="form-group">
          <label className="form-label">Norme de Calcul Structurel</label>
          <select
            className="form-select"
            value={projectData.norme}
            onChange={(e) => updateProjectData({ norme: e.target.value })}
          >
            <option value="BAEL91">BAEL 91 Révisé 99 (Norme Française / CIPEC)</option>
            <option value="Eurocode2">Eurocode 2 (NF EN 1992-1-1)</option>
          </select>
        </div>
      </div>

      <div style={{ display: 'flex', justifyContent: 'flex-end' }}>
        <button className="btn btn-primary" onClick={onNext}>
          <span>Lancer la Descente de Charge & Calculs</span>
          <ArrowRight size={18} />
        </button>
      </div>
    </div>
  );
}
