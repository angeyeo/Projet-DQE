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
  const [analysisWarnings, setAnalysisWarnings] = useState([]);

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
    const isImage = ['jpg', 'jpeg', 'png'].includes(ext);
    const isIfc = ext === 'ifc';
    const isCAD = ['pln', 'pl', 'pdf'].includes(ext);

    if (!isImage && !isIfc && !isCAD) {
      setAnalysisError("Format non supporté. Veuillez déposer une image (.png, .jpg), un fichier IFC (.ifc) ou ArchiCAD (.pln).");
      return;
    }

    setAnalysisError(null);
    setAnalysisSuccess(false);
    setAnalysisWarnings([]);
    updateProjectData({
      planFileName: file.name,
      planFileSize: (file.size / (1024 * 1024)).toFixed(2) + ' MB',
    });

    // Import IFC : aperçu Phase A -- détection des paramètres de trame,
    // pré-remplissage du formulaire (aucun ElementStructurel créé ici).
    if (isIfc) {
      setAnalyzing(true);
      setAnalysisError(null);
      try {
        let projetId = projectData.id;
        if (!projetId) {
          const projet = await dqeService.createProjet(projectData);
          projetId = projet.id;
          updateProjectData({ id: projetId });
        }

        const params = await dqeService.importerPlanIFC(projetId, file);
        updateProjectData({
          nbTraveesX: params.nb_travees_x ?? projectData.nbTraveesX,
          nbTraveesY: params.nb_travees_y ?? projectData.nbTraveesY,
          porteeX: params.portee_x ?? projectData.porteeX,
          porteeY: params.portee_y ?? projectData.porteeY,
          nombreNiveaux: params.nb_niveaux ?? projectData.nombreNiveaux,
          hauteurEtage: params.hauteur_etage ?? projectData.hauteurEtage,
          ifcImporte: true,
        });
        // Le backend (detecter_parametres_trame) calcule des avertissements
        // explicites quand la grille détectée est irrégulière (nb de poteaux
        // incohérent avec une grille parfaite, portées ou hauteurs d'étage trop
        // variables...). Ils existaient déjà côté API mais n'étaient jamais
        // affichés : l'utilisateur voyait "575 poteaux" comme une donnée fiable
        // alors que le fichier n'en contenait réellement que 72, sans aucune
        // indication que la grille était une approximation.
        setAnalysisWarnings(params.avertissements || []);
        setAnalysisSuccess(true);
      } catch (err) {
        setAnalysisError(`Erreur d'import IFC : ${err.message || "Impossible d'extraire le plan"}`);
      } finally {
        setAnalyzing(false);
      }
      return;
    }

    // Traitement Vision IA si c'est une image de plan (Aperçu uniquement, aucune mutation des paramètres du projet)
    if (isImage) {
      setAnalyzing(true);
      setAnalysisError(null);
      try {
        let projetId = projectData.id;
        if (!projetId) {
          const projet = await dqeService.createProjet(projectData);
          projetId = projet.id;
          updateProjectData({ id: projetId });
        }

        const result = await dqeService.analyserPlanImage(projetId, file);
        updateProjectData({ visionResult: result });
        setAnalysisSuccess(true);
      } catch (err) {
        setAnalysisError(`Erreur d'analyse IA : ${err.message || "Impossible d'extraire le plan"}`);
      } finally {
        setAnalyzing(false);
      }
    }
  };

  const vision = projectData.visionResult;

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
                <CheckCircle2 size={16} /> Annotations du plan détectées automatiquement — vérification humaine requise.
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
              <input type="file" accept="image/png,image/jpeg,.ifc,.pln,.pl,.pdf" onChange={handleFileUpload} style={{ display: 'none' }} />
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

      {/* Gemini Vision Results Panel */}
      {vision && (
        <div style={{ padding: '1.25rem', borderRadius: '12px', background: 'rgba(15, 23, 42, 0.6)', border: '1px solid rgba(59, 130, 246, 0.3)', marginBottom: '2rem' }}>
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '1rem', flexWrap: 'wrap', gap: '0.5rem' }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: '0.6rem' }}>
              <FileText size={20} color="#60a5fa" />
              <h4 style={{ fontSize: '1.05rem', fontWeight: 700, margin: 0, color: '#f8fafc' }}>
                Éléments détectés sur le plan (Aperçu Vision)
              </h4>
            </div>
            <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
              <span style={{ fontSize: '0.75rem', fontWeight: 600, padding: '0.25rem 0.6rem', borderRadius: '12px', background: vision.source === 'GEMINI' ? 'rgba(99, 102, 241, 0.2)' : 'rgba(245, 158, 11, 0.2)', color: vision.source === 'GEMINI' ? '#a5b4fc' : '#fcd34d', border: vision.source === 'GEMINI' ? '1px solid rgba(99, 102, 241, 0.4)' : '1px solid rgba(245, 158, 11, 0.4)' }}>
                Source : {vision.source || 'GEMINI'}
              </span>
              {vision.validation_humaine_requise && (
                <span style={{ fontSize: '0.75rem', color: '#94a3b8', fontStyle: 'italic' }}>
                  Une vérification humaine est requise.
                </span>
              )}
            </div>
          </div>

          {vision.source === 'FALLBACK_LOCAL' && (
            <div style={{ padding: '0.75rem 1rem', borderRadius: '8px', background: 'rgba(245, 158, 11, 0.1)', border: '1px solid rgba(245, 158, 11, 0.3)', marginBottom: '1rem', color: '#fcd34d', fontSize: '0.85rem' }}>
              L'analyse automatique du plan n'est pas disponible pour le moment.
            </div>
          )}

          {/* Annotations lues */}
          {Array.isArray(vision.annotations_lues) && vision.annotations_lues.length > 0 ? (
            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(220px, 1fr))', gap: '0.75rem', marginBottom: '1rem' }}>
              {vision.annotations_lues.map((ann, idx) => (
                <div key={idx} style={{ padding: '0.75rem', borderRadius: '8px', background: 'rgba(30, 41, 59, 0.7)', border: '1px solid rgba(148, 163, 184, 0.15)' }}>
                  <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '0.25rem' }}>
                    <span style={{ fontWeight: 700, fontSize: '0.95rem', color: '#38bdf8' }}>{ann.repere || ann.texte_lu}</span>
                    <span style={{ fontSize: '0.75rem', textTransform: 'capitalize', padding: '0.15rem 0.4rem', borderRadius: '4px', background: 'rgba(56, 189, 248, 0.15)', color: '#7dd3fc' }}>
                      {ann.type_normalise || 'Élément'}
                    </span>
                  </div>
                  {ann.dimensions_parsees && Array.isArray(ann.dimensions_parsees.valeurs) && ann.dimensions_parsees.valeurs.length > 0 && (
                    <div style={{ fontSize: '0.8rem', color: '#cbd5e1', marginTop: '0.25rem' }}>
                      Dimensions : {ann.dimensions_parsees.valeurs.join(' × ')} {ann.dimensions_parsees.unite || ''}
                    </div>
                  )}
                </div>
              ))}
            </div>
          ) : (
            <p style={{ fontSize: '0.85rem', color: '#94a3b8', margin: 0 }}>Aucun élément reconnu avec certitude sur ce plan.</p>
          )}

          {/* Textes non classés */}
          {Array.isArray(vision.textes_non_classes) && vision.textes_non_classes.length > 0 && (
            <div style={{ marginTop: '1rem', paddingTop: '0.75rem', borderTop: '1px solid rgba(148, 163, 184, 0.15)' }}>
              <div style={{ fontSize: '0.8rem', fontWeight: 600, color: '#94a3b8', marginBottom: '0.5rem' }}>
                Textes détectés non classés :
              </div>
              <div style={{ display: 'flex', flexWrap: 'wrap', gap: '0.4rem' }}>
                {vision.textes_non_classes.map((txt, idx) => (
                  <span key={idx} style={{ fontSize: '0.75rem', background: 'rgba(51, 65, 85, 0.6)', color: '#cbd5e1', padding: '0.2rem 0.5rem', borderRadius: '4px', border: '1px solid rgba(148, 163, 184, 0.2)' }}>
                    {txt}
                  </span>
                ))}
              </div>
            </div>
          )}
        </div>
      )}

      {analysisWarnings.length > 0 && (
        <div style={{ padding: '0.85rem 1rem', borderRadius: '10px', background: 'rgba(245, 158, 11, 0.1)', border: '1px solid rgba(245, 158, 11, 0.35)', marginBottom: '1.5rem', color: '#fcd34d', fontSize: '0.85rem' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', fontWeight: 600, marginBottom: '0.5rem' }}>
            <AlertCircle size={18} color="#f59e0b" />
            <span>Trame détectée approximative -- à vérifier avant de continuer</span>
          </div>
          <ul style={{ margin: 0, paddingLeft: '1.4rem' }}>
            {analysisWarnings.map((w, idx) => (
              <li key={idx} style={{ marginBottom: '0.3rem' }}>{w}</li>
            ))}
          </ul>
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