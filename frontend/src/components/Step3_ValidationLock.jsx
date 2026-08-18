import React, { useState } from 'react';
import { Lock, Unlock, CheckCircle, ShieldAlert, ArrowLeft, ArrowRight, Edit3, ShieldCheck, HardHat, Plus, Trash2 } from 'lucide-react';

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

  // AJOUTÉ : formulaire local d'ajout d'un poste de main d'œuvre
  // (saisie libre par l'ingénieur, distincte des éléments calculés).
  const [nouveauPoste, setNouveauPoste] = useState({
    designation: '',
    unite: 'forfait',
    quantite: '',
    prixUnitaire: '',
  });
  const [posteEnCours, setPosteEnCours] = useState(false);

  const handleAjouterPoste = async () => {
    const quantite = parseFloat(nouveauPoste.quantite);
    const prixUnitaire = parseFloat(nouveauPoste.prixUnitaire);
    if (!nouveauPoste.designation.trim() || !quantite || quantite <= 0 || !prixUnitaire || prixUnitaire <= 0) {
      return; // le bouton est de toute façon désactivé tant que ce n'est pas rempli
    }
    setPosteEnCours(true);
    await onAddPosteMainDoeuvre({ ...nouveauPoste, quantite, prixUnitaire });
    setPosteEnCours(false);
    setNouveauPoste({ designation: '', unite: 'forfait', quantite: '', prixUnitaire: '' });
  };

  const totalMainDoeuvre = postesMainDoeuvre.reduce(
    (sum, p) => sum + (p.montant ?? p.quantite * p.prix_unitaire),
    0
  );

  const allElements = [
    ...poteaux.map(p => ({ ...p, category: 'Poteau' })),
    ...poutres.map(p => ({ ...p, category: 'Poutre' })),
    ...semelles.map(s => ({ ...s, category: 'Semelle' })),
  ];

  const lockedCount = allElements.filter(e => e.locked).length;
  const isAllLocked = lockedCount === allElements.length;

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

        <button
          className={`btn ${isAllLocked ? 'btn-warning' : 'btn-success'}`}
          onClick={() => toggleLockAll(!isAllLocked)}
        >
          {isAllLocked ? <Unlock size={18} /> : <Lock size={18} />}
          <span>{isAllLocked ? 'Déverrouiller Tout' : 'Verrouiller Toutes les Sections'}</span>
        </button>
      </div>

      {/* AJOUTÉ : le message d'erreur de validation (validationError) était
          déjà remonté par App.jsx (ex. "Renseignez un côté valide...",
          échec réseau, 400/503...) mais n'était jamais affiché ici --
          l'ingénieur voyait la validation échouer sans aucune explication. */}
      {validationError && (
        <div
          style={{
            padding: '1rem 1.25rem',
            borderRadius: '12px',
            background: 'rgba(239, 68, 68, 0.1)',
            border: '1px solid rgba(239, 68, 68, 0.35)',
            marginBottom: '1.5rem',
            display: 'flex',
            alignItems: 'flex-start',
            gap: '0.75rem',
          }}
        >
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

      {/* Liste interactive des éléments avec Verrouillage */}
      <div style={{ marginBottom: '2.5rem' }}>
        <h3 style={{ fontSize: '1.1rem', fontWeight: 600, marginBottom: '1rem' }}>
          Gestion et Verrouillage Éléments par Éléments
        </h3>

        {allElements.map((item) => (
          <div key={item.id} className={`element-card ${item.locked ? 'is-locked' : ''}`}>
            <div className="element-card-header">
              <div style={{ display: 'flex', alignItems: 'center', gap: '0.75rem' }}>
                <span className="badge badge-info">{item.category}</span>
                <strong style={{ fontSize: '1rem' }}>{item.id} — {item.name}</strong>
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

            {item.calculIndisponible ? (
              <div className="grid-3" style={{ alignItems: 'start' }}>
                <div
                  style={{
                    gridColumn: '1 / -1',
                    marginBottom: '0.5rem',
                    padding: '0.6rem 0.9rem',
                    borderRadius: '8px',
                    background: 'rgba(245, 158, 11, 0.1)',
                    border: '1px solid rgba(245, 158, 11, 0.3)',
                    fontSize: '0.82rem',
                    color: '#b45309',
                  }}
                >
                  ⚠ Calcul automatique indisponible pour cet élément
                  {item.erreurCalcul ? ` (${item.erreurCalcul})` : ''}. Saisissez les
                  dimensions retenues manuellement pour pouvoir la verrouiller.
                </div>

                {item.category === 'Poteau' && (
                  <div>
                    <label className="form-label">Côté du poteau (cm)</label>
                    <input
                      type="number"
                      min="1"
                      step="1"
                      className="form-control"
                      placeholder="ex : 25"
                      value={item.manualCoteCm || ''}
                      disabled={item.locked}
                      onChange={(e) => updateSection(item.id, item.category, 'manualCoteCm', e.target.value)}
                    />
                  </div>
                )}

                {item.category === 'Poutre' && (
                  <>
                    <div>
                      <label className="form-label">Largeur (cm)</label>
                      <input
                        type="number"
                        min="1"
                        step="1"
                        className="form-control"
                        placeholder="ex : 25"
                        value={item.manualLargeurCm || ''}
                        disabled={item.locked}
                        onChange={(e) => updateSection(item.id, item.category, 'manualLargeurCm', e.target.value)}
                      />
                    </div>
                    <div>
                      <label className="form-label">Hauteur (cm)</label>
                      <input
                        type="number"
                        min="1"
                        step="1"
                        className="form-control"
                        placeholder="ex : 80"
                        value={item.manualHauteurCm || ''}
                        disabled={item.locked}
                        onChange={(e) => updateSection(item.id, item.category, 'manualHauteurCm', e.target.value)}
                      />
                    </div>
                  </>
                )}

                {item.category === 'Semelle' && (
                  <>
                    <div>
                      <label className="form-label">Côté (cm)</label>
                      <input
                        type="number"
                        min="1"
                        step="1"
                        className="form-control"
                        placeholder="ex : 160"
                        value={item.manualCoteCm || ''}
                        disabled={item.locked}
                        onChange={(e) => updateSection(item.id, item.category, 'manualCoteCm', e.target.value)}
                      />
                    </div>
                    <div>
                      <label className="form-label">Hauteur (cm)</label>
                      <input
                        type="number"
                        min="1"
                        step="1"
                        className="form-control"
                        placeholder="ex : 40"
                        value={item.manualHauteurCm || ''}
                        disabled={item.locked}
                        onChange={(e) => updateSection(item.id, item.category, 'manualHauteurCm', e.target.value)}
                      />
                    </div>
                  </>
                )}
              </div>
            ) : (
              <div className="grid-3" style={{ alignItems: 'center' }}>
                <div>
                  <label className="form-label">Section Dimensionnée (b x h)</label>
                  <input
                    type="text"
                    className="form-control"
                    value={item.section}
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
            )}
          </div>
        ))}
      </div>

      {/* AJOUTÉ : le backend gère déjà entièrement les postes de main
          d'œuvre (modèle PosteMainDoeuvre, intégrés au sous-total du
          DQE et aux exports PDF/Excel) mais aucune interface ne
          permettait à l'ingénieur d'en saisir -- ce champ "manquant"
          signalé. Distinct des éléments structurels : saisie 100%
          manuelle (désignation, unité, quantité, prix unitaire),
          jamais calculée automatiquement. */}
      <div style={{ marginBottom: '2.5rem' }}>
        <h3 style={{ fontSize: '1.1rem', fontWeight: 600, marginBottom: '1rem', display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
          <HardHat size={20} />
          <span>Main d'Œuvre & Prestations Complémentaires</span>
        </h3>

        {mainDoeuvreError && (
          <div
            style={{
              padding: '0.85rem 1.1rem',
              borderRadius: '10px',
              background: 'rgba(239, 68, 68, 0.1)',
              border: '1px solid rgba(239, 68, 68, 0.35)',
              marginBottom: '1rem',
              fontSize: '0.85rem',
              color: '#fca5a5',
            }}
          >
            {mainDoeuvreError}
          </div>
        )}

        {postesMainDoeuvre.length > 0 && (
          <table className="custom-table" style={{ marginBottom: '1rem' }}>
            <thead>
              <tr>
                <th>Désignation</th>
                <th>Unité</th>
                <th>Quantité</th>
                <th>Prix Unitaire (FCFA)</th>
                <th>Montant (FCFA)</th>
                <th></th>
              </tr>
            </thead>
            <tbody>
              {postesMainDoeuvre.map((poste) => (
                <tr key={poste.id}>
                  <td style={{ fontWeight: 600 }}>{poste.designation}</td>
                  <td><span className="badge badge-info">{poste.unite}</span></td>
                  <td>{poste.quantite}</td>
                  <td>{Number(poste.prix_unitaire).toLocaleString()}</td>
                  <td style={{ fontWeight: 700, color: 'var(--accent-emerald)' }}>
                    {Number(poste.montant ?? poste.quantite * poste.prix_unitaire).toLocaleString()}
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
                <td colSpan={4} style={{ textAlign: 'right', fontWeight: 600 }}>Sous-total Main d'Œuvre</td>
                <td style={{ fontWeight: 700, color: 'var(--accent-emerald)' }}>
                  {totalMainDoeuvre.toLocaleString()} FCFA
                </td>
                <td></td>
              </tr>
            </tbody>
          </table>
        )}

        <div className="grid-4" style={{ alignItems: 'end', gap: '0.75rem' }}>
          <div>
            <label className="form-label">Désignation</label>
            <input
              type="text"
              className="form-control"
              placeholder="ex : Main d'œuvre coffrage"
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
        <button
          className="btn btn-success"
          style={{ marginTop: '0.85rem' }}
          disabled={
            posteEnCours ||
            !nouveauPoste.designation.trim() ||
            !nouveauPoste.quantite ||
            !nouveauPoste.prixUnitaire
          }
          onClick={handleAjouterPoste}
        >
          <Plus size={16} />
          <span>{posteEnCours ? 'Ajout...' : 'Ajouter le Poste'}</span>
        </button>
      </div>

      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
        <button className="btn btn-secondary" onClick={onBack}>
          <ArrowLeft size={18} />
          <span>Retour aux calculs</span>
        </button>

        <button className="btn btn-primary" onClick={onNext}>
          <span>Générer le Devis Quantitatif (DQE)</span>
          <ArrowRight size={18} />
        </button>
      </div>
    </div>
  );
}