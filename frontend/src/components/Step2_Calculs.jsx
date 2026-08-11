import React from 'react';
import { ArrowLeft, ArrowRight, Shield, Layers, Box, Cpu } from 'lucide-react';

export default function Step2_Calculs({ sections, projectData, onBack, onNext }) {
  const { poteaux = [], poutres = [], semelles = [] } = sections || {};

  return (
    <div className="glass-panel">
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '2rem' }}>
        <div>
          <h2 style={{ fontSize: '1.5rem', fontWeight: 700, marginBottom: '0.5rem' }}>
            Descente de Charge & Pré-dimensionnement Structurel
          </h2>
          <p style={{ color: 'var(--text-muted)', fontSize: '0.9rem' }}>
            Calcul automatique des sections normatives ({projectData.norme || 'BAEL 91'}) pour l'ouvrage <strong>{projectData.nomProjet}</strong>.
          </p>
        </div>
        <div className="badge badge-info" style={{ padding: '0.5rem 1rem', fontSize: '0.85rem' }}>
          <Cpu size={16} />
          <span>Formules BAEL 91 / Eurocode 2</span>
        </div>
      </div>

      {/* Cartes de synthèse mathématiques & normatives */}
      <div className="grid-3" style={{ marginBottom: '2rem' }}>
        <div style={{ background: '#f0f7ff', border: '1px solid #bfdbfe', padding: '1.25rem', borderRadius: '14px' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', color: '#1e40af', marginBottom: '0.5rem' }}>
            <Layers size={18} />
            <h4 style={{ fontSize: '0.9rem', fontWeight: 600 }}>Combinaison d'Actions ELU</h4>
          </div>
          <div style={{ fontSize: '1.35rem', fontWeight: 700, color: '#1e3a8a', fontFamily: 'serif' }}>
            q<sub>ELU</sub> = 1.35 G + 1.5 Q
          </div>
          <div style={{ fontSize: '0.8rem', color: '#475569', marginTop: '0.35rem' }}>
            G = 5.0 kN/m² | Q = {projectData.chargeExploitation} kN/m²
          </div>
        </div>

        <div style={{ background: '#f0fdf4', border: '1px solid #bbf7d0', padding: '1.25rem', borderRadius: '14px' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', color: '#166534', marginBottom: '0.5rem' }}>
            <Box size={18} />
            <h4 style={{ fontSize: '0.9rem', fontWeight: 600 }}>Éléments Dimensionnés</h4>
          </div>
          <div style={{ fontSize: '1.35rem', fontWeight: 700, color: '#14532d' }}>
            {poteaux.length + poutres.length + semelles.length} Éléments
          </div>
          <div style={{ fontSize: '0.8rem', color: '#475569', marginTop: '0.35rem' }}>
            {poteaux.length} Poteaux | {poutres.length} Poutres | {semelles.length} Semelles
          </div>
        </div>

        <div style={{ background: '#fffbeb', border: '1px solid #fef3c7', padding: '1.25rem', borderRadius: '14px' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', color: '#92400e', marginBottom: '0.5rem' }}>
            <Shield size={18} />
            <h4 style={{ fontSize: '0.9rem', fontWeight: 600 }}>Contrainte & Sol</h4>
          </div>
          <div style={{ fontSize: '1.35rem', fontWeight: 700, color: '#78350f', fontFamily: 'serif' }}>
            σ<sub>sol</sub> = 0.20 MPa
          </div>
          <div style={{ fontSize: '0.8rem', color: '#475569', marginTop: '0.35rem' }}>
            Portance admissible du sol de fondation
          </div>
        </div>
      </div>

      {/* Tableau des Poteaux */}
      <div style={{ marginBottom: '2rem' }}>
        <h3 style={{ fontSize: '1.1rem', fontWeight: 600, marginBottom: '0.75rem', display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
          <span>Poteaux (Compression Centrée — Effort Axial N<sub>sd</sub>)</span>
        </h3>
        <table className="custom-table">
          <thead>
            <tr>
              <th>Identifiant</th>
              <th>Élément Structurel</th>
              <th>Effort Axial (N<sub>sd</sub>)</th>
              <th>Section Proposée (b × h)</th>
              <th>Armatures Longitudinales</th>
            </tr>
          </thead>
          <tbody>
            {poteaux.map((item) => (
              <tr key={item.id}>
                <td style={{ fontWeight: 600, color: 'var(--accent-primary)' }}>{item.id}</td>
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
          Poutres (Flexion Simple — Portée L)
        </h3>
        <table className="custom-table">
          <thead>
            <tr>
              <th>Identifiant</th>
              <th>Nom de la Poutre</th>
              <th>Portée (L)</th>
              <th>Section Proposée (b × h)</th>
              <th>Armatures Longitudinales</th>
            </tr>
          </thead>
          <tbody>
            {poutres.map((item) => (
              <tr key={item.id}>
                <td style={{ fontWeight: 600, color: 'var(--accent-primary)' }}>{item.id}</td>
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
          Semelles Isolées de Fondation (Portance σ<sub>sol</sub>)
        </h3>
        <table className="custom-table">
          <thead>
            <tr>
              <th>Identifiant</th>
              <th>Nom de la Semelle</th>
              <th>Contrainte du Sol (σ<sub>sol</sub>)</th>
              <th>Surface d'Appui (A × B)</th>
              <th>Hauteur (h)</th>
            </tr>
          </thead>
          <tbody>
            {semelles.map((item) => (
              <tr key={item.id}>
                <td style={{ fontWeight: 600, color: 'var(--accent-primary)' }}>{item.id}</td>
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
