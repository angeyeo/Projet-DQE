import React from 'react';
import { ArrowLeft, ArrowRight, Shield, Layers, Box, Cpu, AlertCircle } from 'lucide-react';

export default function Step2_Calculs({ sections, projectData, onBack, onNext }) {
  const { poteaux = [], poutres = [], semelles = [] } = sections || {};

  return (
    <div className="glass-panel">
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '2rem' }}>
        <div>
          <h2 style={{ fontSize: '1.5rem', fontWeight: 700, marginBottom: '0.5rem' }}>
            Étape 2 : Descente de charge & Sections proposées
          </h2>
          <p style={{ color: 'var(--text-muted)', fontSize: '0.9rem' }}>
            Calcul automatique des sections normatives ({projectData.norme || 'BAEL 91'}) pour l'ouvrage <strong>{projectData.nomProjet}</strong>.
          </p>
        </div>
        <div className="badge badge-info" style={{ padding: '0.5rem 1rem', fontSize: '0.85rem' }}>
          <Cpu size={16} />
          <span>Formules BAEL / Eurocode 2</span>
        </div>
      </div>

      {/* Cartes de synthèse */}
      <div className="grid-3" style={{ marginBottom: '2rem' }}>
        <div style={{ background: 'rgba(59, 130, 246, 0.08)', border: '1px solid rgba(59, 130, 246, 0.2)', padding: '1.25rem', borderRadius: '14px' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', color: '#93c5fd', marginBottom: '0.5rem' }}>
            <Layers size={18} />
            <h4 style={{ fontSize: '0.9rem', fontWeight: 600 }}>Combinaison ELU</h4>
          </div>
          <div style={{ fontSize: '1.4rem', fontWeight: 700 }}>
            q_ELU = 1.35 G + 1.5 Q
          </div>
          <div style={{ fontSize: '0.8rem', color: 'var(--text-muted)', marginTop: '0.25rem' }}>
            Charge permanente G = 5.0 kN/m² | Q = {projectData.chargeExploitation} kN/m²
          </div>
        </div>

        <div style={{ background: 'rgba(16, 185, 129, 0.08)', border: '1px solid rgba(16, 185, 129, 0.2)', padding: '1.25rem', borderRadius: '14px' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', color: '#6ee7b7', marginBottom: '0.5rem' }}>
            <Box size={18} />
            <h4 style={{ fontSize: '0.9rem', fontWeight: 600 }}>Nombre d'Éléments</h4>
          </div>
          <div style={{ fontSize: '1.4rem', fontWeight: 700 }}>
            {poteaux.length + poutres.length + semelles.length} Éléments Calculés
          </div>
          <div style={{ fontSize: '0.8rem', color: 'var(--text-muted)', marginTop: '0.25rem' }}>
            {poteaux.length} Poteaux | {poutres.length} Poutres | {semelles.length} Semelles
          </div>
        </div>

        <div style={{ background: 'rgba(245, 158, 11, 0.08)', border: '1px solid rgba(245, 158, 11, 0.2)', padding: '1.25rem', borderRadius: '14px' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', color: '#fcd34d', marginBottom: '0.5rem' }}>
            <Shield size={18} />
            <h4 style={{ fontSize: '0.9rem', fontWeight: 600 }}>Validation Humaine</h4>
          </div>
          <div style={{ fontSize: '1.4rem', fontWeight: 700 }}>
            Étape 3 Suivante
          </div>
          <div style={{ fontSize: '0.8rem', color: 'var(--text-muted)', marginTop: '0.25rem' }}>
            Validation obligatoire avant verrouillage final.
          </div>
        </div>
      </div>

      {/* Tableau des Poteaux */}
      <div style={{ marginBottom: '2rem' }}>
        <h3 style={{ fontSize: '1.1rem', fontWeight: 600, marginBottom: '0.75rem', display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
          <span>Poteaux (Descente de charge axiale N_sd)</span>
        </h3>
        <table className="custom-table">
          <thead>
            <tr>
              <th>Identifiant</th>
              <th>Nom de l'Élément</th>
              <th>Effort Axial (N_sd)</th>
              <th>Section Proposée (b x h)</th>
              <th>Armatures (FeE500)</th>
            </tr>
          </thead>
          <tbody>
            {poteaux.map((item) => (
              <tr key={item.id}>
                <td style={{ fontWeight: 600, color: '#93c5fd' }}>{item.id}</td>
                <td>{item.name}</td>
                <td><span className="badge badge-info">{item.charge}</span></td>
                <td style={{ fontWeight: 700, color: 'var(--accent-emerald)' }}>{item.section}</td>
                <td>{item.armatures}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {/* Tableau des Poutres */}
      <div style={{ marginBottom: '2rem' }}>
        <h3 style={{ fontSize: '1.1rem', fontWeight: 600, marginBottom: '0.75rem' }}>
          Poutres (Pré-dimensionnement en flexion simple)
        </h3>
        <table className="custom-table">
          <thead>
            <tr>
              <th>Identifiant</th>
              <th>Nom de la Poutre</th>
              <th>Portée L</th>
              <th>Section Proposée (b x h)</th>
              <th>Armatures Longitudinales</th>
            </tr>
          </thead>
          <tbody>
            {poutres.map((item) => (
              <tr key={item.id}>
                <td style={{ fontWeight: 600, color: '#93c5fd' }}>{item.id}</td>
                <td>{item.name}</td>
                <td>{item.portee}</td>
                <td style={{ fontWeight: 700, color: 'var(--accent-emerald)' }}>{item.section}</td>
                <td>{item.armatures}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {/* Tableau des Semelles */}
      <div style={{ marginBottom: '2.5rem' }}>
        <h3 style={{ fontSize: '1.1rem', fontWeight: 600, marginBottom: '0.75rem' }}>
          Semelles de Fondation (Contrainte du sol \sigma_sol)
        </h3>
        <table className="custom-table">
          <thead>
            <tr>
              <th>Identifiant</th>
              <th>Nom de la Semelle</th>
              <th>Contrainte du Sol</th>
              <th>Dimensions (A x B)</th>
              <th>Hauteur h</th>
            </tr>
          </thead>
          <tbody>
            {semelles.map((item) => (
              <tr key={item.id}>
                <td style={{ fontWeight: 600, color: '#93c5fd' }}>{item.id}</td>
                <td>{item.name}</td>
                <td>{item.contrainteSol}</td>
                <td style={{ fontWeight: 700, color: 'var(--accent-emerald)' }}>{item.section}</td>
                <td>{item.hauteur}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
        <button className="btn btn-secondary" onClick={onBack}>
          <ArrowLeft size={18} />
          <span>Retour aux paramètres</span>
        </button>

        <button className="btn btn-primary" onClick={onNext}>
          <span>Passer à la Validation & Verrouillage</span>
          <ArrowRight size={18} />
        </button>
      </div>
    </div>
  );
}
