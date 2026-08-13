import React, { useState } from 'react';
import { Grid, Cpu, ArrowRight, ShieldCheck, Layers } from 'lucide-react';

export default function StepDalles({ projectData, onNext }) {
  const [lx, setLx] = useState(projectData.porteeMax || 4.5);
  const [ly, setLy] = useState(6.0);
  const [typePlancher, setTypePlancher] = useState('dalle_pleine_4');

  // Calcul du rapport α = Lx / Ly
  const alpha = (parseFloat(lx) / parseFloat(ly)).toFixed(2);
  
  // Épaisseur minimale hd selon la RDM / BAEL 91
  // Dalle pleine appuyée sur 4 côtés : hd >= Lx / 40 (si alpha > 0.4)
  const hdTh = Math.max(12, Math.ceil((parseFloat(lx) * 100) / 40));
  const poidsPropreDalle = (hdTh * 0.25).toFixed(2); // 25 kN/m³

  return (
    <div className="glass-panel">
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '1.75rem' }}>
        <div>
          <div className="badge badge-info" style={{ marginBottom: '0.4rem' }}>Phase 2 — Module 7</div>
          <h2 style={{ fontSize: '1.5rem', fontWeight: 700, fontFamily: 'var(--font-heading)' }}>
            Pré-dimensionnement des Dalles & Planchers
          </h2>
          <p style={{ color: 'var(--text-muted)', fontSize: '0.9rem' }}>
            Calcul de l'épaisseur minimale <i>h<sub>d</sub></i> et vérification du comportement en nappe (BAEL 91).
          </p>
        </div>

        <div className="badge badge-unlocked" style={{ padding: '0.5rem 1rem' }}>
          <Grid size={16} />
          <span>Calcul 2D (L<sub>x</sub> / L<sub>y</sub> = {alpha})</span>
        </div>
      </div>

      {/* Formulaire Dalles */}
      <div className="grid-3" style={{ marginBottom: '2rem' }}>
        <div className="form-group">
          <label className="form-label">Petite Portée <i>L<sub>x</sub></i> (mètres)</label>
          <input
            type="number"
            step="0.1"
            className="form-control"
            value={lx}
            onChange={(e) => setLx(e.target.value)}
          />
        </div>

        <div className="form-group">
          <label className="form-label">Grande Portée <i>L<sub>y</sub></i> (mètres)</label>
          <input
            type="number"
            step="0.1"
            className="form-control"
            value={ly}
            onChange={(e) => setLy(e.target.value)}
          />
        </div>

        <div className="form-group">
          <label className="form-label">Type de Plancher / Appuis</label>
          <select
            className="form-select"
            value={typePlancher}
            onChange={(e) => setTypePlancher(e.target.value)}
          >
            <option value="dalle_pleine_4">Dalle Pleine sur 4 appuis (h_d ≥ Lx/40)</option>
            <option value="dalle_pleine_2">Dalle Pleine sur 2 appuis (h_d ≥ Lx/30)</option>
            <option value="corps_creux">Plancher Corps Creux 16+4 cm (Poutrelles + Hourdis)</option>
          </select>
        </div>
      </div>

      {/* Résultat Synthétique Dalle */}
      <div style={{ background: '#f8fafc', border: '1px solid var(--core-border)', borderRadius: 'var(--radius-md)', padding: '1.5rem', marginBottom: '2rem' }}>
        <h3 style={{ fontSize: '1.1rem', fontWeight: 600, marginBottom: '1rem', fontFamily: 'var(--font-heading)' }}>
          Résultat du Pré-dimensionnement de la Dalle
        </h3>

        <div className="grid-3">
          <div style={{ background: '#ffffff', border: '1px solid var(--core-border)', padding: '1.15rem', borderRadius: 'var(--radius-md)' }}>
            <div style={{ fontSize: '0.75rem', color: 'var(--text-muted)', textTransform: 'uppercase', fontWeight: 600 }}>
              Épaisseur Minimale h<sub>d</sub>
            </div>
            <div style={{ fontSize: '1.6rem', fontWeight: 800, color: 'var(--accent-emerald)', marginTop: '0.2rem' }}>
              {hdTh} cm
            </div>
            <div style={{ fontSize: '0.75rem', color: 'var(--text-muted)', marginTop: '0.25rem' }}>
              Condition de flèche h<sub>d</sub> ≥ L<sub>x</sub>/40
            </div>
          </div>

          <div style={{ background: '#ffffff', border: '1px solid var(--core-border)', padding: '1.15rem', borderRadius: 'var(--radius-md)' }}>
            <div style={{ fontSize: '0.75rem', color: 'var(--text-muted)', textTransform: 'uppercase', fontWeight: 600 }}>
              Poids Propre de Dalle (g<sub>dalle</sub>)
            </div>
            <div style={{ fontSize: '1.6rem', fontWeight: 800, color: 'var(--accent-primary)', marginTop: '0.2rem' }}>
              {poidsPropreDalle} kN/m²
            </div>
            <div style={{ fontSize: '0.75rem', color: 'var(--text-muted)', marginTop: '0.25rem' }}>
              Poids volumique béton γ = 25 kN/m³
            </div>
          </div>

          <div style={{ background: '#ffffff', border: '1px solid var(--core-border)', padding: '1.15rem', borderRadius: 'var(--radius-md)' }}>
            <div style={{ fontSize: '0.75rem', color: 'var(--text-muted)', textTransform: 'uppercase', fontWeight: 600 }}>
              Mode de Travail
            </div>
            <div style={{ fontSize: '1.2rem', fontWeight: 700, color: '#4338ca', marginTop: '0.4rem' }}>
              {alpha > 0.4 ? 'Travail dans les 2 Sens (2D)' : 'Travail dans 1 seul Sens (1D)'}
            </div>
            <div style={{ fontSize: '0.75rem', color: 'var(--text-muted)', marginTop: '0.25rem' }}>
              Rapport α = L<sub>x</sub>/L<sub>y</sub> = {alpha}
            </div>
          </div>
        </div>
      </div>

      <div style={{ display: 'flex', justifyContent: 'flex-end' }}>
        <button className="btn btn-primary" onClick={onNext}>
          <span>Poursuivre la Descente de Charge</span>
          <ArrowRight size={18} />
        </button>
      </div>
    </div>
  );
}
