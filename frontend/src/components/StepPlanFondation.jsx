import React, { useState, useEffect } from 'react';
import { ArrowLeft, ArrowRight, Download, CheckCircle, AlertTriangle, Grid } from 'lucide-react';
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
      setErrorMsg("Impossible de charger le plan depuis l'API backend (Mode local actif).");
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
      console.warn("Erreur validation plan :", err.message);
      onNext();
    } finally {
      setValidating(false);
    }
  };

  const listSemelles = (planData && planData.semelles) || (sections && sections.semelles) || [];

  // Calcul de l'échelle d'affichage du plan SVG.
  // Les coordonnées (position_x/position_y) sont des coordonnées réelles en
  // mètres (ex. issues d'un import IFC), potentiellement très éloignées de
  // (0,0) et sur une grande amplitude (ex. -234.18, -44.29). Un facteur fixe
  // (ancien code : position_x * 40) plaçait donc les semelles à des milliers
  // de pixels hors du viewBox -- rien ne se dessinait. On normalise ici les
  // positions dans le cadre disponible, quelle que soit leur amplitude.
  const VB_W = 600;
  const VB_H = 420;
  const PAD = 55;
  const drawW = VB_W - PAD * 2;
  const drawH = VB_H - PAD * 2;

  const semellesPositionnees = listSemelles.filter(
    (s) => typeof s.position_x === 'number' && typeof s.position_y === 'number'
      && !Number.isNaN(s.position_x) && !Number.isNaN(s.position_y)
  );

  let projeter = (x, y) => [VB_W / 2, VB_H / 2];
  let echellePxParM = 20;

  if (semellesPositionnees.length > 0) {
    const xs = semellesPositionnees.map((s) => s.position_x);
    const ys = semellesPositionnees.map((s) => s.position_y);
    const minX = Math.min(...xs);
    const maxX = Math.max(...xs);
    const minY = Math.min(...ys);
    const maxY = Math.max(...ys);
    const spanX = maxX - minX || 1;
    const spanY = maxY - minY || 1;

    const scale = Math.min(drawW / spanX, drawH / spanY);
    echellePxParM = scale;
    const offsetX = PAD + (drawW - spanX * scale) / 2;
    const offsetY = PAD + (drawH - spanY * scale) / 2;

    projeter = (x, y) => {
      const px = offsetX + (x - minX) * scale;
      // Axe Y inversé : Y croissant (nord) vers le haut du plan.
      const py = offsetY + (drawH - (y - minY) * scale);
      return [px, py];
    };
  }

  return (
    <div className="glass-panel">
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '1.5rem' }}>
        <div>
          <div className="badge badge-info" style={{ marginBottom: '0.4rem' }}>Étape 3bis — Plan de Fondation</div>
          <h2 style={{ fontSize: '1.5rem', fontWeight: 700 }}>
            Plan de Fondation & Implantation de la Trame (.DXF)
          </h2>
          <p style={{ color: 'var(--text-muted)', fontSize: '0.85rem', marginTop: '0.25rem' }}>
            Positions en coordonnées réelles calculées selon la trame structurelle de l'ouvrage.
          </p>
          <div style={{ display: 'inline-flex', alignItems: 'center', gap: '0.4rem', background: 'rgba(245, 158, 11, 0.1)', color: '#fcd34d', border: '1px solid rgba(245, 158, 11, 0.3)', padding: '0.4rem 0.85rem', borderRadius: '8px', fontSize: '0.8rem', marginTop: '0.6rem', fontWeight: 500 }}>
            <AlertTriangle size={15} />
            <span>Positions calculées depuis une trame régulière. Précisez le plan d'exécution pour les bâtiments complexes.</span>
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
        <div style={{ background: 'rgba(239, 68, 68, 0.1)', border: '1px solid rgba(239, 68, 68, 0.35)', color: '#fca5a5', padding: '0.75rem 1rem', borderRadius: '8px', marginBottom: '1.5rem', fontSize: '0.85rem' }}>
          {errorMsg}
        </div>
      )}

      {/* Rendu Graphique SVG */}
      {listSemelles.length > 0 && (
        <div style={{ marginBottom: '2rem', textAlign: 'center' }}>
          <h4 style={{ fontSize: '0.95rem', fontWeight: 600, marginBottom: '0.75rem', color: 'var(--text-muted)' }}>
            Aperçu Graphique de l'Implantation des Semelles (Trame)
          </h4>
          <svg viewBox={`0 0 ${VB_W} ${VB_H}`} style={{ width: '100%', maxWidth: 480, background: 'rgba(15, 23, 42, 0.6)', border: '1px solid var(--core-border)', borderRadius: '12px', padding: '0.5rem' }}>
            {listSemelles.map((s, idx) => {
              const positionConnue = typeof s.position_x === 'number' && typeof s.position_y === 'number'
                && !Number.isNaN(s.position_x) && !Number.isNaN(s.position_y);
              const [posX, posY] = positionConnue
                ? projeter(s.position_x, s.position_y)
                // Repli en grille si la position réelle est indisponible (ex. saisie manuelle).
                : [PAD + (idx % 4) * (drawW / 4) + drawW / 8, PAD + Math.floor(idx / 4) * 50 + 20];
              const cote = (parseFloat(s.cote_cm) || 120) / 100; // mètres
              const size = Math.max(10, Math.min(45, cote * echellePxParM));
              const label = s.identifiant || s.id || `S${idx + 1}`;
              const labelW = Math.max(18, label.length * 5.4 + 6);
              return (
                <g key={s.identifiant || idx} transform={`translate(${posX}, ${posY})`}>
                  <rect
                    x={-size / 2} y={-size / 2}
                    width={size} height={size}
                    fill="rgba(59, 130, 246, 0.2)" stroke="#3b82f6" strokeWidth="1.5" rx="3"
                  />
                  {/* Fond derrière l'étiquette : évite qu'elle se fonde dans un
                      texte voisin quand deux semelles sont proches sur le plan. */}
                  <rect
                    x={-labelW / 2} y={-size / 2 - 15}
                    width={labelW} height={12}
                    fill="rgba(15, 23, 42, 0.85)" rx="2"
                  />
                  <text x="0" y={-size / 2 - 6} fontSize="9" fontWeight="bold" fill="#93c5fd" textAnchor="middle">
                    {label}
                  </text>
                </g>
              );
            })}
          </svg>
        </div>
      )}

      {/* Tableau des semelles */}
      <div style={{ marginBottom: '2rem' }}>
        <h3 style={{ fontSize: '1.05rem', fontWeight: 600, marginBottom: '1rem', display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
          <Grid size={18} color="var(--accent-primary)" />
          <span>Coordonnées & Dimensions des Semelles</span>
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
                <th>Coordonnées (X, Y)</th>
                <th>Statut Implantation</th>
              </tr>
            </thead>
            <tbody>
              {listSemelles.length > 0 ? (
                listSemelles.map((sem, idx) => (
                  <tr key={idx}>
                    <td style={{ fontWeight: 700, color: '#93c5fd' }}>{sem.identifiant || sem.id || `S${idx + 1}`}</td>
                    <td>{sem.name || sem.designation || 'Semelle de fondation'}</td>
                    <td style={{ fontWeight: 600 }}>{sem.section || `${sem.largeur_m || 1.2} x ${sem.hauteur_m || 0.4} m`}</td>
                    <td>{sem.position_x !== undefined ? `(${sem.position_x} m, ${sem.position_y} m)` : 'Grille (0,0)'}</td>
                    <td>
                      <span className="badge badge-success" style={{ display: 'inline-flex', alignItems: 'center', gap: '0.3rem' }}>
                        <CheckCircle size={14} />
                        <span>Implanté sur Grille</span>
                      </span>
                    </td>
                  </tr>
                ))
              ) : (
                <tr>
                  <td colSpan="5" style={{ textAlign: 'center', color: 'var(--text-muted)', padding: '2rem' }}>
                    Aucune semelle disponible.
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