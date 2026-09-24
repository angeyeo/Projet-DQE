import React, { useState, useEffect } from 'react';
import { ArrowLeft, ArrowRight, Download, CheckCircle, AlertTriangle, Grid, FileText, Layers } from 'lucide-react';
import { dqeService } from '../api/dqeService';

export default function StepPlanFondation({ projetId, sections, onBack, onNext }) {
  const [planData, setPlanData] = useState(null);
  const [loading, setLoading] = useState(false);
  const [downloadingDxf, setDownloadingDxf] = useState(false);
  const [downloadingPdf, setDownloadingPdf] = useState(false);
  const [validating, setValidating] = useState(false);
  const [errorMsg, setErrorMsg] = useState(null);
  const [pdfPreviewUrl, setPdfPreviewUrl] = useState(null);

  useEffect(() => {
    if (projetId) {
      chargerPlanFondation();
      chargerApercuPdf();
    }

    // Nettoyage de l'URL Blob en mémoire à la destruction du composant
    return () => {
      if (pdfPreviewUrl) {
        window.URL.revokeObjectURL(pdfPreviewUrl);
      }
    };
  }, [projetId]);

  const chargerPlanFondation = async () => {
    setLoading(true);
    setErrorMsg(null);
    try {
      const data = await dqeService.recupererPlanFondation(projetId);
      setPlanData(data);
    } catch (err) {
      console.warn("Impossible de récupérer le plan de fondation via API :", err.message);
      setErrorMsg("Impossible de charger le plan depuis l'API backend (Mode local actif).");
    } finally {
      setLoading(false);
    }
  };

  // Charge le PDF en Blob pour contourner les erreurs "127.0.0.1 a refusé de se connecter" dans l'iframe
  const chargerApercuPdf = async () => {
    try {
      const blob = await dqeService.recupererPlanFondationPDF(projetId);
      const url = window.URL.createObjectURL(blob);
      setPdfPreviewUrl(url);
    } catch (err) {
      console.error("Erreur lors du chargement du blob PDF pour l'aperçu :", err);
    }
  };

  const handleDownloadDXF = async () => {
    if (!projetId) {
      alert("Projet non enregistré sur le serveur backend.");
      return;
    }
    setDownloadingDxf(true);
    try {
      await dqeService.telechargerPlanFondationDXF(projetId);
    } catch (err) {
      alert("Erreur lors du téléchargement du fichier DXF : " + err.message);
    } finally {
      setDownloadingDxf(false);
    }
  };

  const handleDownloadPDF = async () => {
    if (!projetId) {
      alert("Projet non enregistré sur le serveur backend.");
      return;
    }
    setDownloadingPdf(true);
    try {
      const blob = await dqeService.recupererPlanFondationPDF(projetId);
      const url = window.URL.createObjectURL(blob);
      const link = document.createElement('a');
      link.href = url;
      link.setAttribute('download', `Plan_Coffrage_${projetId}.pdf`);
      document.body.appendChild(link);
      link.click();
      link.remove();
      window.URL.revokeObjectURL(url);
    } catch (err) {
      alert("Erreur lors du téléchargement du fichier PDF : " + err.message);
    } finally {
      setDownloadingPdf(false);
    }
  };

  const handleValiderPlan = async () => {
    if (!projetId) {
      onNext();
      return;
    }
    setValidating(true);
    try {
      await dqeService.validerPlanFondation(projetId);
      onNext();
    } catch (err) {
      console.warn("Erreur validation plan :", err.message);
      onNext();
    } finally {
      setValidating(false);
    }
  };

  const listSemelles = (planData && planData.semelles) || (sections && sections.semelles) || [];

  return (
    <div className="glass-panel" style={{ padding: '1.5rem' }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '1.5rem' }}>
        <div>
          <div className="badge badge-info" style={{ marginBottom: '0.4rem' }}>Étape 3bis — Plan de Fondation</div>
          <h2 style={{ fontSize: '1.5rem', fontWeight: 700 }}>
            Plan de Fondation & Coffrage Général (.PDF / .DXF)
          </h2>
          <p style={{ color: 'var(--text-muted)', fontSize: '0.85rem', marginTop: '0.25rem' }}>
            Positions en coordonnées réelles calculées selon la trame structurelle de l'ouvrage.
          </p>
          <div style={{ display: 'inline-flex', alignItems: 'center', gap: '0.4rem', background: 'rgba(245, 158, 11, 0.1)', color: '#fcd34d', border: '1px solid rgba(245, 158, 11, 0.3)', padding: '0.4rem 0.85rem', borderRadius: '8px', fontSize: '0.8rem', marginTop: '0.6rem', fontWeight: 500 }}>
            <AlertTriangle size={15} />
            <span>Positions calculées depuis une trame régulière. Précisez le plan d'exécution pour les bâtiments complexes.</span>
          </div>
        </div>

        {/* Boutons d'exportation */}
        <div style={{ display: 'flex', gap: '0.75rem' }}>
          <button
            type="button"
            className="btn btn-secondary"
            onClick={handleDownloadPDF}
            disabled={downloadingPdf}
            style={{ gap: '0.5rem' }}
          >
            <FileText size={18} />
            <span>{downloadingPdf ? 'Téléchargement...' : 'Télécharger (.PDF)'}</span>
          </button>

          <button
            type="button"
            className="btn btn-secondary"
            onClick={handleDownloadDXF}
            disabled={downloadingDxf}
            style={{ gap: '0.5rem', border: '1px solid var(--accent-primary)', color: 'var(--accent-primary)' }}
          >
            <Download size={18} />
            <span>{downloadingDxf ? 'Téléchargement...' : 'Télécharger (.DXF)'}</span>
          </button>
        </div>
      </div>

      {errorMsg && (
        <div style={{ background: 'rgba(239, 68, 68, 0.1)', border: '1px solid rgba(239, 68, 68, 0.35)', color: '#fca5a5', padding: '0.75rem 1rem', borderRadius: '8px', marginBottom: '1.5rem', fontSize: '0.85rem' }}>
          {errorMsg}
        </div>
      )}

      {/* Aperçu du Plan de Coffrage Intégré via Blob URL */}
      <div style={{ marginBottom: '2rem', textAlign: 'center' }}>
        <h4 style={{ fontSize: '0.95rem', fontWeight: 600, marginBottom: '0.75rem', color: 'var(--text-muted)', display: 'flex', alignItems: 'center', justifyContent: 'center', gap: '0.5rem' }}>
          <Layers size={18} color="var(--accent-primary)" />
          <span>Aperçu Graphique du Plan de Coffrage BTP</span>
        </h4>
        
        {projetId ? (
          <div 
            style={{ 
              width: '100%', 
              height: '600px', 
              borderRadius: '12px', 
              overflow: 'hidden', 
              border: '1px solid var(--core-border)',
              background: '#ffffff'
            }}
          >
            {pdfPreviewUrl ? (
              <iframe 
                src={`${pdfPreviewUrl}#toolbar=0&navpanes=0`} 
                title="Aperçu Plan de Fondation"
                width="100%" 
                height="100%" 
                style={{ border: 'none' }}
              />
            ) : (
              <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', height: '100%', color: '#64748b', fontSize: '0.9rem' }}>
                Chargement du rendu vectoriel du plan...
              </div>
            )}
          </div>
        ) : (
          <div style={{ padding: '2rem', background: 'rgba(15, 23, 42, 0.6)', border: '1px solid var(--core-border)', borderRadius: '12px', color: 'var(--text-muted)' }}>
            Enregistrez le projet pour afficher l'aperçu du plan de coffrage.
          </div>
        )}
      </div>

      {/* Tableau des semelles */}
      <div style={{ marginBottom: '2rem' }}>
        <h3 style={{ fontSize: '1.05rem', fontWeight: 600, marginBottom: '1rem', display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
          <Grid size={18} color="var(--accent-primary)" />
          <span>Coordonnées & Dimensions des Semelles</span>
        </h3>

        {loading ? (
          <p style={{ color: 'var(--text-muted)', fontSize: '0.9rem' }}>Chargement du plan de fondation...</p>
        ) : (
          <table className="custom-table">
            <thead>
              <tr>
                <th>Repère</th>
                <th>Désignation</th>
                <th>Dimensions (B x H)</th>
                <th>Coordonnées (X, Y)</th>
                <th>Statut Implantation</th>
              </tr>
            </thead>
            <tbody>
              {listSemelles.length > 0 ? (
                listSemelles.map((sem, idx) => (
                  <tr key={idx}>
                    <td style={{ fontWeight: 700, color: '#93c5fd' }}>{sem.identifiant || sem.id || `S${idx + 1}`}</td>
                    <td>{sem.name || sem.designation || 'Semelle de fondation'}</td>
                    <td style={{ fontWeight: 600 }}>{sem.section || `${sem.largeur_m || 1.2} x ${sem.hauteur_m || 0.4} m`}</td>
                    <td>{sem.position_x !== undefined ? `(${sem.position_x} m, ${sem.position_y} m)` : 'Grille (0,0)'}</td>
                    <td>
                      <span className="badge badge-success" style={{ display: 'inline-flex', alignItems: 'center', gap: '0.3rem' }}>
                        <CheckCircle size={14} />
                        <span>Implanté sur Grille</span>
                      </span>
                    </td>
                  </tr>
                ))
              ) : (
                <tr>
                  <td colSpan="5" style={{ textAlign: 'center', color: 'var(--text-muted)', padding: '2rem' }}>
                    Aucune semelle disponible.
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        )}
      </div>

      {/* Navigation */}
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
        <button type="button" className="btn btn-secondary" onClick={onBack}>
          <ArrowLeft size={18} />
          <span>Retour à la Validation</span>
        </button>

        <button type="button" className="btn btn-primary" onClick={handleValiderPlan} disabled={validating}>
          <span>{validating ? 'Validation...' : 'Valider le Plan & Passer au Devis'}</span>
          <ArrowRight size={18} />
        </button>
      </div>
    </div>
  );
}