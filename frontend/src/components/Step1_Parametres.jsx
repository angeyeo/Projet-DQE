import React, { useState, useEffect } from 'react';
import { UploadCloud, FileText, ArrowRight, Loader2, CheckCircle2, AlertCircle } from 'lucide-react';
import { dqeService } from '../api/dqeService';

const CHARGE_EXPLOITATION_PAR_USAGE = {
  habitation: 1.5,
  bureau: 2.5,
  commercial: 4.0,
};

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
  const [analyzing, setAnalyzing] = useState(false);
  const [analysisError, setAnalysisError] = useState(null);
  const [analysisSuccess, setAnalysisSuccess] = useState(false);

  useEffect(() => {
    if (!projectData.chargeExploitation && projectData.typeUsage) {
      const defaut = CHARGE_EXPLOITATION_PAR_USAGE[projectData.typeUsage];
      if (defaut) updateProjectData({ chargeExploitation: defaut });
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const handleFileUpload = async (e) => {
    const files = e.target.files || e.dataTransfer.files;
    if (!files || !files[0]) return;

    const file = files[0];
    const ext = file.name.split('.').pop().toLowerCase();
    const isImage = ['jpg', 'jpeg', 'png', 'webp'].includes(ext);
    const isIfc = ext === 'ifc';
    const isCAD = ['pln', 'pl', 'pdf'].includes(ext);

    if (!isImage && !isIfc && !isCAD) {
      setAnalysisError("Format non supporté. Veuillez déposer une image (.png, .jpg), un fichier IFC (.ifc) ou ArchiCAD (.pln).");
      return;
    }

    setAnalysisError(null);
    setAnalysisSuccess(false);
    updateProjectData({
      planFileName: file.name,
      planFileSize: (file.size / (1024 * 1024)).toFixed(2) + ' MB',
    });

    // Traitement Vision IA si c'est une image de plan
    if (isImage && projectData.id) {
      setAnalyzing(true);
      try {
        const result = await dqeService.analyserPlanImage(projectData.id, file);
        if (result && result.parametres_detectes) {
          const params = result.parametres_detectes;
          updateProjectData({
            nbTraveesX: params.nb_travees_x || projectData.nbTraveesX,
            nbTraveesY: params.nb_travees_y || projectData.nbTraveesY,
            porteeX: params.portee_x || projectData.porteeX,
            porteeY: params.portee_y || projectData.porteeY,
            nombreNiveaux: params.nombre_niveaux || projectData.nombreNiveaux,
          });
          setAnalysisSuccess(true);
        }
      } catch (err) {
        setAnalysisError(`Erreur d'analyse IA : ${err.message || "Impossible d'extraire le plan"}`);
      } finally {
        setAnalyzing(false);
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
          Importez vos plans d'architecture (Image 2D, `.IFC`, `.PLN`) pour auto-remplir les paramètres ou saisissez-les manuellement.
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
          {analyzing ? <Loader2 size={30} className="spin" /> : <UploadCloud size={30} />}
        </div>

        {analyzing ? (
          <div>
            <h3 style={{ fontSize: '1.1rem', fontWeight: 600, color: 'var(--accent-primary)', marginBottom: '0.25rem' }}>
              Analyse Vision IA du plan en cours...
            </h3>
            <p style={{ fontSize: '0.85rem', color: 'var(--text-muted)' }}>
              Extraction automatique des cotes, travées et niveaux du bâtiment.
            </p>
          </div>
        ) : projectData.planFileName ? (
          <div>
            <div style={{ display: 'inline-flex', alignItems: 'center', gap: '0.5rem', background: 'rgba(16, 185, 129, 0.15)', color: '#6ee7b7', padding: '0.5rem 1rem', borderRadius: '20px', fontWeight: 600 }}>
              <FileText size={16} />
              <span>{projectData.planFileName} ({projectData.planFileSize})</span>
            </div>
            {analysisSuccess && (
              <p style={{ fontSize: '0.85rem', color: '#6ee7b7', marginTop: '0.5rem', display: 'flex', alignItems: 'center', justifyContent: 'center', gap: '0.3rem' }}>
                <CheckCircle2 size={16} /> Paramètres extraits avec succès par l'IA !
              </p>
            )}
            <p style={{ fontSize: '0.8rem', color: 'var(--text-muted)', marginTop: '0.75rem' }}>
              Glissez un nouveau fichier pour remplacer ce plan.
            </p>
          </div>
        ) : (
          <div>
            <h3 style={{ fontSize: '1.1rem', fontWeight: 600, marginBottom: '0.5rem' }}>
              Déposez votre fichier de plan ici (Image, .IFC, .PLN, .PDF)
            </h3>
            <p style={{ fontSize: '0.85rem', color: 'var(--text-muted)', marginBottom: '1.25rem' }}>
              Plans 2D scannés/images, fichiers IFC BIM et exports ArchiCAD supportés.
            </p>
            <label className="btn btn-secondary">
              Parcourir les fichiers
              <input type="file" accept="image/*,.ifc,.pln,.pl,.pdf" onChange={handleFileUpload} style={{ display: 'none' }} />
            </label>
          </div>
        )}
      </div>

      {analysisError && (
        <div style={{ padding: '0.85rem 1rem', borderRadius: '10px', background: 'rgba(239, 68, 68, 0.1)', border: '1px solid rgba(239, 68, 68, 0.35)', marginBottom: '1.5rem', display: 'flex', alignItems: 'center', gap: '0.5rem', color: '#fca5a5', fontSize: '0.88rem' }}>
          <AlertCircle size={18} color="#ef4444" />
          <span>{analysisError}</span>
        </div>
      )}

      {/* Form Fields */}
      <div className="grid-2" style={{ marginBottom: '2rem' }}>
        <div className="form-group">
          <label className="form-label">Nom du Projet BTP</label>
          <input
            type="text"
            className="form-control"
            value={projectData.nomProjet || ''}
            onChange={(e) => updateProjectData({ nomProjet: e.target.value })}
            placeholder="ex: Immeuble R+3 Résidence des Palmes"
          />
        </div>

        <div className="form-group">
          <label className="form-label">N° de Devis (optionnel)</label>
          <input
            type="text"
            className="form-control"
            value={projectData.numeroDevis || ''}
            onChange={(e) => updateProjectData({ numeroDevis: e.target.value })}
            placeholder="ex: 0017-2026"
          />
        </div>

        <div className="form-group">
          <label className="form-label">Usage principal du Bâtiment</label>
          <select
            className="form-select"
            value={projectData.typeUsage || 'habitation'}
            onChange={(e) => {
              const usage = e.target.value;
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
            value={projectData.nombreNiveaux || ''}
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
            value={projectData.nbTraveesX || ''}
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
            value={projectData.porteeX || ''}
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
            value={projectData.nbTraveesY || ''}
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
            value={projectData.porteeY || ''}
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
            value={projectData.hauteurEtage || ''}
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
            value={projectData.chargeExploitation || ''}
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
            value={projectData.norme || 'BAEL91'}
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