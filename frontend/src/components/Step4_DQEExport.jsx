import React from 'react';
import { Download, FileSpreadsheet, FileText, Bot, ArrowLeft, RefreshCw, CheckCircle2, Sparkles } from 'lucide-react';

export default function Step4_DQEExport({ dqeData, projectData, onBack, onReset }) {
  const { quantites = [], montantTotalFCFA = '0 FCFA', explicationIA = '' } = dqeData || {};

  const handleExportPDF = () => {
    alert("Génération et téléchargement du rapport PDF (ReportLab)...");
  };

  const handleExportExcel = () => {
    alert("Exportation du devis quantitatif sous format Excel (.xlsx openpyxl)...");
  };

  return (
    <div className="glass-panel">
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '2rem' }}>
        <div>
          <h2 style={{ fontSize: '1.5rem', fontWeight: 700, marginBottom: '0.5rem' }}>
            Étape 4 : Devis Quantitatif Estimatif (DQE / DEK) & Couche IA
          </h2>
          <p style={{ color: 'var(--text-muted)', fontSize: '0.9rem' }}>
            Devis généré automatiquement à partir des sections verrouillées de l'ouvrage <strong>{projectData.nomProjet}</strong>.
          </p>
        </div>

        <div style={{ display: 'flex', gap: '0.75rem' }}>
          <button className="btn btn-secondary" onClick={handleExportExcel}>
            <FileSpreadsheet size={18} color="#10b981" />
            <span>Exporter Excel (.xlsx)</span>
          </button>
          <button className="btn btn-primary" onClick={handleExportPDF}>
            <Download size={18} />
            <span>Télécharger PDF</span>
          </button>
        </div>
      </div>

      {/* Carte Montant Total */}
      <div
        style={{
          background: 'linear-gradient(135deg, rgba(59, 130, 246, 0.15), rgba(16, 185, 129, 0.15))',
          border: '1px solid rgba(59, 130, 246, 0.3)',
          borderRadius: '16px',
          padding: '1.75rem 2rem',
          marginBottom: '2rem',
          display: 'flex',
          justifyContent: 'space-between',
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
          <div className="badge badge-locked" style={{ marginBottom: '0.5rem', padding: '0.4rem 0.8rem' }}>
            <CheckCircle2 size={14} />
            <span>Basé sur Données Verrouillées</span>
          </div>
          <div style={{ fontSize: '0.8rem', color: 'var(--text-muted)' }}>
            Calculé avec prix unitaires locaux BTP
          </div>
        </div>
      </div>

      {/* Module Assistant IA */}
      <div
        style={{
          background: 'rgba(99, 102, 241, 0.08)',
          border: '1px solid rgba(99, 102, 241, 0.25)',
          borderRadius: '16px',
          padding: '1.5rem',
          marginBottom: '2rem',
        }}
      >
        <div style={{ display: 'flex', alignItems: 'center', gap: '0.75rem', marginBottom: '0.75rem' }}>
          <div style={{ width: '32px', height: '32px', borderRadius: '8px', background: 'var(--accent-indigo)', display: 'flex', alignItems: 'center', justifyContent: 'center', color: 'white' }}>
            <Sparkles size={18} />
          </div>
          <h4 style={{ fontSize: '1rem', fontWeight: 600, color: '#a5b4fc' }}>
            Explication & Validation par IA (DKE IA)
          </h4>
        </div>
        <p style={{ fontSize: '0.9rem', color: '#e2e8f0', lineHeight: 1.6 }}>
          {explicationIA}
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
            {quantites.map((row, idx) => (
              <tr key={idx}>
                <td style={{ fontWeight: 600 }}>{row.materiau}</td>
                <td><span className="badge badge-info">{row.unite}</span></td>
                <td style={{ fontWeight: 700 }}>{row.quantite}</td>
                <td>{row.prixUnitaire}</td>
                <td style={{ fontWeight: 700, color: 'var(--accent-emerald)' }}>{row.total}</td>
              </tr>
            ))}
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
