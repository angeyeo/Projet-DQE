import React from 'react';
import { Layers, Plus, Trash2, ShieldCheck } from 'lucide-react';

export default function FormCouchesCharge({ couches, setCouches }) {
  const defaultCouches = [
    { id: 1, nom: 'Carrelage + Chape de mortier (Ep. 5cm)', epaisseurCm: 5, poidsVolumique: 20, chargeG: 1.0 },
    { id: 2, nom: 'Dalle en béton armé (Ep. 16cm)', epaisseurCm: 16, poidsVolumique: 25, chargeG: 4.0 },
    { id: 3, nom: 'Enduit plâtre sous-face (Ep. 1.5cm)', epaisseurCm: 1.5, poidsVolumique: 10, chargeG: 0.15 },
  ];

  const list = couches && couches.length > 0 ? couches : defaultCouches;

  const handleAdd = () => {
    const newId = Date.now();
    const newCouche = { id: newId, nom: 'Nouvelle couche (ex: Étanchéité)', epaisseurCm: 2, poidsVolumique: 15, chargeG: 0.3 };
    setCouches([...list, newCouche]);
  };

  const handleRemove = (id) => {
    setCouches(list.filter(c => c.id !== id));
  };

  const handleUpdate = (id, field, val) => {
    setCouches(list.map(c => {
      if (c.id === id) {
        const updated = { ...c, [field]: val };
        if (field === 'epaisseurCm' || field === 'poidsVolumique') {
          const epM = parseFloat(updated.epaisseurCm || 0) / 100;
          const gamma = parseFloat(updated.poidsVolumique || 0);
          updated.chargeG = parseFloat((epM * gamma).toFixed(2));
        }
        return updated;
      }
      return c;
    }));
  };

  const totalG = list.reduce((sum, c) => sum + (parseFloat(c.chargeG) || 0), 0).toFixed(2);

  return (
    <div style={{ background: '#f8fafc', border: '1px solid var(--core-border)', borderRadius: 'var(--radius-md)', padding: '1.25rem', marginTop: '1rem' }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '1rem' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
          <Layers size={18} color="var(--accent-primary)" />
          <h4 style={{ fontSize: '0.95rem', fontWeight: 600 }}>Phase 2 — Charges Permanentes Composées Multi-couches (G)</h4>
        </div>
        <div className="badge badge-info">
          Total G = {totalG} kN/m²
        </div>
      </div>

      <p style={{ fontSize: '0.8rem', color: 'var(--text-muted)', marginBottom: '1rem' }}>
        Décomposez le plancher en plusieurs couches (revêtement, dalle, isolation, enduit) pour un calcul exact de la charge permanente <i>G</i>.
      </p>

      <table className="custom-table" style={{ marginTop: '0' }}>
        <thead>
          <tr>
            <th>Désignation de la couche</th>
            <th>Épaisseur (cm)</th>
            <th>Poids Volumique γ (kN/m³)</th>
            <th>Charge G (kN/m²)</th>
            <th>Action</th>
          </tr>
        </thead>
        <tbody>
          {list.map((item) => (
            <tr key={item.id}>
              <td>
                <input
                  type="text"
                  className="form-control"
                  style={{ padding: '0.4rem 0.6rem', fontSize: '0.85rem' }}
                  value={item.nom}
                  onChange={(e) => handleUpdate(item.id, 'nom', e.target.value)}
                />
              </td>
              <td style={{ width: '120px' }}>
                <input
                  type="number"
                  className="form-control"
                  style={{ padding: '0.4rem 0.6rem', fontSize: '0.85rem' }}
                  value={item.epaisseurCm}
                  onChange={(e) => handleUpdate(item.id, 'epaisseurCm', e.target.value)}
                />
              </td>
              <td style={{ width: '150px' }}>
                <input
                  type="number"
                  className="form-control"
                  style={{ padding: '0.4rem 0.6rem', fontSize: '0.85rem' }}
                  value={item.poidsVolumique}
                  onChange={(e) => handleUpdate(item.id, 'poidsVolumique', e.target.value)}
                />
              </td>
              <td style={{ fontWeight: 700, color: 'var(--accent-emerald)', width: '120px' }}>
                {item.chargeG} kN/m²
              </td>
              <td style={{ width: '60px', textAlign: 'center' }}>
                <button
                  type="button"
                  className="btn btn-secondary"
                  style={{ padding: '0.3rem', color: '#dc2626' }}
                  onClick={() => handleRemove(item.id)}
                >
                  <Trash2 size={14} />
                </button>
              </td>
            </tr>
          ))}
        </tbody>
      </table>

      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginTop: '1rem' }}>
        <button type="button" className="btn btn-secondary" style={{ fontSize: '0.8rem', padding: '0.4rem 0.8rem' }} onClick={handleAdd}>
          <Plus size={14} />
          <span>Ajouter une couche</span>
        </button>
        <span style={{ fontSize: '0.85rem', fontWeight: 700, color: 'var(--text-main)' }}>
          Somme totale <i>G</i> = {totalG} kN/m²
        </span>
      </div>
    </div>
  );
}
