import React, { useMemo, useRef, useState } from 'react';
import { Minus, Plus, Redo2, Trash2, Undo2, X } from 'lucide-react';
import { DISTANCE_MIN_M, PAS_GRILLE_M, accrocher, doublon, emprise } from './accrochage';

// Éditeur de poteaux (issues #93 et #94).
// - Étape 1, plan d'architecte : le fond est le dessin de l'architecte.
// - Étape 2 : le fond est la structure calculée (poutres) et, s'il existe,
//   le plan d'architecte. Les poteaux ajoutés ou déplacés deviennent « saisi ».
// Aucun poteau n'est jamais déduit du fond : il ne sert qu'à se repérer.
// Repère : mètres, Y vers le haut. Les modifications restent locales tant que
// le parent ne les envoie pas au serveur ; elles sont annulables (historique).

const ZOOMS = [1, 2, 4];
const SEUIL_GLISSER_M = 0.05; // en dessous : un clic, pas un déplacement

const nf = (v) => (Math.round(v * 100) / 100).toLocaleString('fr-FR', { maximumFractionDigits: 2 });

export default function EditeurPoteaux({
  fond = null, traitsStructure = [], poteaux, onChange, desactive = false, libelleCompte = 'poteau(x) placé(s)',
}) {
  const svgRef = useRef(null);
  const clicApresGlisse = useRef(false); // le « click » qui suit un glisser ne doit pas ajouter de poteau
  const [selection, setSelection] = useState(null);
  const [curseur, setCurseur] = useState(null);
  const [mode, setMode] = useState('grille');
  const [pas, setPas] = useState(0.05);
  const [zoom, setZoom] = useState(1);
  const [message, setMessage] = useState(null);
  const [saisie, setSaisie] = useState({ x: '', y: '' });
  const [confirmerEffacement, setConfirmerEffacement] = useState(false);
  const [historique, setHistorique] = useState({ passe: [], futur: [] });
  const [glisse, setGlisse] = useState(null); // {i, depart:{x,y}, position:{x,y}, bouge}

  const segmentsFond = fond?.segments || [];
  const e = useMemo(() => emprise([...segmentsFond, ...traitsStructure], poteaux),
    // eslint-disable-next-line react-hooks/exhaustive-deps
    [segmentsFond, traitsStructure, poteaux.length]);
  const L = e.xmax - e.xmin;
  const H = e.ymax - e.ymin;
  const marge = Math.max(L, H) * 0.05;
  const cote = Math.max(0.25, Math.max(L, H) * 0.012); // taille d'affichage d'un poteau
  const tolerance = Math.max(0.3, Math.max(L, H) * 0.02); // accrochage aux poteaux
  const sy = (y) => e.ymax - y; // Y du plan -> Y de l'écran (vers le bas)
  const chemin = (segs) => segs.map(([x1, y1, x2, y2]) => `M${x1} ${sy(y1)}L${x2} ${sy(y2)}`).join('');
  const traitsFond = useMemo(() => chemin(segmentsFond),
    // eslint-disable-next-line react-hooks/exhaustive-deps
    [segmentsFond, e.ymax]);
  const traitsPoutres = useMemo(() => chemin(traitsStructure),
    // eslint-disable-next-line react-hooks/exhaustive-deps
    [traitsStructure, e.ymax]);

  // Toute modification passe ici : historique d'annulation, puis parent.
  const appliquer = (liste) => {
    setHistorique((h) => ({ passe: [...h.passe.slice(-49), poteaux], futur: [] }));
    onChange(liste);
  };
  const annuler = () => {
    if (!historique.passe.length) return;
    const precedent = historique.passe[historique.passe.length - 1];
    setHistorique((h) => ({ passe: h.passe.slice(0, -1), futur: [poteaux, ...h.futur] }));
    setSelection(null);
    setMessage(null);
    onChange(precedent);
  };
  const retablir = () => {
    if (!historique.futur.length) return;
    const [suivant, ...reste] = historique.futur;
    setHistorique((h) => ({ passe: [...h.passe, poteaux], futur: reste }));
    setSelection(null);
    onChange(suivant);
  };

  const pointeurBrut = (evt) => {
    const svg = svgRef.current;
    const pt = svg.createSVGPoint();
    pt.x = evt.clientX;
    pt.y = evt.clientY;
    const p = pt.matrixTransform(svg.getScreenCTM().inverse());
    return { x: p.x, y: e.ymax - p.y };
  };
  const pointeur = (evt, ignorer = -1) => accrocher(pointeurBrut(evt), mode, { pas, poteaux, tolerance, ignorer });

  const ajouter = (x, y) => {
    const i = doublon(poteaux, x, y);
    if (i >= 0) {
      setMessage(`Trop près du poteau n° ${i + 1} (moins de ${DISTANCE_MIN_M * 100} cm) : poteau non ajouté.`);
      return false;
    }
    setMessage(null);
    appliquer([...poteaux, { x, y, origine: 'saisi' }]);
    setSelection(poteaux.length);
    return true;
  };

  const deplacer = (i, x, y) => {
    const j = doublon(poteaux, x, y, i);
    if (j >= 0) {
      setMessage(`Déplacement refusé : le poteau n° ${i + 1} serait à moins de ${DISTANCE_MIN_M * 100} cm du n° ${j + 1}.`);
      return;
    }
    setMessage(null);
    appliquer(poteaux.map((p, k) => (k === i ? { ...p, x, y, origine: 'saisi' } : p)));
  };

  const modifierChamp = (i, champ, valeur) => {
    const v = Number(valeur);
    if (valeur === '' || !Number.isFinite(v)) return;
    const p = { ...poteaux[i], [champ]: v };
    deplacer(i, p.x, p.y);
  };

  const supprimer = (i) => {
    appliquer(poteaux.filter((_, k) => k !== i));
    setSelection(null);
    setMessage(null);
  };

  const ajouterSaisie = (evt) => {
    evt.preventDefault();
    const x = Number(saisie.x);
    const y = Number(saisie.y);
    if (saisie.x === '' || saisie.y === '' || !Number.isFinite(x) || !Number.isFinite(y)) {
      setMessage('Saisissez les deux coordonnées X et Y en mètres.');
      return;
    }
    if (ajouter(x, y)) setSaisie({ x: '', y: '' });
  };

  // Glisser-déposer d'un poteau (souris, stylet ou doigt).
  const debutGlisse = (evt, i) => {
    if (desactive) return;
    evt.stopPropagation();
    evt.currentTarget.setPointerCapture?.(evt.pointerId);
    setSelection(i);
    setGlisse({ i, depart: pointeurBrut(evt), position: { x: poteaux[i].x, y: poteaux[i].y }, bouge: false });
  };
  const surDeplacement = (evt) => {
    if (glisse) {
      const brut = pointeurBrut(evt);
      const bouge = glisse.bouge || Math.hypot(brut.x - glisse.depart.x, brut.y - glisse.depart.y) > SEUIL_GLISSER_M;
      setGlisse({ ...glisse, bouge, position: bouge ? pointeur(evt, glisse.i) : glisse.position });
    }
    setCurseur(pointeur(evt));
  };
  const finGlisse = () => {
    if (glisse?.bouge) {
      clicApresGlisse.current = true;
      deplacer(glisse.i, glisse.position.x, glisse.position.y);
    }
    setGlisse(null);
  };

  const surClavier = (evt) => {
    const mod = evt.ctrlKey || evt.metaKey;
    if (mod && evt.key.toLowerCase() === 'z' && !evt.shiftKey) { evt.preventDefault(); annuler(); return; }
    if (mod && (evt.key.toLowerCase() === 'y' || (evt.key.toLowerCase() === 'z' && evt.shiftKey))) {
      evt.preventDefault(); retablir(); return;
    }
    if (selection === null || desactive || evt.target.tagName === 'INPUT') return;
    if (evt.key === 'Delete' || evt.key === 'Backspace') { evt.preventDefault(); supprimer(selection); }
    if (evt.key === 'Escape') setSelection(null);
  };

  const echelle = L > 30 ? 10 : L > 8 ? 5 : 1; // barre d'échelle en mètres
  const lignesGrille = useMemo(() => {
    if (mode !== 'grille' || pas < 0.5) return '';
    const d = [];
    for (let x = Math.ceil(e.xmin / pas) * pas; x <= e.xmax; x += pas) d.push(`M${x} ${sy(e.ymin)}L${x} ${sy(e.ymax)}`);
    for (let y = Math.ceil(e.ymin / pas) * pas; y <= e.ymax; y += pas) d.push(`M${e.xmin} ${sy(y)}L${e.xmax} ${sy(y)}`);
    return d.join('');
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [mode, pas, e.xmin, e.xmax, e.ymin, e.ymax]);
  const nbSaisis = poteaux.filter((p) => p.origine === 'saisi').length;

  return (
    <div className="editeur-poteaux" onKeyDown={surClavier}>
      <div className="editeur-barre">
        <span className="editeur-compte"><strong>{poteaux.length}</strong> {libelleCompte}</span>
        <div className="editeur-historique" role="group" aria-label="Historique des modifications">
          <button type="button" className="btn btn-secondary btn-icone" aria-label="Annuler (Ctrl+Z)" title="Annuler (Ctrl+Z)"
            disabled={desactive || !historique.passe.length} onClick={annuler}><Undo2 size={16} /></button>
          <button type="button" className="btn btn-secondary btn-icone" aria-label="Rétablir (Ctrl+Y)" title="Rétablir (Ctrl+Y)"
            disabled={desactive || !historique.futur.length} onClick={retablir}><Redo2 size={16} /></button>
        </div>
        <label className="editeur-option">
          Accrochage
          <select className="form-select editeur-select" value={mode} onChange={(evt) => setMode(evt.target.value)}>
            <option value="aucun">aucun</option>
            <option value="grille">grille</option>
            <option value="poteaux">alignement sur les poteaux</option>
          </select>
        </label>
        {mode === 'grille' && (
          <label className="editeur-option">
            Pas
            <select className="form-select editeur-select" value={pas} onChange={(evt) => setPas(Number(evt.target.value))}>
              {PAS_GRILLE_M.map((v) => <option key={v} value={v}>{v < 1 ? `${v * 100} cm` : `${v} m`}</option>)}
            </select>
          </label>
        )}
        <div className="editeur-zoom" role="group" aria-label="Zoom du plan">
          <button type="button" className="btn btn-secondary btn-icone" aria-label="Zoom arrière"
            disabled={zoom === ZOOMS[0]} onClick={() => setZoom(ZOOMS[ZOOMS.indexOf(zoom) - 1])}><Minus size={16} /></button>
          <span aria-live="polite">× {zoom}</span>
          <button type="button" className="btn btn-secondary btn-icone" aria-label="Zoom avant"
            disabled={zoom === ZOOMS[ZOOMS.length - 1]} onClick={() => setZoom(ZOOMS[ZOOMS.indexOf(zoom) + 1])}><Plus size={16} /></button>
        </div>
      </div>

      {/* Coordonnées du pointeur en surimpression : un texte dans la barre
          changeait de largeur au survol et décalait le plan sous la souris. */}
      <div className="editeur-zone">
      <span className="editeur-curseur" aria-hidden="true">
        {curseur ? `X ${nf(curseur.x)} m · Y ${nf(curseur.y)} m` : 'Clic : ajouter · glisser un poteau : déplacer'}
      </span>
      <div className="editeur-cadre">
        <svg
          ref={svgRef}
          className={desactive ? 'editeur-svg desactive' : 'editeur-svg'}
          style={{ width: `${zoom * 100}%` }}
          viewBox={`${e.xmin - marge} ${-marge} ${L + 2 * marge} ${H + 4 * marge}`}
          data-ymax={e.ymax}
          role="img"
          aria-label={`Plan de ${nf(L)} × ${nf(H)} m avec ${poteaux.length} poteau(x). La liste sous le plan permet de les modifier au clavier.`}
          onClick={(evt) => {
            if (clicApresGlisse.current) { clicApresGlisse.current = false; return; }
            if (!desactive && !glisse) { const { x, y } = pointeur(evt); ajouter(x, y); }
          }}
          onPointerMove={surDeplacement}
          onPointerUp={finGlisse}
          onPointerLeave={() => setCurseur(null)}
        >
          {lignesGrille && <path d={lignesGrille} className="editeur-grille" vectorEffect="non-scaling-stroke" />}
          {traitsFond && <path d={traitsFond} className="editeur-fond" vectorEffect="non-scaling-stroke" />}
          {traitsPoutres && <path d={traitsPoutres} className="editeur-poutres" vectorEffect="non-scaling-stroke" />}
          <g className="editeur-echelle" transform={`translate(${e.xmin} ${H + marge * 1.8})`}>
            <line x1="0" y1="0" x2={echelle} y2="0" vectorEffect="non-scaling-stroke" />
            <text x={echelle + marge * 0.3} y={marge * 0.25} fontSize={marge * 0.7}>{echelle} m</text>
          </g>
          {poteaux.map((p, i) => {
            const pos = glisse?.i === i && glisse.bouge ? glisse.position : p;
            const classes = ['editeur-poteau', p.origine && p.origine !== 'saisi' ? 'lu' : 'saisi',
              i === selection ? 'selection' : ''].join(' ');
            return (
              <g key={i} className={classes} onPointerDown={(evt) => debutGlisse(evt, i)}
                onClick={(evt) => evt.stopPropagation()}>
                <rect x={pos.x - cote / 2} y={sy(pos.y) - cote / 2} width={cote} height={cote} />
                <text x={pos.x + cote * 0.7} y={sy(pos.y) - cote * 0.7} fontSize={cote * 0.9}>{i + 1}</text>
              </g>
            );
          })}
        </svg>
      </div>
      </div>

      <p className="editeur-legende">
        <span className="pastille saisi" aria-hidden="true" /> saisi ({nbSaisis})
        {poteaux.length > nbSaisis && (
          <><span className="pastille lu" aria-hidden="true" /> lu dans le plan ou la trame ({poteaux.length - nbSaisis})</>
        )}
      </p>

      {message && <p className="editeur-message" role="alert">{message}</p>}

      <div className="editeur-panneaux">
        <form className="editeur-saisie" onSubmit={ajouterSaisie}>
          <span className="form-label">Ajouter un poteau par ses coordonnées</span>
          <div className="editeur-champs">
            <label>X (m)<input type="number" step="0.01" className="form-control" value={saisie.x}
              onChange={(evt) => setSaisie((s) => ({ ...s, x: evt.target.value }))} disabled={desactive} /></label>
            <label>Y (m)<input type="number" step="0.01" className="form-control" value={saisie.y}
              onChange={(evt) => setSaisie((s) => ({ ...s, y: evt.target.value }))} disabled={desactive} /></label>
            <button type="submit" className="btn btn-secondary" disabled={desactive}>Ajouter</button>
          </div>
        </form>

        {selection !== null && poteaux[selection] && (
          <div className="editeur-selection">
            <span className="form-label">
              Poteau n° {selection + 1} · {poteaux[selection].origine === 'saisi' || !poteaux[selection].origine ? 'saisi' : `lu (${poteaux[selection].origine})`}
            </span>
            <div className="editeur-champs">
              <label>X (m)<input type="number" step="0.01" className="form-control" defaultValue={poteaux[selection].x}
                key={`x-${selection}-${poteaux[selection].x}`}
                onBlur={(evt) => modifierChamp(selection, 'x', evt.target.value)} disabled={desactive} /></label>
              <label>Y (m)<input type="number" step="0.01" className="form-control" defaultValue={poteaux[selection].y}
                key={`y-${selection}-${poteaux[selection].y}`}
                onBlur={(evt) => modifierChamp(selection, 'y', evt.target.value)} disabled={desactive} /></label>
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
                  n° {i + 1} : X {nf(p.x)} m · Y {nf(p.y)} m{p.origine && p.origine !== 'saisi' ? ` (${p.origine})` : ''}
                </button>
              </li>
            ))}
          </ol>
          {confirmerEffacement ? (
            <div className="editeur-champs">
              <button type="button" className="btn btn-secondary" onClick={() => { appliquer([]); setSelection(null); setConfirmerEffacement(false); }}>
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
