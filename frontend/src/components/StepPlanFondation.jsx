import React, { useState, useEffect } from 'react';
import { ArrowLeft, ArrowRight, Download, CheckCircle, AlertTriangle, ShieldCheck, Grid } from 'lucide-react';
import { dqeService } from '../api/dqeService';

export default function StepPlanFondation({ projetId, sections, onBack, onNext }) {
  const [planData, setPlanData] = useState(null);
  const [loading, setLoading] = useState(false);
  const [downloading, setDownloading] = useState(false);
  const [validating, setValidating] = useState(false);
  const [errorMsg, setErrorMsg] = useState(null);

  useEffect(() => {
    if (projetId) {
      chargerPlanFondation();
    }
  }, [projetId]);

  const chargerPlanFondation = async () => {
    setLoading(true);
    setErrorMsg(null);
    try {
      const data = await dqeService.recupererPlanFondation(projetId);
      setPlanData(data);
    } catch (err) {
      console.warn("Impossible de récupérer le plan de fondation via API :", err.message);
      setErrorMsg("Impossible de charger le plan depuis l'API backend (mode local).");
    } finally {
      setLoading(false);
    }
  };

  const handleDownloadDXF = async () => {
    if (!projetId) {
      alert("Projet non enregistré sur le serveur backend.");
      return;
    }
    setDownloading(true);
    try {
      await dqeService.telechargerPlanFondationDXF(projetId);
    } catch (err) {
      alert("Erreur lors du téléchargement du fichier DXF : " + err.message);
    } finally {
      setDownloading(false);
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
      alert("Erreur lors de la validation du plan : " + err.message);
      onNext(); // permet de continuer même en mode hors-ligne
    } finally {
      setValidating(false);
    }
  };

  const listSemelles = (planData && planData.semelles) || (sections && sections.semelles) || [];

  return (
    <div className="glass-panel">
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '1.5rem' }}>
        <div>
          <div className="badge badge-info" style={{ marginBottom: '0.4rem' }}>Étape 3bis — Plan de Fondation</div>
          <h2 style={{ fontSize: '1.5rem', fontWeight: 700, fontFamily: 'var(--font-heading)' }}>
            Plan de Fondation Schématique (.DXF)
          </h2>
          <p style={{ color: 'var(--text-muted)', fontSize: '0.85rem', marginTop: '0.25rem' }}>
            Positions en grille schématiques des semelles isolées et filantes.
          </p>
          <div style={{ display: 'inline-flex', alignItems: 'center', gap: '0.4rem', background: '#fffbeb', color: '#b45309', border: '1px solid #fef3c7', padding: '0.4rem 0.85rem', borderRadius: '8px', fontSize: '0.8rem', marginTop: '0.6rem', fontWeight: 500 }}>
            <AlertTriangle size={15} />
            <span>Ce plan est schématique (positions en grille, pas les vraies coordonnées du terrain) — ne pas confondre avec un plan d'exécution.</span>
          </div>
        </div>

        <button
          type="button"
          className="btn btn-secondary"
          onClick={handleDownloadDXF}
          disabled={downloading}
          style={{ gap: '0.5rem', border: '1px solid var(--accent-primary)', color: 'var(--accent-primary)' }}
        >
          <Download size={18} />
          <span>{downloading ? 'Téléchargement...' : 'Télécharger le plan (.DXF)'}</span>
        </button>
      </div>

      {errorMsg && (
        <div style={{ background: '#fef2f2', border: '1px solid #fecaca', color: '#dc2626', padding: '0.75rem 1rem', borderRadius: '8px', marginBottom: '1.5rem', fontSize: '0.85rem' }}>
          {errorMsg}
        </div>
      )}

      {/* Tableau des semelles du plan */}
      <div style={{ marginBottom: '2rem' }}>
        <h3 style={{ fontSize: '1.05rem', fontWeight: 600, marginBottom: '1rem', display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
          <Grid size={18} color="var(--accent-primary)" />
          <span>Implantation des Semelles & Fondations</span>
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
                <th>Poteau Associé</th>
                <th>Statut Implantation</th>
              </tr>
            </thead>
            <tbody>
              {listSemelles.length > 0 ? (
                listSemelles.map((sem, idx) => (
                  <tr key={idx}>
                    <td style={{ fontWeight: 700, color: 'var(--accent-primary)' }}>{sem.identifiant || sem.id || `SEM-${idx + 1}`}</td>
                    <td>{sem.name || sem.designation || 'Semelle de fondation'}</td>
                    <td style={{ fontWeight: 600 }}>{sem.section || `${sem.largeur_m || 1.2} x ${sem.hauteur_m || 0.4} m`}</td>
                    <td>{sem.poteau_associe || 'Poteau Central C1'}</td>
                    <td>
                      <span className="badge badge-success">
                        <CheckCircle size={14} />
                        <span>Implanté sur Grille</span>
                      </span>
                    </td>
                  </tr>
                ))
              ) : (
                <tr>
                  <td colSpan="5" style={{ textAlign: 'center', color: 'var(--text-muted)', padding: '2rem' }}>
                    Aucune semelle validée disponible.
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        )}
      </div>

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
