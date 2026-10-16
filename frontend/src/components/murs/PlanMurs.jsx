import React, { useMemo, useState } from 'react';
import { BrickWall, Eraser, Loader2, RefreshCw, ScanLine } from 'lucide-react';
import Alerte from '../ui/Alerte';
import { nf } from '../charts/palette';

const NIVEAUX = {
  etages: { cle: 'mursEtages', champ: 'murs_etages', libelle: 'Murs des étages', aide: 'posés sur les poutres du plancher' },
  rdc: { cle: 'mursRdc', champ: 'murs_rdc', libelle: 'Murs du rez-de-chaussée', aide: 'posés sur les longrines' },
};

// Tronçons de la trame (poutres) avec leurs extrémités : géométrie lue
// telle que le serveur l'a calculée (clé du tronçon comprise).
function lireTroncons(elements) {
  const poteaux = new Map(elements.filter((e) => e.type_element === 'poteau').map((p) => [p.id, p]));
  return elements
    .filter((e) => e.type_element === 'poutre')
    .map((e) => {
      const a = poteaux.get(e.poteau_origine);
      const b = poteaux.get(e.poteau_destination);
      const r = e.resultat_calcul || {};
      if (!a || !b || a.position_x == null || b.position_x == null) return null;
      return {
        id: e.id, nom: e.identifiant, cle: r.cle_segment || null, rive: !!r.rive, portee: e.portee,
        x1: a.position_x, y1: a.position_y, x2: b.position_x, y2: b.position_y,
      };
    })
    .filter(Boolean);
}

// Plan des murs : l'utilisateur désigne les tronçons qui portent RÉELLEMENT
// un mur (plan architectural). Rien n'est supposé : un tronçon non désigné
// ne porte pas de mur. Le calcul est refait par le serveur.
export default function PlanMurs({ projet, poidsRenseigne, onEnregistrer }) {
  const elements = projet?.elements || [];
  const troncons = useMemo(() => lireTroncons(elements), [elements]);
  const poteaux = elements.filter((e) => e.type_element === 'poteau' && e.position_x != null);
  const nbNiveaux = projet?.nb_niveaux || 1;
  const niveauxDispo = nbNiveaux >= 2 ? ['etages', 'rdc'] : ['rdc'];

  const [niveau, setNiveau] = useState(niveauxDispo[0]);
  const initial = useMemo(() => ({
    etages: new Set(projet?.murs_etages || []), rdc: new Set(projet?.murs_rdc || []),
  }), [projet?.murs_etages, projet?.murs_rdc]);
  const [selection, setSelection] = useState(initial);
  const [etat, setEtat] = useState({ enCours: false, erreur: null });
  const [projetVu, setProjetVu] = useState(projet?.id);
  if (projetVu !== projet?.id) { setProjetVu(projet?.id); setSelection(initial); }

  const niveauActif = niveauxDispo.includes(niveau) ? niveau : niveauxDispo[0];
  const courante = selection[niveauActif];
  const cles = new Set(troncons.map((t) => t.cle).filter(Boolean));
  const sansCle = troncons.some((t) => !t.cle);
  const orphelins = [...courante].filter((c) => !cles.has(c));
  const modifie = ['etages', 'rdc'].some((n) => selection[n].size !== initial[n].size
    || [...selection[n]].some((c) => !initial[n].has(c)));
  const longueur = troncons.filter((t) => courante.has(t.cle)).reduce((s, t) => s + (t.portee || 0), 0);

  const changer = (maj) => setSelection((s) => ({ ...s, [niveauActif]: maj(new Set(s[niveauActif])) }));
  const basculer = (cle) => changer((s) => { if (s.has(cle)) s.delete(cle); else s.add(cle); return s; });
  const proposerFacades = () => changer((s) => { troncons.filter((t) => t.rive && t.cle).forEach((t) => s.add(t.cle)); return s; });

  const enregistrer = async () => {
    setEtat({ enCours: true, erreur: null });
    try {
      await onEnregistrer({ mursEtages: [...selection.etages], mursRdc: [...selection.rdc] });
      setEtat({ enCours: false, erreur: null });
    } catch (err) {
      setEtat({ enCours: false, erreur: err.message });
    }
  };

  if (!troncons.length) {
    return (
      <section className="plan-murs" aria-labelledby="titre-plan-murs">
        <h3 id="titre-plan-murs"><BrickWall size={18} aria-hidden="true" /> Plan des murs</h3>
        <p className="texte-discret">Aucune poutre : générez d'abord la trame (étape 1) pour placer les murs.</p>
      </section>
    );
  }

  // Repère du plan : y vers le haut, marge de 8 % autour de la trame.
  const xs = troncons.flatMap((t) => [t.x1, t.x2]);
  const ys = troncons.flatMap((t) => [t.y1, t.y2]);
  const [minX, maxX, minY, maxY] = [Math.min(...xs), Math.max(...xs), Math.min(...ys), Math.max(...ys)];
  const marge = Math.max(maxX - minX, maxY - minY, 1) * 0.08;
  const vb = [minX - marge, -(maxY + marge), maxX - minX + 2 * marge, maxY - minY + 2 * marge];
  const cote = Math.max(vb[2], vb[3]) * 0.012;

  return (
    <section className="plan-murs" aria-labelledby="titre-plan-murs">
      <div className="plan-murs-entete">
        <div>
          <h3 id="titre-plan-murs"><BrickWall size={18} aria-hidden="true" /> Plan des murs</h3>
          <p className="texte-discret">
            Désignez les poutres qui portent réellement un mur, d'après le plan architectural (façades, murs de séparation).
            Un tronçon non désigné ne porte aucun mur.
          </p>
        </div>
        <p className="plan-murs-total tabular" aria-live="polite">
          <strong>{nf(longueur, 2)} m</strong> <span className="texte-discret">de murs · {courante.size} tronçon(s)</span>
        </p>
      </div>

      {!poidsRenseigne && (
        <Alerte type="attention">
          Poids des murs non renseigné (étape 1, hypothèses de charges) : les murs placés ne seront pas comptés tant qu'il manque.
        </Alerte>
      )}
      {sansCle && (
        <Alerte type="attention">
          Certaines poutres datent d'un calcul antérieur au plan des murs : relancez le calcul pour pouvoir les désigner.
        </Alerte>
      )}

      <div className="onglets" role="tablist" aria-label="Niveau des murs">
        {niveauxDispo.map((n) => (
          <button key={n} type="button" role="tab" aria-selected={niveauActif === n}
            className={niveauActif === n ? 'onglet actif' : 'onglet'} onClick={() => setNiveau(n)}>
            {NIVEAUX[n].libelle} <span className="texte-discret">({selection[n].size})</span>
          </button>
        ))}
      </div>
      <p className="texte-discret">{NIVEAUX[niveauActif].libelle} : {NIVEAUX[niveauActif].aide}.
        {niveauActif === 'etages' && " Vérifiez qu'aucun mur d'étage ne tombe à faux sur une dalle sans poutre dessous."}</p>

      <div className="plan-murs-outils">
        <button type="button" className="btn btn-secondary btn-compact" onClick={proposerFacades}>
          <ScanLine size={14} aria-hidden="true" /> <span>Ajouter les façades</span>
        </button>
        <button type="button" className="btn btn-secondary btn-compact" disabled={!courante.size}
          onClick={() => changer(() => new Set())}>
          <Eraser size={14} aria-hidden="true" /> <span>Tout effacer</span>
        </button>
      </div>

      <svg className="plan-murs-svg" viewBox={vb.join(' ')} role="group" aria-label={`Plan de la trame : ${NIVEAUX[niveauActif].libelle.toLowerCase()}`}>
        {troncons.map((t) => {
          const actif = t.cle && courante.has(t.cle);
          return (
            <g key={t.id} className={`troncon${actif ? ' avec-mur' : ''}${t.cle ? '' : ' inactif'}`}
              role="button" tabIndex={t.cle ? 0 : -1} aria-pressed={!!actif}
              aria-label={`Poutre ${t.nom}, ${nf(t.portee, 2)} m${t.rive ? ', façade' : ''} : ${actif ? 'mur placé' : 'sans mur'}`}
              onClick={() => t.cle && basculer(t.cle)}
              onKeyDown={(e) => { if (t.cle && (e.key === 'Enter' || e.key === ' ')) { e.preventDefault(); basculer(t.cle); } }}>
              <title>{`${t.nom} — ${nf(t.portee, 2)} m${t.rive ? ' (façade)' : ''}`}</title>
              <line className="troncon-zone" x1={t.x1} y1={-t.y1} x2={t.x2} y2={-t.y2} />
              <line className="troncon-trait" x1={t.x1} y1={-t.y1} x2={t.x2} y2={-t.y2} />
            </g>
          );
        })}
        {poteaux.map((p) => (
          <rect key={p.id} className="poteau-plan" x={p.position_x - cote} y={-p.position_y - cote} width={cote * 2} height={cote * 2} />
        ))}
      </svg>

      <ul className="plan-murs-legende" aria-hidden="true">
        <li><span className="pastille-mur" /> mur placé</li>
        <li><span className="pastille-poutre" /> poutre sans mur</li>
        <li><span className="pastille-poteau" /> poteau</li>
      </ul>

      {orphelins.length > 0 && (
        <Alerte type="attention" action={{ libelle: 'Retirer', onClick: () => changer((s) => { orphelins.forEach((c) => s.delete(c)); return s; }) }}>
          {orphelins.length} tronçon(s) de mur ne correspondent plus à aucune poutre (trame modifiée) : ils ne sont pas comptés.
        </Alerte>
      )}
      {etat.erreur && <Alerte type="erreur" titre="Plan des murs non enregistré">{etat.erreur}</Alerte>}

      <div className="plan-murs-actions">
        <button type="button" className="btn btn-primary" disabled={!modifie || etat.enCours} onClick={enregistrer}>
          {etat.enCours ? <Loader2 size={16} className="spin" /> : <RefreshCw size={16} />}
          <span>Enregistrer et recalculer</span>
        </button>
        {modifie && !etat.enCours && <span className="texte-discret">Modifications non enregistrées</span>}
      </div>
    </section>
  );
}
