import React, { useMemo, useRef, useState } from 'react';
import { Check, FileSpreadsheet, Loader2, Upload, X } from 'lucide-react';
import { dqeService, formatFCFA } from '../../api/dqeService';
import Alerte from '../ui/Alerte';

// Import d'un DQE Excel existant dans la bibliothèque, en deux temps :
//  1. le serveur lit le fichier et renvoie un aperçu (rien n'est écrit) ;
//  2. l'utilisateur coche, choisit les lots et prix laissés ouverts, puis
//     confirme. Le serveur écrit tout ou rien.
// Aucun lot ni prix n'est deviné ici : ce que le fichier ne dit pas
// clairement reste à choisir par l'utilisateur.

const norm = (t) => String(t || '').trim().toLowerCase();
const cle = (lot, designation, unite) => `${lot}|${norm(designation)}|${norm(unite)}`;

const BADGES = {
  nouveau: { texte: 'Nouveau', classe: 'ok' },
  identique: { texte: 'Déjà en bibliothèque', classe: 'neutre' },
  prix_different: { texte: 'Prix différent', classe: 'attention' },
  lot_a_choisir: { texte: 'Lot à choisir', classe: 'attention' },
  prix_a_arbitrer: { texte: 'Plusieurs prix', classe: 'attention' },
  sans_prix: { texte: 'Sans prix', classe: 'neutre' },
};

// État d'une ligne d'après les choix de l'utilisateur et la bibliothèque actuelle.
function evaluer(l, bibliotheque) {
  if (!l.lot) return { importable: false, raison: 'Choisissez le lot.' };
  if (l.prix_possibles.length > 1 && l.prix === null) return { importable: false, raison: 'Choisissez le prix.' };
  const existant = bibliotheque.get(cle(l.lot, l.designation, l.unite));
  if (existant === undefined) return { importable: true, action: 'creer' };
  if (existant === l.prix) return { importable: false, raison: 'Déjà en bibliothèque au même prix.', identique: true };
  return { importable: true, action: 'mettre_a_jour', ancienPrix: existant };
}

// Parts matériaux / main-d'œuvre lues dans le fichier pour le prix retenu
// (issue #92) ; null si ce prix n'a pas de décomposition cohérente.
const partsDuPrix = (l) => (l.decompositions || []).find((d) => d.prix === l.prix) || null;

export default function ImportDQEExcel({ lots, ouvrages, onTermine, onFermer }) {
  const entree = useRef(null);
  const [etat, setEtat] = useState({ enCours: false, erreur: null, erreursLignes: null });
  const [apercu, setApercu] = useState(null);           // {fichier, feuilles, avertissements}
  const [lignes, setLignes] = useState([]);
  const [origine, setOrigine] = useState({ sourcePrix: '', datePrix: '' });
  const [bilan, setBilan] = useState(null);

  const bibliotheque = useMemo(() => new Map((ouvrages || []).map((o) => [cle(o.lot, o.designation, o.unite), o.prix_unitaire])), [ouvrages]);
  const libelleLot = useMemo(() => Object.fromEntries(lots.map((l) => [l.cle, l.libelle])), [lots]);

  const analyser = async (fichier) => {
    if (!fichier) return;
    setEtat({ enCours: true, erreur: null, erreursLignes: null });
    setBilan(null);
    try {
      const r = await dqeService.analyserDQEExcel(fichier);
      setApercu({ fichier: r.fichier, feuilles: r.feuilles, avertissements: r.avertissements });
      setLignes(r.lignes.map((l, i) => ({
        ...l, id: i, prix: l.prix_unitaire,
        // Coché d'office seulement quand tout est établi et que l'ouvrage est nouveau.
        coche: l.statut === 'nouveau',
      })));
      setOrigine({ sourcePrix: `DQE importé : ${r.fichier}`, datePrix: '' });
      setEtat({ enCours: false, erreur: null, erreursLignes: null });
    } catch (err) {
      setApercu(null);
      setEtat({ enCours: false, erreur: err.message, erreursLignes: null });
    } finally {
      if (entree.current) entree.current.value = '';
    }
  };

  const maj = (id, champs) => setLignes((ls) => ls.map((l) => (l.id === id ? { ...l, ...champs } : l)));
  const lotPourSection = (section, lot) => setLignes((ls) => ls.map((l) => (
    l.statut === 'lot_a_choisir' && l.section === section && !l.lotChoisiSeul ? { ...l, lot: lot || null } : l)));

  const evaluees = useMemo(() => lignes.map((l) => ({ ...l, ev: evaluer(l, bibliotheque) })), [lignes, bibliotheque]);
  const retenues = evaluees.filter((l) => l.coche && l.ev.importable);
  const nbMaj = retenues.filter((l) => l.ev.action === 'mettre_a_jour').length;

  const confirmer = async () => {
    setEtat({ enCours: true, erreur: null, erreursLignes: null });
    try {
      const r = await dqeService.confirmerImportDQE({
        lignes: retenues.map((l) => {
          const parts = partsDuPrix(l);
          return {
            lot: l.lot, designation: l.designation, unite: l.unite, prix_unitaire: l.prix, action: l.ev.action,
            prix_materiaux: parts?.materiaux ?? null, prix_main_oeuvre: parts?.main_oeuvre ?? null,
          };
        }),
        ...origine,
      });
      setBilan(r);
      setApercu(null);
      setLignes([]);
      setEtat({ enCours: false, erreur: null, erreursLignes: null });
      onTermine?.();
    } catch (err) {
      const parLigne = err.data?.lignes
        ? Object.entries(err.data.lignes).map(([n, msg]) => ({ n, msg, des: retenues[Number(n) - 1]?.designation }))
        : null;
      setEtat({ enCours: false, erreur: err.message, erreursLignes: parLigne });
    }
  };

  const sections = useMemo(() => {
    const vues = new Map();
    lignes.filter((l) => l.statut === 'lot_a_choisir').forEach((l) => {
      const s = l.section || 'Sans titre de section';
      vues.set(s, (vues.get(s) || 0) + 1);
    });
    return [...vues.entries()].filter(([, n]) => n > 1);
  }, [lignes]);

  return (
    <section className="import-dqe" aria-labelledby="titre-import-dqe">
      <header className="import-dqe-entete">
        <div>
          <h3 id="titre-import-dqe"><FileSpreadsheet size={18} aria-hidden="true" /> Importer un DQE Excel</h3>
          <p className="texte-discret">
            Le logiciel lit les désignations, unités et prix unitaires d'un DQE (.xlsx) déjà chiffré, et
            les colonnes « matériaux » et « main-d'œuvre » si le fichier en a. Les quantités
            et montants du fichier ne sont pas repris. Rien n'est enregistré avant votre confirmation.
          </p>
        </div>
        <button type="button" className="btn btn-secondary btn-compact" onClick={onFermer} aria-label="Fermer l'import">
          <X size={14} aria-hidden="true" />
        </button>
      </header>

      <label className="depot-excel">
        <input ref={entree} type="file" accept=".xlsx" className="sr-only" disabled={etat.enCours}
          onChange={(e) => analyser(e.target.files?.[0])} />
        {etat.enCours && !apercu ? <Loader2 size={18} className="spin" aria-hidden="true" /> : <Upload size={18} aria-hidden="true" />}
        <span>{apercu ? `Fichier lu : ${apercu.fichier} — choisir un autre fichier` : 'Choisir un fichier .xlsx (5 Mo au plus)'}</span>
      </label>

      {etat.erreur && (
        <Alerte type="erreur" liste={etat.erreursLignes?.map((e) => e.msg)}>{etat.erreur}</Alerte>
      )}
      {bilan && (
        <p className="bilan-import" role="status">
          <Check size={16} aria-hidden="true" /> Import terminé : {bilan.crees} ouvrage(s) ajouté(s)
          {bilan.mis_a_jour ? `, ${bilan.mis_a_jour} prix mis à jour` : ''}.
        </p>
      )}

      {apercu && (
        <>
          <p className="texte-discret">
            {apercu.feuilles.map((f) => `« ${f.nom} » : ${f.lignes} ligne(s) lue(s)`).join(' · ')} — {lignes.length} ouvrage(s) distinct(s).
          </p>
          {apercu.avertissements.map((a) => <Alerte key={a} type="attention">{a}</Alerte>)}

          {sections.length > 0 && (
            <div className="sections-a-classer">
              <p><strong>Sections sans lot reconnu</strong> — choisissez le lot pour toute la section :</p>
              {sections.map(([s, n]) => (
                <label key={s} className="section-a-classer">
                  <span>{s} <span className="texte-discret">({n} ouvrages)</span></span>
                  <select className="form-select" defaultValue="" onChange={(e) => lotPourSection(s === 'Sans titre de section' ? null : s, e.target.value)}>
                    <option value="">— Lot —</option>
                    {lots.map((l) => <option key={l.cle} value={l.cle}>{l.libelle}</option>)}
                  </select>
                </label>
              ))}
            </div>
          )}

          <div className="table-scroll">
            <table className="custom-table table-import">
              <thead>
                <tr>
                  <th><span className="sr-only">Importer</span></th>
                  <th>Désignation</th><th>Unité</th><th>Lot</th><th>Prix unitaire HT</th><th>Statut</th>
                </tr>
              </thead>
              <tbody>
                {evaluees.map((l) => {
                  // Badge de l'état ACTUEL (après les choix de l'utilisateur).
                  const badge = l.ev.identique ? BADGES.identique
                    : l.ev.action === 'mettre_a_jour' ? BADGES.prix_different
                      : !l.ev.importable ? BADGES[l.statut]
                        : l.prix == null ? BADGES.sans_prix : BADGES.nouveau;
                  return (
                    <tr key={l.id} className={l.coche && l.ev.importable ? 'ligne-retenue' : ''}>
                      <td>
                        <input type="checkbox" aria-label={`Importer ${l.designation}`} checked={l.coche && l.ev.importable}
                          disabled={!l.ev.importable} onChange={(e) => maj(l.id, { coche: e.target.checked })} />
                      </td>
                      <td>
                        <strong>{l.designation}</strong>
                        <span className="origine-import">{l.origine}{l.occurrences > 1 ? ` · ${l.occurrences} fois dans le fichier` : ''}</span>
                      </td>
                      <td>{l.unite}</td>
                      <td>
                        {l.statut === 'lot_a_choisir' ? (
                          <select aria-label={`Lot de ${l.designation}`} className="form-select select-compact" value={l.lot || ''}
                            onChange={(e) => maj(l.id, { lot: e.target.value || null, lotChoisiSeul: true, coche: !!e.target.value })}>
                            <option value="">— Choisir —</option>
                            {lots.map((x) => <option key={x.cle} value={x.cle}>{x.libelle}</option>)}
                          </select>
                        ) : libelleLot[l.lot] || l.lot}
                      </td>
                      <td className="tabular">
                        {l.prix_possibles.length > 1 ? (
                          <select aria-label={`Prix de ${l.designation}`} className="form-select select-compact" value={l.prix ?? ''}
                            onChange={(e) => maj(l.id, { prix: e.target.value === '' ? null : Number(e.target.value), coche: e.target.value !== '' })}>
                            <option value="">— {l.prix_possibles.length} prix —</option>
                            {l.prix_possibles.map((p) => <option key={p} value={p}>{formatFCFA(p)}</option>)}
                          </select>
                        ) : l.prix != null ? formatFCFA(l.prix) : <span className="texte-discret">aucun</span>}
                        {l.prix != null && (partsDuPrix(l)
                          ? <span className="parts-prix">mat. {formatFCFA(partsDuPrix(l).materiaux)} · MO {formatFCFA(partsDuPrix(l).main_oeuvre)}</span>
                          : <span className="parts-prix non-decompose">non décomposé</span>)}
                        {l.ev.action === 'mettre_a_jour' && (
                          <span className="origine-import">bibliothèque : {l.ev.ancienPrix != null ? formatFCFA(l.ev.ancienPrix) : 'sans prix'}</span>
                        )}
                      </td>
                      <td>
                        <span className={`badge-import ${badge.classe}`}>{badge.texte}</span>
                        {!l.ev.importable && !l.ev.identique && <span className="origine-import">{l.ev.raison}</span>}
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>

          <div className="pied-import">
            <div className="form-group">
              <label className="form-label" htmlFor="imp-src">Origine des prix</label>
              <input id="imp-src" className="form-control" maxLength={200} value={origine.sourcePrix}
                onChange={(e) => setOrigine({ ...origine, sourcePrix: e.target.value })} />
            </div>
            <div className="form-group">
              <label className="form-label" htmlFor="imp-date">Date des prix</label>
              <input id="imp-date" type="date" className="form-control" value={origine.datePrix}
                onChange={(e) => setOrigine({ ...origine, datePrix: e.target.value })} />
            </div>
            <button type="button" className="btn btn-primary" disabled={!retenues.length || etat.enCours} onClick={confirmer}>
              {etat.enCours ? <Loader2 size={16} className="spin" /> : <Check size={16} />}
              <span>Importer {retenues.length} ouvrage(s){nbMaj ? ` dont ${nbMaj} mise(s) à jour de prix` : ''}</span>
            </button>
          </div>
        </>
      )}
    </section>
  );
}
