import React, { useState } from 'react';
import { Lock, Unlock, ShieldAlert, ArrowLeft, ArrowRight, Edit3, ShieldCheck, HardHat, Plus, Trash2 } from 'lucide-react';

export default function Step3_ValidationLock({
  sections,
  toggleLock,
  toggleLockAll,
  updateSection,
  validationError,
  validatingId,
  postesMainDoeuvre = [],
  onAddPosteMainDoeuvre,
  onRemovePosteMainDoeuvre,
  mainDoeuvreError,
  onBack,
  onNext,
}) {
  const { poteaux = [], poutres = [], semelles = [] } = sections || {};

  const [nouveauPoste, setNouveauPoste] = useState({
    lot: 'lot_02_gros_oeuvre_superstructure',
    mode: 'simple',
    designation: '',
    unite: 'forfait',
    quantite: '',
    prixUnitaire: '',
    typePoste: 'maconnerie_creuse',
    valeurGeometrie: '',
  });
  const [posteEnCours, setPosteEnCours] = useState(false);

  const handleAjouterPoste = async () => {
    if (nouveauPoste.mode === 'simple') {
      const quantite = parseFloat(nouveauPoste.quantite);
      const prixUnitaire = parseFloat(nouveauPoste.prixUnitaire);
      if (!nouveauPoste.designation.trim() || !quantite || quantite <= 0 || !prixUnitaire || prixUnitaire <= 0) {
        return;
      }
      setPosteEnCours(true);
      await onAddPosteMainDoeuvre({ ...nouveauPoste, quantite, prixUnitaire });
    } else {
      const valGeo = parseFloat(nouveauPoste.valeurGeometrie);
      if (!valGeo || valGeo <= 0) return;
      setPosteEnCours(true);
      await onAddPosteMainDoeuvre({
        lot: nouveauPoste.lot,
        mode: 'ratio',
        type_poste: nouveauPoste.typePoste,
        geometrie: (nouveauPoste.typePoste || '').includes('chainage') ? { longueur_ml: valGeo } : { surface_m2: valGeo },
      });
    }
    setPosteEnCours(false);
    setNouveauPoste((p) => ({ ...p, designation: '', quantite: '', prixUnitaire: '', valeurGeometrie: '' }));
  };

  const totalMainDoeuvre = postesMainDoeuvre.reduce(
    (sum, p) => sum + (p.montant ?? ((p.quantite || 0) * (p.prix_unitaire || 0))),
    0
  );

  const allElements = [
    ...poteaux.map(p => ({ ...p, category: 'Poteau' })),
    ...poutres.map(p => ({ ...p, category: 'Poutre' })),
    ...semelles.map(s => ({ ...s, category: 'Semelle' })),
  ];

  const lockedCount = allElements.filter(e => e.locked).length;
  const isAllLocked = allElements.length > 0 && lockedCount === allElements.length;

  return (
    <div className="glass-panel">
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '2rem' }}>
        <div>
          <h2 style={{ fontSize: '1.5rem', fontWeight: 700, marginBottom: '0.5rem' }}>
            Étape 3 : Validation Ingénieur & Système de Verrouillage
          </h2>
          <p style={{ color: 'var(--text-muted)', fontSize: '0.9rem' }}>
            Ajustez les dimensions si nécessaire et <strong>verrouillez les sections</strong> pour garantir l'intégrité avant génération du devis.
          </p>
        </div>

        {allElements.length > 0 && (
          <button
            className={`btn ${isAllLocked ? 'btn-warning' : 'btn-success'}`}
            onClick={() => toggleLockAll(!isAllLocked)}
          >
            {isAllLocked ? <Unlock size={18} /> : <Lock size={18} />}
            <span>{isAllLocked ? 'Déverrouiller Tout' : 'Verrouiller Toutes les Sections'}</span>
          </button>
        )}
      </div>

      {validationError && (
        <div style={{ padding: '1rem 1.25rem', borderRadius: '12px', background: 'rgba(239, 68, 68, 0.1)', border: '1px solid rgba(239, 68, 68, 0.35)', marginBottom: '1.5rem', display: 'flex', alignItems: 'flex-start', gap: '0.75rem' }}>
          <ShieldAlert size={20} color="#ef4444" style={{ flexShrink: 0, marginTop: '0.1rem' }} />
          <span style={{ fontSize: '0.88rem', color: '#fca5a5' }}>{validationError}</span>
        </div>
      )}

      {/* Banner de Sécurité */}
      <div
        style={{
          padding: '1.25rem 1.5rem',
          borderRadius: '14px',
          background: isAllLocked ? 'rgba(16, 185, 129, 0.1)' : 'rgba(245, 158, 11, 0.1)',
          border: `1px solid ${isAllLocked ? 'rgba(16, 185, 129, 0.3)' : 'rgba(245, 158, 11, 0.3)'}`,
          marginBottom: '2rem',
          display: 'flex',
          alignItems: 'center',
          gap: '1rem',
        }}
      >
        {isAllLocked ? (
          <ShieldCheck size={28} color="#10b981" />
        ) : (
          <ShieldAlert size={28} color="#f59e0b" />
        )}
        <div>
          <h4 style={{ fontSize: '1rem', fontWeight: 600, color: isAllLocked ? '#6ee7b7' : '#fcd34d' }}>
            {isAllLocked ? 'Projet Intégralement Verrouillé & Validé' : 'Validation Ingénieur en cours'}
          </h4>
          <p style={{ fontSize: '0.85rem', color: 'var(--text-muted)' }}>
            {isAllLocked
              ? 'Toutes les sections sont verrouillées. Aucune modification non autorisée ne peut intervenir lors de l\'exportation du devis.'
              : `${lockedCount} sur ${allElements.length} sections verrouillées. Cliquez sur le cadenas à droite de chaque ligne pour la verrouiller.`}
          </p>
        </div>
      </div>

      {/* Liste interactive des éléments */}
      <div style={{ marginBottom: '2.5rem' }}>
        <h3 style={{ fontSize: '1.1rem', fontWeight: 600, marginBottom: '1rem' }}>
          Gestion et Verrouillage Éléments par Éléments
        </h3>

        {allElements.length === 0 ? (
          <div style={{ padding: '1.5rem', textAlign: 'center', background: 'rgba(255,255,255,0.02)', borderRadius: '12px', border: '1px dashed var(--core-border)' }}>
            <p style={{ color: 'var(--text-muted)', fontSize: '0.9rem' }}>
              Aucun élément structurel à verrouiller. Veuillez vérifier l'étape précédente.
            </p>
          </div>
        ) : (
          allElements.map((item) => (
            <div key={item.id} className={`element-card ${item.locked ? 'is-locked' : ''}`} style={{ marginBottom: '1rem', padding: '1rem', background: 'rgba(255,255,255,0.03)', borderRadius: '12px', border: '1px solid var(--core-border)' }}>
              <div className="element-card-header" style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '0.75rem' }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: '0.75rem' }}>
                  <span className="badge badge-info">{item.category}</span>
                  <strong style={{ fontSize: '1rem' }}>{item.id} — {item.name || `${item.category} ${item.id}`}</strong>
                </div>

                <div style={{ display: 'flex', alignItems: 'center', gap: '1rem' }}>
                  <span className={item.locked ? 'badge badge-locked' : 'badge badge-unlocked'}>
                    {item.locked ? <Lock size={12} /> : <Unlock size={12} />}
                    {item.locked ? 'SECTION VERROUILLÉE' : 'MODIFIABLE'}
                  </span>

                  <button
                    className={`btn ${item.locked ? 'btn-secondary' : 'btn-success'}`}
                    style={{ padding: '0.4rem 0.8rem', fontSize: '0.8rem' }}
                    disabled={validatingId === item.id}
                    onClick={() => toggleLock(item.id, item.category)}
                  >
                    {item.locked ? <Unlock size={14} /> : <Lock size={14} />}
                    <span>
                      {validatingId === item.id
                        ? 'Validation...'
                        : item.locked
                        ? 'Déverrouiller'
                        : 'Valider & Verrouiller'}
                    </span>
                  </button>
                </div>
              </div>

              <div className="grid-3" style={{ alignItems: 'center' }}>
                <div>
                  <label className="form-label">Section Dimensionnée (b x h)</label>
                  <input
                    type="text"
                    className="form-control"
                    value={item.section || ''}
                    disabled={item.locked}
                    onChange={(e) => updateSection(item.id, item.category, 'section', e.target.value)}
                  />
                </div>

                <div>
                  <label className="form-label">Dispositions de Ferraillage</label>
                  <input
                    type="text"
                    className="form-control"
                    value={item.armatures || item.hauteur || ''}
                    disabled={item.locked}
                    onChange={(e) => updateSection(item.id, item.category, 'armatures', e.target.value)}
                  />
                </div>

                <div style={{ fontSize: '0.85rem', color: 'var(--text-muted)', background: 'rgba(15, 23, 42, 0.4)', padding: '0.75rem', borderRadius: '8px' }}>
                  {item.locked ? (
                    <span style={{ color: '#fca5a5', display: 'flex', alignItems: 'center', gap: '0.35rem' }}>
                      <Lock size={14} /> Section figée par l'ingénieur
                    </span>
                  ) : (
                    <span style={{ color: '#6ee7b7', display: 'flex', alignItems: 'center', gap: '0.35rem' }}>
                      <Edit3 size={14} /> Saisie manuelle autorisée avant verrou
                    </span>
                  )}
                </div>
              </div>
            </div>
          ))
        )}
      </div>

      {/* Postes Complémentaires */}
      <div style={{ marginBottom: '2.5rem' }}>
        <h3 style={{ fontSize: '1.1rem', fontWeight: 600, marginBottom: '1rem', display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
          <HardHat size={20} />
          <span>Postes Complémentaires & Prestations par Lot</span>
        </h3>

        {mainDoeuvreError && (
          <div style={{ padding: '0.85rem 1.1rem', borderRadius: '10px', background: 'rgba(239, 68, 68, 0.1)', border: '1px solid rgba(239, 68, 68, 0.35)', marginBottom: '1rem', fontSize: '0.85rem', color: '#fca5a5' }}>
            {mainDoeuvreError}
          </div>
        )}

        {postesMainDoeuvre.length > 0 && (
          <table className="custom-table" style={{ marginBottom: '1rem' }}>
            <thead>
              <tr>
                <th>Lot</th>
                <th>Mode</th>
                <th>Désignation / Type</th>
                <th>Quantité / Géométrie</th>
                <th>Prix Unitaire</th>
                <th>Montant Total</th>
                <th>Action</th>
              </tr>
            </thead>
            <tbody>
              {postesMainDoeuvre.map((poste) => (
                <tr key={poste.id}>
                  <td><span className="badge badge-info">{poste.lot || 'Généralités'}</span></td>
                  <td><span className="badge badge-warning">{poste.mode || 'simple'}</span></td>
                  <td style={{ fontWeight: 600 }}>{poste.designation || poste.type_poste || 'Poste complémentaire'}</td>
                  <td>{poste.mode === 'ratio' ? JSON.stringify(poste.geometrie || {}) : `${poste.quantite} ${poste.unite || ''}`}</td>
                  <td>{poste.prix_unitaire ? `${Number(poste.prix_unitaire).toLocaleString()} FCFA` : '—'}</td>
                  <td style={{ fontWeight: 700, color: 'var(--accent-emerald)' }}>
                    {Number(poste.montant ?? ((poste.quantite || 0) * (poste.prix_unitaire || 0))).toLocaleString()} FCFA
                  </td>
                  <td>
                    <button
                      className="btn btn-secondary"
                      style={{ padding: '0.35rem 0.6rem' }}
                      onClick={() => onRemovePosteMainDoeuvre(poste.id)}
                      title="Supprimer ce poste"
                    >
                      <Trash2 size={14} color="#ef4444" />
                    </button>
                  </td>
                </tr>
              ))}
              <tr>
                <td colSpan={5} style={{ textAlign: 'right', fontWeight: 600 }}>Sous-total Postes Complémentaires</td>
                <td style={{ fontWeight: 700, color: 'var(--accent-emerald)' }}>
                  {totalMainDoeuvre.toLocaleString()} FCFA
                </td>
                <td></td>
              </tr>
            </tbody>
          </table>
        )}

        {/* Formulaire Bi-mode */}
        <div style={{ background: 'rgba(255,255,255,0.02)', border: '1px solid var(--core-border)', borderRadius: '12px', padding: '1.25rem' }}>
          <div className="grid-2" style={{ marginBottom: '1rem' }}>
            <div>
              <label className="form-label">Lot d'Ouvrage</label>
              <select
                className="form-select"
                value={nouveauPoste.lot}
                onChange={(e) => setNouveauPoste((p) => ({ ...p, lot: e.target.value }))}
              >
                <option value="lot_00_generalites">Lot 00 — Généralités & Installation</option>
                <option value="lot_01_terrassement">Lot 01 — Terrassement & Fouilles</option>
                <option value="lot_02_gros_oeuvre_infrastructure">Lot 02a — Gros Œuvre Infrastructure</option>
                <option value="lot_02_gros_oeuvre_superstructure">Lot 02b — Gros Œuvre Superstructure</option>
                <option value="lot_03_etancheite">Lot 03 — Étanchéité & Isolation</option>
                <option value="lot_04_revêtements">Lot 04 — Revêtements Sols & Murs</option>
                <option value="lot_05_menuiserie">Lot 05 — Menuiserie & Serrurerie</option>
                <option value="lot_06_plomberie_electricite">Lot 06 — Plomberie & Électricité</option>
                <option value="lot_07_peinture_finitions">Lot 07 — Peinture & Finitions</option>
              </select>
            </div>

            <div>
              <label className="form-label">Mode de Saisie</label>
              <select
                className="form-select"
                value={nouveauPoste.mode}
                onChange={(e) => setNouveauPoste((p) => ({ ...p, mode: e.target.value }))}
              >
                <option value="simple">Mode Simple (Désignation, Quantité, Prix)</option>
                <option value="ratio">Mode Ratio (Choix du Type + Géométrie)</option>
              </select>
            </div>
          </div>

          {nouveauPoste.mode === 'simple' ? (
            <div className="grid-4" style={{ alignItems: 'end', gap: '0.75rem' }}>
              <div>
                <label className="form-label">Désignation du Poste</label>
                <input
                  type="text"
                  className="form-control"
                  placeholder="ex : Installation de chantier"
                  value={nouveauPoste.designation}
                  onChange={(e) => setNouveauPoste((p) => ({ ...p, designation: e.target.value }))}
                />
              </div>
              <div>
                <label className="form-label">Unité</label>
                <select
                  className="form-select"
                  value={nouveauPoste.unite}
                  onChange={(e) => setNouveauPoste((p) => ({ ...p, unite: e.target.value }))}
                >
                  <option value="forfait">Forfait</option>
                  <option value="m²">m²</option>
                  <option value="m³">m³</option>
                  <option value="kg">kg</option>
                  <option value="jour">Jour</option>
                  <option value="unité">Unité</option>
                </select>
              </div>
              <div>
                <label className="form-label">Quantité</label>
                <input
                  type="number"
                  min="0"
                  step="0.01"
                  className="form-control"
                  placeholder="ex : 1"
                  value={nouveauPoste.quantite}
                  onChange={(e) => setNouveauPoste((p) => ({ ...p, quantite: e.target.value }))}
                />
              </div>
              <div>
                <label className="form-label">Prix Unitaire (FCFA)</label>
                <input
                  type="number"
                  min="0"
                  step="1"
                  className="form-control"
                  placeholder="ex : 150000"
                  value={nouveauPoste.prixUnitaire}
                  onChange={(e) => setNouveauPoste((p) => ({ ...p, prixUnitaire: e.target.value }))}
                />
              </div>
            </div>
          ) : (
            <div className="grid-2" style={{ alignItems: 'end', gap: '1rem' }}>
              <div>
                <label className="form-label">Type de Prestation Ratio</label>
                <select
                  className="form-select"
                  value={nouveauPoste.typePoste}
                  onChange={(e) => setNouveauPoste((p) => ({ ...p, typePoste: e.target.value }))}
                >
                  <option value="maconnerie_creuse">Maçonnerie agglos creux (Surface m²)</option>
                  <option value="maconnerie_pleine">Maçonnerie agglos pleins (Surface m²)</option>
                  <option value="enduit_interieur">Enduit ciment intérieur (Surface m²)</option>
                  <option value="enduit_exterieur">Enduit ciment extérieur (Surface m²)</option>
                  <option value="chainage_linteau">Chaînage / Linteau (Longueur ml)</option>
                  <option value="chape_mortier">Chape mortier de lissage (Surface m²)</option>
                </select>
              </div>
              <div>
                <label className="form-label">
                  {(nouveauPoste.typePoste || '').includes('chainage') ? 'Longueur (ml)' : 'Surface (m²)'}
                </label>
                <input
                  type="number"
                  min="0"
                  step="0.1"
                  className="form-control"
                  placeholder="ex : 45.0"
                  value={nouveauPoste.valeurGeometrie}
                  onChange={(e) => setNouveauPoste((p) => ({ ...p, valeurGeometrie: e.target.value }))}
                />
              </div>
            </div>
          )}

          <button
            className="btn btn-success"
            style={{ marginTop: '1.1rem' }}
            disabled={posteEnCours}
            onClick={handleAjouterPoste}
          >
            <Plus size={16} />
            <span>{posteEnCours ? 'Ajout...' : 'Ajouter ce Poste Complémentaire'}</span>
          </button>
        </div>
      </div>

      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
        <button className="btn btn-secondary" onClick={onBack}>
          <ArrowLeft size={18} />
          <span>Retour aux calculs</span>
        </button>

        <button className="btn btn-primary" onClick={onNext}>
          <span>Passer au Plan de Fondation & Exports DQE</span>
          <ArrowRight size={18} />
        </button>
      </div>
    </div>
  );
}