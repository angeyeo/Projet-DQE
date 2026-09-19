import React, { useState, useEffect } from 'react';
import { UploadCloud, FileText, ArrowRight, Loader2, CheckCircle2, AlertCircle, Sparkles } from 'lucide-react';
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

  // Vision IA -- résultat brut renvoyé par /projets/{id}/analyser_plan_image/ :
  // une liste d'annotations OCR lues sur l'image (pas des nb_travees_x/y).
  const [visionAnnotations, setVisionAnnotations] = useState([]);
  const [visionMessage, setVisionMessage] = useState(null);
  const [visionSource, setVisionSource] = useState(null);

  // Structuration NLP -- description libre du projet analysée par l'IA
  // (POST /assistant/structurer-projet/), jamais câblée à aucune UI avant.
  const [nlpDescription, setNlpDescription] = useState('');
  const [nlpLoading, setNlpLoading] = useState(false);
  const [nlpError, setNlpError] = useState(null);
  const [nlpResult, setNlpResult] = useState(null);

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

    // Traitement Vision IA si c'est une image de plan.
    // Le backend (projets/services/assistant_ia/vision.py::analyser_plan_2d)
    // ne renvoie PAS de nb_travees_x/y : il renvoie une lecture OCR brute des
    // annotations visibles sur l'image (repère + dimensions entre parenthèses,
    // ex: "S1(170x170x40)"), à charge pour l'ingénieur de les reporter
    // manuellement. L'ancien code attendait `result.parametres_detectes`, un
    // champ qui n'existe pas dans la réponse -- la condition ne se déclenchait
    // donc jamais et rien ne s'affichait, en plus du crash sur la fonction
    // manquante.
    if (isImage && projectData.id) {
      setAnalyzing(true);
      setVisionAnnotations([]);
      setVisionMessage(null);
      setVisionSource(null);
      try {
        const result = await dqeService.analyserPlanImage(projectData.id, file);
        setVisionAnnotations(result?.annotations_lues || []);
        setVisionMessage(result?.message || null);
        setVisionSource(result?.source || null);
        setAnalysisSuccess((result?.annotations_lues || []).length > 0);
      } catch (err) {
        setAnalysisError(`Erreur d'analyse IA : ${err.message || "Impossible d'extraire le plan"}`);
      } finally {
        setAnalyzing(false);
      }
    }
  };

  const handleStructurerIA = async () => {
    if (!nlpDescription.trim()) return;
    setNlpLoading(true);
    setNlpError(null);
    setNlpResult(null);
    try {
      const res = await dqeService.structurerProjetIA(nlpDescription.trim());
      setNlpResult(res);

      const usageMap = { HABITATION: 'habitation', BUREAU: 'bureau', COMMERCE: 'commercial' };
      const patch = {};
      if (res.nombre_niveaux != null) patch.nombreNiveaux = res.nombre_niveaux;
      if (res.usage && usageMap[res.usage]) {
        patch.typeUsage = usageMap[res.usage];
        patch.chargeExploitation = CHARGE_EXPLOITATION_PAR_USAGE[usageMap[res.usage]];
      }
      if (res.portee_m != null) {
        patch.porteeX = res.portee_m;
        patch.porteeY = res.portee_m;
      }
      if (res.hauteur_niveau_m != null) patch.hauteurEtage = res.hauteur_niveau_m;
      updateProjectData(patch);
    } catch (err) {
      setNlpError(err.message || "Impossible de structurer la description.");
    } finally {
      setNlpLoading(false);
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
                <CheckCircle2 size={16} /> Paramètres extraits automatiquement, à vérifier ci-dessous !
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

      {visionAnnotations.length > 0 && (
        <div style={{ padding: '0.85rem 1rem', borderRadius: '10px', background: 'rgba(99, 102, 241, 0.08)', border: '1px solid rgba(99, 102, 241, 0.25)', marginBottom: '1.5rem', fontSize: '0.85rem' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', fontWeight: 600, marginBottom: '0.5rem', color: '#a5b4fc' }}>
            <Sparkles size={18} />
            <span>Vision IA -- annotations lues sur l'image ({visionSource === 'MOCK' ? 'mode démo' : 'Gemini'})</span>
          </div>
          <table className="custom-table">
            <thead>
              <tr>
                <th>Repère</th>
                <th>Texte lu</th>
                <th>Type</th>
                <th>Dimensions</th>
              </tr>
            </thead>
            <tbody>
              {visionAnnotations.map((a, idx) => (
                <tr key={idx}>
                  <td>{a.repere || '—'}</td>
                  <td>{a.texte_lu}</td>
                  <td>{a.type_normalise || 'n/d'}</td>
                  <td>
                    {a.dimensions_parsees?.valeurs
                      ? a.dimensions_parsees.valeurs.join(' x ')
                      : '—'}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
          <p style={{ color: 'var(--text-muted)', marginTop: '0.5rem' }}>
            Ces lectures doivent être vérifiées par l'ingénieur avant report dans les champs ci-dessous.
          </p>
        </div>
      )}

      {visionMessage && (
        <div style={{ padding: '0.85rem 1rem', borderRadius: '10px', background: 'rgba(245, 158, 11, 0.1)', border: '1px solid rgba(245, 158, 11, 0.35)', marginBottom: '1.5rem', color: '#fcd34d', fontSize: '0.85rem' }}>
          {visionMessage}
        </div>
      )}

      {/* Structuration NLP -- Assistant IA */}
      <div style={{ background: 'rgba(99, 102, 241, 0.08)', border: '1px solid rgba(99, 102, 241, 0.25)', borderRadius: '14px', padding: '1.25rem', marginBottom: '2rem' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', marginBottom: '0.75rem' }}>
          <Sparkles size={18} color="#a5b4fc" />
          <h4 style={{ fontSize: '0.95rem', fontWeight: 600, color: '#a5b4fc' }}>
            Décrire le projet en langage naturel (Assistant IA)
          </h4>
        </div>
        <textarea
          className="form-control"
          rows={3}
          placeholder="ex : Bâtiment R+2 commercial avec des portées de 6 mètres."
          value={nlpDescription}
          onChange={(e) => setNlpDescription(e.target.value)}
          style={{ marginBottom: '0.75rem', resize: 'vertical' }}
        />
        <button
          className="btn btn-secondary"
          disabled={nlpLoading || !nlpDescription.trim()}
          onClick={handleStructurerIA}
        >
          {nlpLoading ? <Loader2 size={16} className="spin" /> : <Sparkles size={16} />}
          <span>{nlpLoading ? 'Analyse en cours...' : 'Structurer avec l\'IA'}</span>
        </button>

        {nlpError && (
          <p style={{ color: '#fca5a5', fontSize: '0.85rem', marginTop: '0.75rem' }}>{nlpError}</p>
        )}

        {nlpResult && (
          <div style={{ marginTop: '1rem', fontSize: '0.85rem' }}>
            <p style={{ color: '#6ee7b7', display: 'flex', alignItems: 'center', gap: '0.3rem' }}>
              <CheckCircle2 size={16} /> Paramètres détectés et pré-remplis ci-dessous ({nlpResult.source === 'MOCK' ? 'mode démo' : 'Gemini'}).
            </p>
            {nlpResult.contrainte_sol_kn_m2 != null && (
              <p style={{ color: 'var(--text-muted)' }}>
                Contrainte de sol évoquée : {nlpResult.contrainte_sol_kn_m2} kN/m² (aucun champ dédié -- à noter manuellement).
              </p>
            )}
            {nlpResult.donnees_manquantes?.length > 0 && (
              <p style={{ color: '#fcd34d' }}>
                Données manquantes à compléter : {nlpResult.donnees_manquantes.join(', ')}
              </p>
            )}
            {nlpResult.avertissements?.length > 0 && (
              <ul style={{ margin: '0.3rem 0 0', paddingLeft: '1.4rem', color: '#fcd34d' }}>
                {nlpResult.avertissements.map((w, idx) => <li key={idx}>{w}</li>)}
              </ul>
            )}
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