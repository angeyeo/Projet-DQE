import React from 'react';
import { ArrowLeft, ArrowRight, Shield, Layers, Box, Cpu } from 'lucide-react';

export default function Step2_Calculs({ sections, projectData, onBack, onNext }) {
  const { poteaux = [], poutres = [], semelles = [] } = sections || {};
  const totalElements = poteaux.length + poutres.length + semelles.length;

  return (
    <div className="glass-panel">
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '2rem' }}>
        <div>
          <h2 style={{ fontSize: '1.5rem', fontWeight: 700, marginBottom: '0.5rem' }}>
            Étape 2 : Descente de charge & Sections proposées
          </h2>
          <p style={{ color: 'var(--text-muted)', fontSize: '0.9rem' }}>
            Calcul automatique des sections normatives ({projectData.norme || 'BAEL 91'}) pour l'ouvrage <strong>{projectData.nomProjet || 'Nouveau Projet'}</strong>.
          </p>
        </div>
        <div className="badge badge-info" style={{ padding: '0.5rem 1rem', fontSize: '0.85rem', display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
          <Cpu size={16} />
          <span>Norme : {projectData.norme || 'BAEL91'}</span>
        </div>
      </div>

      {/* Cartes de synthèse */}
      <div className="grid-3" style={{ marginBottom: '2rem' }}>
        <div style={{ background: 'rgba(59, 130, 246, 0.08)', border: '1px solid rgba(59, 130, 246, 0.2)', padding: '1.25rem', borderRadius: '14px' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', color: '#93c5fd', marginBottom: '0.5rem' }}>
            <Layers size={18} />
            <h4 style={{ fontSize: '0.9rem', fontWeight: 600 }}>Combinaison ELU</h4>
          </div>
          <div style={{ fontSize: '1.3rem', fontWeight: 700 }}>
            q_ELU = 1.35 G + 1.5 Q
          </div>
          <div style={{ fontSize: '0.8rem', color: 'var(--text-muted)', marginTop: '0.25rem' }}>
            Charge permanente G = 5.0 kN/m² | Q = {projectData.chargeExploitation || 1.5} kN/m²
          </div>
        </div>

        <div style={{ background: 'rgba(16, 185, 129, 0.08)', border: '1px solid rgba(16, 185, 129, 0.2)', padding: '1.25rem', borderRadius: '14px' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', color: '#6ee7b7', marginBottom: '0.5rem' }}>
            <Box size={18} />
            <h4 style={{ fontSize: '0.9rem', fontWeight: 600 }}>Nombre d'Éléments</h4>
          </div>
          <div style={{ fontSize: '1.3rem', fontWeight: 700 }}>
            {totalElements} Éléments Calculés
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
          <div style={{ fontSize: '1.3rem', fontWeight: 700 }}>
            Étape 3 Suivante
          </div>
          <div style={{ fontSize: '0.8rem', color: 'var(--text-muted)', marginTop: '0.25rem' }}>
            Validation obligatoire avant verrouillage final.
          </div>
        </div>
      </div>

      {totalElements === 0 ? (
        <div style={{ padding: '2rem', textAlign: 'center', background: 'rgba(255,255,255,0.02)', borderRadius: '12px', border: '1px dashed var(--core-border)', marginBottom: '2rem' }}>
          <p style={{ color: 'var(--text-muted)', fontSize: '0.95rem' }}>
            Aucun élément structurel calculé pour le moment.
          </p>
        </div>
      ) : (
        <>
          {/* Tableau des Poteaux */}
          <div style={{ marginBottom: '2rem' }}>
            <h3 style={{ fontSize: '1.1rem', fontWeight: 600, marginBottom: '0.75rem' }}>
              Poteaux (Descente de charge axiale N_sd)
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
                {poteaux.map((item, idx) => (
                  <tr key={item.id || idx}>
                    <td style={{ fontWeight: 600, color: '#93c5fd' }}>{item.id || `P${idx + 1}`}</td>
                    <td>{item.name || `Poteau P${idx + 1}`}</td>
                    <td><span className="badge badge-info">{item.charge || item.effort_axial || '150 kN'}</span></td>
                    <td style={{ fontWeight: 700, color: 'var(--accent-emerald)' }}>{item.section || '20 x 20 cm'}</td>
                    <td>{item.armatures || '4 HA 12'}</td>
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
                {poutres.map((item, idx) => (
                  <tr key={item.id || idx}>
                    <td style={{ fontWeight: 600, color: '#93c5fd' }}>{item.id || `R${idx + 1}`}</td>
                    <td>{item.name || `Poutre R${idx + 1}`}</td>
                    <td>{item.portee || '5.0 m'}</td>
                    <td style={{ fontWeight: 700, color: 'var(--accent-emerald)' }}>{item.section || '20 x 40 cm'}</td>
                    <td>{item.armatures || '3 HA 14'}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

          {/* Tableau des Semelles */}
          <div style={{ marginBottom: '2.5rem' }}>
            <h3 style={{ fontSize: '1.1rem', fontWeight: 600, marginBottom: '0.75rem' }}>
              Semelles de Fondation (Contrainte du sol σ_sol)
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
                {semelles.map((item, idx) => (
                  <tr key={item.id || idx}>
                    <td style={{ fontWeight: 600, color: '#93c5fd' }}>{item.id || `S${idx + 1}`}</td>
                    <td>{item.name || `Semelle S${idx + 1}`}</td>
                    <td>{item.contrainteSol || '0.20 MPa'}</td>
                    <td style={{ fontWeight: 700, color: 'var(--accent-emerald)' }}>{item.section || '120 x 120 cm'}</td>
                    <td>{item.hauteur || '35 cm'}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </>
      )}

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