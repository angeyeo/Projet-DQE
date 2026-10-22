import React, { useMemo, useRef, useState } from 'react';
import { Minus, Plus, Trash2, X } from 'lucide-react';

// Éditeur de poteaux sur un fond de plan d'architecte (issue #93).
// Le fond (traits du DXF) n'est qu'un repère visuel : aucun poteau n'en est
// déduit. Chaque poteau est placé par l'utilisateur (clic ou coordonnées).
// Repère : mètres, origine = coin inférieur gauche du dessin, Y vers le haut.

const PAS_ARRONDI_M = 0.05;
const DISTANCE_MIN_M = 0.3; // même règle que le serveur (doublon probable)
const ZOOMS = [1, 2, 4];

const nf = (v) => (Math.round(v * 100) / 100).toLocaleString('fr-FR', { maximumFractionDigits: 2 });
const arrondir = (v) => Math.round(v / PAS_ARRONDI_M) * PAS_ARRONDI_M;

function doublon(poteaux, x, y, ignorer = -1) {
  return poteaux.findIndex((p, i) => i !== ignorer && Math.hypot(p.x - x, p.y - y) < DISTANCE_MIN_M);
}

export default function EditeurPoteaux({ fond, poteaux, onChange, desactive = false }) {
  const svgRef = useRef(null);
  const [selection, setSelection] = useState(null);
  const [curseur, setCurseur] = useState(null);
  const [arrondi, setArrondi] = useState(true);
  const [zoom, setZoom] = useState(1);
  const [message, setMessage] = useState(null);
  const [saisie, setSaisie] = useState({ x: '', y: '' });
  const [confirmerEffacement, setConfirmerEffacement] = useState(false);

  const L = Math.max(fond.largeur_m, 1);
  const P = Math.max(fond.profondeur_m, 1);
  const marge = Math.max(L, P) * 0.04;
  const cote = Math.max(0.25, Math.max(L, P) * 0.012); // taille d'affichage d'un poteau
  const traits = useMemo(
    () => fond.segments.map(([x1, y1, x2, y2]) => `M${x1} ${P - y1}L${x2} ${P - y2}`).join(''),
    [fond.segments, P],
  );

  // Position du pointeur en mètres dans le repère du plan.
  const versPlan = (evt) => {
    const svg = svgRef.current;
    const pt = svg.createSVGPoint();
    pt.x = evt.clientX;
    pt.y = evt.clientY;
    const p = pt.matrixTransform(svg.getScreenCTM().inverse());
    const x = arrondi ? arrondir(p.x) : p.x;
    const y = arrondi ? arrondir(P - p.y) : P - p.y;
    return { x: Math.round(x * 1000) / 1000, y: Math.round(y * 1000) / 1000 };
  };

  const ajouter = (x, y) => {
    const i = doublon(poteaux, x, y);
    if (i >= 0) {
      setMessage(`Trop près du poteau n° ${i + 1} (moins de ${DISTANCE_MIN_M * 100} cm) : poteau non ajouté.`);
      return false;
    }
    setMessage(null);
    onChange([...poteaux, { x, y }]);
    setSelection(poteaux.length);
    return true;
  };

  const modifier = (i, champ, valeur) => {
    const v = Number(valeur);
    if (valeur === '' || !Number.isFinite(v)) return;
    const suivant = { ...poteaux[i], [champ]: v };
    const j = doublon(poteaux, suivant.x, suivant.y, i);
    setMessage(j >= 0 ? `Le poteau n° ${i + 1} est à moins de ${DISTANCE_MIN_M * 100} cm du n° ${j + 1}.` : null);
    onChange(poteaux.map((p, k) => (k === i ? suivant : p)));
  };

  const supprimer = (i) => {
    onChange(poteaux.filter((_, k) => k !== i));
    setSelection(null);
    setMessage(null);
  };

  const ajouterSaisie = (e) => {
    e.preventDefault();
    const x = Number(saisie.x);
    const y = Number(saisie.y);
    if (saisie.x === '' || saisie.y === '' || !Number.isFinite(x) || !Number.isFinite(y)) {
      setMessage('Saisissez les deux coordonnées X et Y en mètres.');
      return;
    }
    if (ajouter(x, y)) setSaisie({ x: '', y: '' });
  };

  const surClavier = (e) => {
    if (selection === null || desactive) return;
    if (e.key === 'Delete' || e.key === 'Backspace') { e.preventDefault(); supprimer(selection); }
    if (e.key === 'Escape') setSelection(null);
  };

  const echelle = L > 30 ? 10 : L > 8 ? 5 : 1; // barre d'échelle en mètres

  return (
    <div className="editeur-poteaux" onKeyDown={surClavier}>
      <div className="editeur-barre">
        <span className="editeur-compte"><strong>{poteaux.length}</strong> poteau(x) placé(s)</span>
        <label className="editeur-option">
          <input type="checkbox" checked={arrondi} onChange={(e) => setArrondi(e.target.checked)} />
          Arrondir les clics à 5 cm
        </label>
        <div className="editeur-zoom" role="group" aria-label="Zoom du plan">
          <button type="button" className="btn btn-secondary btn-icone" aria-label="Zoom arrière"
            disabled={zoom === ZOOMS[0]} onClick={() => setZoom(ZOOMS[ZOOMS.indexOf(zoom) - 1])}><Minus size={16} /></button>
          <span aria-live="polite">× {zoom}</span>
          <button type="button" className="btn btn-secondary btn-icone" aria-label="Zoom avant"
            disabled={zoom === ZOOMS[ZOOMS.length - 1]} onClick={() => setZoom(ZOOMS[ZOOMS.indexOf(zoom) + 1])}><Plus size={16} /></button>
        </div>
        <span className="editeur-curseur" aria-hidden="true">
          {curseur ? `X ${nf(curseur.x)} m · Y ${nf(curseur.y)} m` : 'Cliquez sur le plan pour placer un poteau'}
        </span>
      </div>

      <div className="editeur-cadre">
        <svg
          ref={svgRef}
          className={desactive ? 'editeur-svg desactive' : 'editeur-svg'}
          style={{ width: `${zoom * 100}%` }}
          viewBox={`${-marge} ${-marge} ${L + 2 * marge} ${P + 4 * marge}`}
          data-profondeur={P}
          role="img"
          aria-label={`Fond de plan de ${nf(fond.largeur_m)} × ${nf(fond.profondeur_m)} m avec ${poteaux.length} poteau(x) placé(s). La liste des poteaux sous le plan permet de les modifier au clavier.`}
          onClick={(e) => { if (!desactive) { const { x, y } = versPlan(e); ajouter(x, y); } }}
          onMouseMove={(e) => setCurseur(versPlan(e))}
          onMouseLeave={() => setCurseur(null)}
        >
          <path d={traits} className="editeur-fond" vectorEffect="non-scaling-stroke" />
          <g className="editeur-echelle" transform={`translate(0 ${P + marge * 1.8})`}>
            <line x1="0" y1="0" x2={echelle} y2="0" vectorEffect="non-scaling-stroke" />
            <text x={echelle + marge * 0.3} y={marge * 0.25} fontSize={marge * 0.7}>{echelle} m</text>
          </g>
          {poteaux.map((p, i) => (
            <g key={i} className={i === selection ? 'editeur-poteau selection' : 'editeur-poteau'}
              onClick={(e) => { e.stopPropagation(); setSelection(i); }}>
              <rect x={p.x - cote / 2} y={P - p.y - cote / 2} width={cote} height={cote} />
              <text x={p.x + cote * 0.7} y={P - p.y - cote * 0.7} fontSize={cote * 0.9}>{i + 1}</text>
            </g>
          ))}
        </svg>
      </div>

      {message && <p className="editeur-message" role="alert">{message}</p>}

      <div className="editeur-panneaux">
        <form className="editeur-saisie" onSubmit={ajouterSaisie}>
          <span className="form-label">Ajouter un poteau par ses coordonnées</span>
          <div className="editeur-champs">
            <label>X (m)<input type="number" step="0.01" className="form-control" value={saisie.x}
              onChange={(e) => setSaisie((s) => ({ ...s, x: e.target.value }))} disabled={desactive} /></label>
            <label>Y (m)<input type="number" step="0.01" className="form-control" value={saisie.y}
              onChange={(e) => setSaisie((s) => ({ ...s, y: e.target.value }))} disabled={desactive} /></label>
            <button type="submit" className="btn btn-secondary" disabled={desactive}>Ajouter</button>
          </div>
        </form>

        {selection !== null && poteaux[selection] && (
          <div className="editeur-selection">
            <span className="form-label">Poteau n° {selection + 1}</span>
            <div className="editeur-champs">
              <label>X (m)<input type="number" step="0.01" className="form-control" value={poteaux[selection].x}
                onChange={(e) => modifier(selection, 'x', e.target.value)} disabled={desactive} /></label>
              <label>Y (m)<input type="number" step="0.01" className="form-control" value={poteaux[selection].y}
                onChange={(e) => modifier(selection, 'y', e.target.value)} disabled={desactive} /></label>
              <button type="button" className="btn btn-secondary" onClick={() => supprimer(selection)} disabled={desactive}>
                <Trash2 size={16} /> <span>Supprimer</span>
              </button>
              <button type="button" className="btn btn-secondary btn-icone" aria-label="Fermer la sélection"
                onClick={() => setSelection(null)}><X size={16} /></button>
            </div>
          </div>
        )}
      </div>

      {poteaux.length > 0 && (
        <details className="editeur-liste">
          <summary>Liste des {poteaux.length} poteau(x) et coordonnées</summary>
          <ol>
            {poteaux.map((p, i) => (
              <li key={i}>
                <button type="button" className="lien" onClick={() => setSelection(i)}>
                  n° {i + 1} : X {nf(p.x)} m · Y {nf(p.y)} m
                </button>
              </li>
            ))}
          </ol>
          {confirmerEffacement ? (
            <div className="editeur-champs">
              <button type="button" className="btn btn-secondary" onClick={() => { onChange([]); setSelection(null); setConfirmerEffacement(false); }}>
                Confirmer : effacer les {poteaux.length} poteaux
              </button>
              <button type="button" className="btn btn-secondary" onClick={() => setConfirmerEffacement(false)}>Annuler</button>
            </div>
          ) : (
            <button type="button" className="btn btn-secondary" disabled={desactive} onClick={() => setConfirmerEffacement(true)}>
              Tout effacer
            </button>
          )}
        </details>
      )}
    </div>
  );
}
