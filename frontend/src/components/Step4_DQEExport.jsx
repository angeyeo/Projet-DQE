import React, { useState } from 'react';
import { Download, FileSpreadsheet, ArrowLeft, RefreshCw, CheckCircle2, Loader2, AlertCircle } from 'lucide-react';
import { dqeService } from '../api/dqeService';

export default function Step4_DQEExport({ dqeData, projectData, projetId, onBack, onReset }) {
  const { quantites = [], montantTotalFCFA = '0 FCFA', syntheseCalcul = '' } = dqeData || {};

  const [exportEnCours, setExportEnCours] = useState(null); // 'pdf' | 'excel' | null
  const [exportErreur, setExportErreur] = useState(null);

  const telecharger = async (format) => {
    if (!projetId) {
      setExportErreur("Identifiant de projet manquant. Impossible de générer l'export.");
      return;
    }
    setExportErreur(null);
    setExportEnCours(format);
    try {
      await dqeService.telechargerDQEFichier(projetId, format);
    } catch (err) {
      setExportErreur(`Échec de l'export ${format === 'pdf' ? 'PDF' : 'Excel'} : ${err.message || "Erreur serveur"}`);
    } finally {
      setExportEnCours(null);
    }
  };

  const handleExportPDF = () => telecharger('pdf');
  const handleExportExcel = () => telecharger('excel');

  return (
    <div className="glass-panel">
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '2rem' }}>
        <div>
          <h2 style={{ fontSize: '1.5rem', fontWeight: 700, marginBottom: '0.5rem' }}>
            Étape 4 : Devis Quantitatif Estimatif (DQE / DEK) & Couche IA
          </h2>
          <p style={{ color: 'var(--text-muted)', fontSize: '0.9rem' }}>
            Devis généré automatiquement à partir des sections verrouillées de l'ouvrage <strong>{projectData.nomProjet || 'Nouveau Projet'}</strong>.
          </p>
        </div>

        <div style={{ display: 'flex', gap: '0.75rem' }}>
          <button className="btn btn-secondary" onClick={handleExportExcel} disabled={exportEnCours !== null}>
            {exportEnCours === 'excel' ? <Loader2 size={18} className="spin" /> : <FileSpreadsheet size={18} color="var(--status-ok)" />}
            <span>{exportEnCours === 'excel' ? 'Génération...' : 'Exporter Excel (.xlsx)'}</span>
          </button>
          <button className="btn btn-primary" onClick={handleExportPDF} disabled={exportEnCours !== null}>
            {exportEnCours === 'pdf' ? <Loader2 size={18} className="spin" /> : <Download size={18} />}
            <span>{exportEnCours === 'pdf' ? 'Génération...' : 'Télécharger PDF'}</span>
          </button>
        </div>
      </div>

      {exportErreur && (
        <div style={{ padding: '1rem 1.25rem', borderRadius: '12px', background: 'var(--status-critical-soft)', border: '1px solid var(--status-critical-soft)', marginBottom: '2rem', display: 'flex', alignItems: 'flex-start', gap: '0.75rem' }}>
          <AlertCircle size={20} color="var(--status-critical)" style={{ flexShrink: 0, marginTop: '0.1rem' }} />
          <span style={{ fontSize: '0.88rem', color: 'var(--status-critical)' }}>{exportErreur}</span>
        </div>
      )}

      {/* Carte Montant Total */}
      <div
        style={{
          background: 'linear-gradient(135deg, var(--accent-soft), var(--status-ok-soft))',
          border: '1px solid var(--accent-soft-border)',
          borderRadius: '16px',
          padding: '1.75rem 2rem',
          marginBottom: '2rem',
          display: 'flex',
          justify: 'space-between',
          alignItems: 'center',
        }}
      >
        <div>
          <div style={{ fontSize: '0.85rem', color: 'var(--text-muted)', textTransform: 'uppercase', letterSpacing: '0.05em' }}>
            Montant Estimatif Total du Gros Œuvre
          </div>
          <div style={{ fontSize: '2.4rem', fontWeight: 800, color: 'white', marginTop: '0.25rem' }}>
            {montantTotalFCFA}
          </div>
        </div>

        <div style={{ textAlign: 'right' }}>
          <div className="badge badge-locked" style={{ marginBottom: '0.5rem', padding: '0.4rem 0.8rem', display: 'inline-flex', alignItems: 'center', gap: '0.35rem' }}>
            <CheckCircle2 size={14} />
            <span>Basé sur Données Verrouillées</span>
          </div>
          <div style={{ fontSize: '0.8rem', color: 'var(--text-muted)' }}>
            Calculé avec prix unitaires locaux BTP
          </div>
        </div>
      </div>

      {/* Synthèse du moteur de calcul -- NB : ce bloc affichait auparavant un
          badge "Sparkles / Explication par IA (DKE IA)" alors que le texte
          est une phrase fixe du moteur de calcul, jamais générée par l'IA.
          Aucun appel à /assistant/expliquer-element/ n'était fait ici.
          L'explication réelle par IA est désormais disponible élément par
          élément à l'Étape 2 (bouton "Expliquer (IA)"). */}
      <div
        style={{
          background: 'var(--status-ok-soft)',
          border: '1px solid var(--status-ok-soft)',
          borderRadius: '16px',
          padding: '1.5rem',
          marginBottom: '2rem',
        }}
      >
        <h4 style={{ fontSize: '1rem', fontWeight: 600, color: 'var(--status-ok)', marginBottom: '0.75rem' }}>
          Synthèse du Moteur de Calcul
        </h4>
        <p style={{ fontSize: '0.9rem', color: 'var(--ink-900)', lineHeight: 1.6 }}>
          {syntheseCalcul || "Aucune analyse complémentaire requise. Les calculs respectent les ratios BAEL91 d'armatures et de béton."}
        </p>
      </div>

      {/* Tableau détaillé du DQE */}
      <div style={{ marginBottom: '2.5rem' }}>
        <h3 style={{ fontSize: '1.1rem', fontWeight: 600, marginBottom: '1rem' }}>
          Bordereau Quantitatif Estimatif des Matériaux
        </h3>

        <table className="custom-table">
          <thead>
            <tr>
              <th>Désignation du Matériau / Prestation</th>
              <th>Unité</th>
              <th>Quantité Estimée</th>
              <th>Prix Unitaire (FCFA)</th>
              <th>Montant Total (FCFA)</th>
            </tr>
          </thead>
          <tbody>
            {quantites.length > 0 ? (
              quantites.map((row, idx) => (
                <tr key={idx}>
                  <td style={{ fontWeight: 600 }}>{row.materiau || row.designation}</td>
                  <td><span className="badge badge-info">{row.unite || 'U'}</span></td>
                  <td style={{ fontWeight: 700 }}>{row.quantite}</td>
                  <td>{row.prixUnitaire || row.prix_unitaire || '—'}</td>
                  <td style={{ fontWeight: 700, color: 'var(--accent-emerald)' }}>{row.total || row.montant}</td>
                </tr>
              ))
            ) : (
              <tr>
                <td colSpan="5" style={{ textAlign: 'center', color: 'var(--text-muted)', padding: '2rem' }}>
                  Aucun poste quantitatif généré.
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>

      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
        <button className="btn btn-secondary" onClick={onBack}>
          <ArrowLeft size={18} />
          <span>Ajuster la Validation</span>
        </button>

        <button className="btn btn-secondary" onClick={onReset}>
          <RefreshCw size={18} />
          <span>Nouveau Projet</span>
        </button>
      </div>
    </div>
  );
}