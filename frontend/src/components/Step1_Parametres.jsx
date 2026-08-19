import React, { useState, useEffect } from 'react';
import { UploadCloud, FileText, ArrowRight, Layers, Building, HelpCircle } from 'lucide-react';

// AJOUTÉ : charge d'exploitation réglementaire standard associée à
// chaque usage (mêmes valeurs que celles annoncées dans le libellé du
// menu déroulant "Usage principal du Bâtiment", jusqu'ici purement
// indicatives et jamais réellement appliquées au champ "Charge
// d'Exploitation" -- source probable des charges aberrantes observées
// (ex: Q laissé incohérent avec l'usage sélectionné).
const CHARGE_EXPLOITATION_PAR_USAGE = {
  habitation: 1.5,
  bureau: 2.5,
  commercial: 4.0,
};

// AJOUTÉ : plages réalistes (BAEL / pratique courante BTP) pour éviter
// une saisie aberrante (ex: 12341 au lieu de 1.5) qui se propage en
// cascade jusqu'à des sections de poteaux/semelles de plusieurs mètres
// sans qu'aucune erreur ne soit jamais levée.
const LIMITES = {
  nombreNiveaux: { min: 1, max: 20 },
  nbTraveesX: { min: 1, max: 10 },
  nbTraveesY: { min: 1, max: 10 },
  porteeX: { min: 1.5, max: 15 },
  porteeY: { min: 1.5, max: 15 },
  chargeExploitation: { min: 0.5, max: 20 },
  hauteurEtage: { min: 2.4, max: 4.5 },
};

const clamp = (value, { min, max }) => {
  if (value === '' || value === null || value === undefined) return value;
  const n = parseFloat(value);
  if (Number.isNaN(n)) return value;
  return Math.min(max, Math.max(min, n));
};

export default function Step1_Parametres({ projectData, updateProjectData, onNext }) {
  const [dragActive, setDragActive] = useState(false);

  // AJOUTÉ : pré-remplit la charge d'exploitation au chargement si elle
  // est vide, avec la valeur standard de l'usage déjà sélectionné par
  // défaut (habitation), au lieu de laisser le champ vide jusqu'à ce
  // que l'utilisateur y pense.
  useEffect(() => {
    if (!projectData.chargeExploitation && projectData.typeUsage) {
      const defaut = CHARGE_EXPLOITATION_PAR_USAGE[projectData.typeUsage];
      if (defaut) updateProjectData({ chargeExploitation: defaut });
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

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
            onChange={(e) => {
              const usage = e.target.value;
              // CORRIGÉ : le libellé de l'option affiche "Q = 1.5 kN/m²"
              // etc. mais ne mettait jamais réellement à jour le champ
              // "Charge d'Exploitation" -- l'utilisateur pouvait donc
              // choisir "Habitation" tout en gardant une charge
              // d'exploitation incohérente (vide ou tapée par erreur).
              updateProjectData({
                typeUsage: usage,
                chargeExploitation: CHARGE_EXPLOITATION_PAR_USAGE[usage],
              });
            }}
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
            min={LIMITES.nombreNiveaux.min}
            max={LIMITES.nombreNiveaux.max}
            className="form-control"
            value={projectData.nombreNiveaux}
            onChange={(e) => updateProjectData({ nombreNiveaux: e.target.value })}
            onBlur={(e) => updateProjectData({ nombreNiveaux: clamp(e.target.value, LIMITES.nombreNiveaux) })}
          />
          <p style={{ fontSize: '0.75rem', color: 'var(--text-muted)', marginTop: '0.3rem' }}>
            Plage acceptée : {LIMITES.nombreNiveaux.min} à {LIMITES.nombreNiveaux.max} niveaux
          </p>
        </div>

        <div className="form-group">
          <label className="form-label">Nombre de travées — Direction X</label>
          <input
            type="number"
            min={LIMITES.nbTraveesX.min}
            max={LIMITES.nbTraveesX.max}
            className="form-control"
            value={projectData.nbTraveesX}
            onChange={(e) => updateProjectData({ nbTraveesX: e.target.value })}
            onBlur={(e) => updateProjectData({ nbTraveesX: clamp(e.target.value, LIMITES.nbTraveesX) })}
            placeholder="ex: 2"
          />
          <p style={{ fontSize: '0.75rem', color: 'var(--text-muted)', marginTop: '0.3rem' }}>
            Plage acceptée : {LIMITES.nbTraveesX.min} à {LIMITES.nbTraveesX.max} travées
          </p>
        </div>

        <div className="form-group">
          <label className="form-label">Portée en X (m)</label>
          <input
            type="number"
            step="0.1"
            min={LIMITES.porteeX.min}
            max={LIMITES.porteeX.max}
            className="form-control"
            value={projectData.porteeX}
            onChange={(e) => updateProjectData({ porteeX: e.target.value })}
            onBlur={(e) => updateProjectData({ porteeX: clamp(e.target.value, LIMITES.porteeX) })}
            placeholder="ex: 5.0"
          />
          <p style={{ fontSize: '0.75rem', color: 'var(--text-muted)', marginTop: '0.3rem' }}>
            Plage acceptée : {LIMITES.porteeX.min} à {LIMITES.porteeX.max} m
          </p>
        </div>

        <div className="form-group">
          <label className="form-label">Nombre de travées — Direction Y</label>
          <input
            type="number"
            min={LIMITES.nbTraveesY.min}
            max={LIMITES.nbTraveesY.max}
            className="form-control"
            value={projectData.nbTraveesY}
            onChange={(e) => updateProjectData({ nbTraveesY: e.target.value })}
            onBlur={(e) => updateProjectData({ nbTraveesY: clamp(e.target.value, LIMITES.nbTraveesY) })}
            placeholder="ex: 2"
          />
          <p style={{ fontSize: '0.75rem', color: 'var(--text-muted)', marginTop: '0.3rem' }}>
            Plage acceptée : {LIMITES.nbTraveesY.min} à {LIMITES.nbTraveesY.max} travées
          </p>
        </div>

        <div className="form-group">
          <label className="form-label">Portée en Y (m)</label>
          <input
            type="number"
            step="0.1"
            min={LIMITES.porteeY.min}
            max={LIMITES.porteeY.max}
            className="form-control"
            value={projectData.porteeY}
            onChange={(e) => updateProjectData({ porteeY: e.target.value })}
            onBlur={(e) => updateProjectData({ porteeY: clamp(e.target.value, LIMITES.porteeY) })}
            placeholder="ex: 5.0"
          />
          <p style={{ fontSize: '0.75rem', color: 'var(--text-muted)', marginTop: '0.3rem' }}>
            Plage acceptée : {LIMITES.porteeY.min} à {LIMITES.porteeY.max} m
          </p>
        </div>

        <div className="form-group" style={{ gridColumn: 'span 2' }}>
          <p style={{ fontSize: '0.85rem', fontWeight: 600, color: 'var(--accent-primary)', background: '#eff6ff', border: '1px solid #bfdbfe', padding: '0.5rem 1rem', borderRadius: '8px', display: 'inline-block' }}>
            Aperçu Trame : Grille de {(parseInt(projectData.nbTraveesX || 0) + 1) * (parseInt(projectData.nbTraveesY || 0) + 1)} poteaux ({projectData.nbTraveesX || 0}x{projectData.nbTraveesY || 0} travées)
          </p>
        </div>

        <div className="form-group">
          <label className="form-label">Hauteur d'Étage (m)</label>
          <input
            type="number"
            step="0.1"
            min={LIMITES.hauteurEtage.min}
            max={LIMITES.hauteurEtage.max}
            className="form-control"
            value={projectData.hauteurEtage}
            onChange={(e) => updateProjectData({ hauteurEtage: e.target.value })}
            onBlur={(e) => updateProjectData({ hauteurEtage: clamp(e.target.value, LIMITES.hauteurEtage) })}
            placeholder="ex: 3.0"
          />
          <p style={{ fontSize: '0.75rem', color: 'var(--text-muted)', marginTop: '0.3rem' }}>
            Plage acceptée : {LIMITES.hauteurEtage.min} à {LIMITES.hauteurEtage.max} m
          </p>
        </div>

        <div className="form-group">
          <label className="form-label">Charge d'Exploitation (Q en kN/m²)</label>
          <input
            type="number"
            step="0.1"
            min={LIMITES.chargeExploitation.min}
            max={LIMITES.chargeExploitation.max}
            className="form-control"
            value={projectData.chargeExploitation}
            onChange={(e) => updateProjectData({ chargeExploitation: e.target.value })}
            onBlur={(e) => updateProjectData({ chargeExploitation: clamp(e.target.value, LIMITES.chargeExploitation) })}
          />
          <p style={{ fontSize: '0.75rem', color: 'var(--text-muted)', marginTop: '0.3rem' }}>
            Plage acceptée : {LIMITES.chargeExploitation.min} à {LIMITES.chargeExploitation.max} kN/m² · pré-remplie selon l'usage, modifiable
          </p>
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