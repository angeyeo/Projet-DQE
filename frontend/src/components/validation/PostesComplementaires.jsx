import React, { useState } from 'react';
import { HardHat, Loader2, Plus, Sparkles, Trash2 } from 'lucide-react';
import { dqeService, formatFCFA } from '../../api/dqeService';
import useReferentiel from '../../hooks/useReferentiel';
import Alerte from '../ui/Alerte';

const UNITES = ['forfait', 'ens.', 'u', 'm²', 'm³', 'ml', 'kg', 'jour'];
const VIDE = { lot: '', mode: 'simple', designation: '', unite: '', quantite: '', prixUnitaire: '', typePoste: '', geometrie: {} };

// Postes hors structure (installation de chantier, maçonnerie, enduits…).
// Mode simple : quantité et prix SAISIS. Mode ratio : géométrie saisie,
// quantités calculées par le moteur au DQE avec le barème du cabinet.
export default function PostesComplementaires({ postes, onAjouter, onSupprimer, erreur }) {
  const { data: ref, erreur: erreurRef } = useReferentiel();
  const [p, setP] = useState(VIDE);
  const [enCours, setEnCours] = useState(false);
  const [ia, setIa] = useState({ description: '', chargement: false, erreur: null, info: null });

  const libelleLot = (cle) => ref?.lots.find((l) => l.cle === cle)?.libelle || cle;
  const typeRatio = ref?.types_postes_ratio.find((t) => t.cle === p.typePoste);

  const manquants = [];
  if (!p.lot) manquants.push('lot');
  if (p.mode === 'simple') {
    if (!p.designation.trim()) manquants.push('désignation');
    if (!p.unite) manquants.push('unité');
    if (!(Number(p.quantite) > 0)) manquants.push('quantité > 0');
    if (p.prixUnitaire === '' || Number(p.prixUnitaire) < 0) manquants.push('prix unitaire');
  } else {
    if (!p.typePoste) manquants.push('type de poste');
    typeRatio?.geometrie.filter((g) => g.requis).forEach((g) => {
      if (!(Number(p.geometrie[g.cle]) > 0)) manquants.push(g.libelle.toLowerCase());
    });
  }

  const ajouter = async (e) => {
    e.preventDefault();
    if (manquants.length) return;
    setEnCours(true);
    const geometrie = Object.fromEntries(
      Object.entries(p.geometrie).filter(([, v]) => v !== '' && v !== undefined).map(([k, v]) => [k, Number(v)]),
    );
    const ok = await onAjouter({ ...p, geometrie });
    setEnCours(false);
    if (ok) setP({ ...VIDE, lot: p.lot, mode: p.mode });
  };

  const suggerer = async () => {
    setIa((s) => ({ ...s, chargement: true, erreur: null, info: null }));
    try {
      const res = await dqeService.suggererPosteIA(ia.description.trim());
      if (!res.suggestion) {
        setIa((s) => ({ ...s, chargement: false, info: res.message || 'Aucune suggestion : renseignez le poste manuellement.' }));
        return;
      }
      const s = res.suggestion;
      setP((x) => ({ ...x, mode: 'simple', designation: s.designation || '', unite: s.unite || '', lot: s.lot_suggere || x.lot }));
      setIa((x) => ({
        ...x, chargement: false,
        info: `RECOMMANDATION IA (confiance : ${s.confiance ?? 'non précisée'}${res.source === 'MOCK' ? ', SIMULATION non IA' : ''}) : désignation, unité et lot pré-remplis. Quantité et prix restent à saisir et à vérifier.`,
      }));
    } catch (err) {
      setIa((x) => ({ ...x, chargement: false, erreur: err.message }));
    }
  };

  return (
    <section aria-labelledby="titre-postes">
      <div className="bloc-titre">
        <HardHat size={20} aria-hidden="true" />
        <h3 id="titre-postes">Postes complémentaires</h3>
      </div>

      {erreur && <Alerte type="erreur">{erreur}</Alerte>}
      {erreurRef && <Alerte type="erreur">Référentiel indisponible : {erreurRef}</Alerte>}

      {postes.length > 0 && (
        <div className="table-scroll">
          <table className="custom-table">
            <thead><tr><th>Lot</th><th>Poste</th><th>Quantité / géométrie</th><th>PU</th><th>Montant</th><th><span className="sr-only">Actions</span></th></tr></thead>
            <tbody>
              {postes.map((x) => (
                <tr key={x.id}>
                  <td>{libelleLot(x.lot)}</td>
                  <td>
                    <strong>{x.mode === 'ratio' ? (ref?.types_postes_ratio.find((t) => t.cle === x.type_poste)?.libelle || x.type_poste) : x.designation}</strong>
                    <div className="texte-discret">{x.mode === 'ratio' ? 'ratio — quantités calculées au DQE' : 'saisi'}</div>
                  </td>
                  <td className="tabular">
                    {x.mode === 'ratio'
                      ? Object.entries(x.geometrie || {}).map(([k, v]) => `${k} = ${v}`).join(' · ')
                      : `${x.quantite} ${x.unite}`}
                  </td>
                  <td className="tabular">{x.mode === 'ratio' ? 'barème' : formatFCFA(x.prix_unitaire)}</td>
                  <td className="tabular">{x.montant != null ? formatFCFA(x.montant) : <span className="texte-discret">au DQE</span>}</td>
                  <td>
                    <button type="button" className="btn btn-secondary btn-compact" onClick={() => onSupprimer(x.id)} aria-label="Supprimer ce poste">
                      <Trash2 size={14} color="var(--status-critical)" aria-hidden="true" />
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      <div className="encart-ia">
        <label className="form-label" htmlFor="poste-ia">Décrire le poste (l'IA propose désignation, unité et lot)</label>
        <div className="actions-ligne">
          <input id="poste-ia" className="form-control" maxLength={500} placeholder="ex : installation et repli de chantier"
            value={ia.description} onChange={(e) => setIa({ ...ia, description: e.target.value })} />
          <button type="button" className="btn btn-ia" disabled={ia.chargement || !ia.description.trim()} onClick={suggerer}>
            {ia.chargement ? <Loader2 size={16} className="spin" /> : <Sparkles size={16} />}
            <span>{ia.chargement ? 'Analyse…' : 'Suggérer'}</span>
          </button>
        </div>
        {ia.erreur && <p className="texte-erreur">Suggestion IA indisponible : {ia.erreur}</p>}
        {ia.info && <p className="texte-discret">{ia.info}</p>}
      </div>

      <form className="formulaire-poste" onSubmit={ajouter}>
        <div className="grid-2">
          <div className="form-group">
            <label className="form-label" htmlFor="poste-lot">Lot</label>
            <select id="poste-lot" className="form-select" value={p.lot} onChange={(e) => setP({ ...p, lot: e.target.value })}>
              <option value="">— Choisir —</option>
              {ref?.lots.map((l) => <option key={l.cle} value={l.cle}>{l.libelle}</option>)}
            </select>
          </div>
          <div className="form-group">
            <label className="form-label" htmlFor="poste-mode">Mode</label>
            <select id="poste-mode" className="form-select" value={p.mode} onChange={(e) => setP({ ...p, mode: e.target.value })}>
              <option value="simple">Saisie directe (quantité × prix)</option>
              <option value="ratio">Calcul par ratio (géométrie)</option>
            </select>
          </div>
        </div>

        {p.mode === 'simple' ? (
          <div className="grid-4">
            <div className="form-group">
              <label className="form-label" htmlFor="poste-des">Désignation</label>
              <input id="poste-des" className="form-control" value={p.designation} onChange={(e) => setP({ ...p, designation: e.target.value })} />
            </div>
            <div className="form-group">
              <label className="form-label" htmlFor="poste-unite">Unité</label>
              <select id="poste-unite" className="form-select" value={p.unite} onChange={(e) => setP({ ...p, unite: e.target.value })}>
                <option value="">—</option>
                {[...new Set([...UNITES, p.unite].filter(Boolean))].map((u) => <option key={u} value={u}>{u}</option>)}
              </select>
            </div>
            <div className="form-group">
              <label className="form-label" htmlFor="poste-qte">Quantité</label>
              <input id="poste-qte" type="number" min="0" step="0.01" className="form-control" value={p.quantite} onChange={(e) => setP({ ...p, quantite: e.target.value })} />
            </div>
            <div className="form-group">
              <label className="form-label" htmlFor="poste-pu">Prix unitaire (FCFA)</label>
              <input id="poste-pu" type="number" min="0" step="1" className="form-control" value={p.prixUnitaire} onChange={(e) => setP({ ...p, prixUnitaire: e.target.value })} />
            </div>
          </div>
        ) : (
          <div className="grid-3">
            <div className="form-group">
              <label className="form-label" htmlFor="poste-type">Type de poste</label>
              <select id="poste-type" className="form-select" value={p.typePoste} onChange={(e) => setP({ ...p, typePoste: e.target.value, geometrie: {} })}>
                <option value="">— Choisir —</option>
                {ref?.types_postes_ratio.map((t) => <option key={t.cle} value={t.cle}>{t.libelle}</option>)}
              </select>
            </div>
            {typeRatio?.geometrie.map((g) => (
              <div className="form-group" key={g.cle}>
                <label className="form-label" htmlFor={`geo-${g.cle}`}>{g.libelle}{g.unite ? ` (${g.unite})` : ''}{g.requis ? ' *' : ''}</label>
                <input id={`geo-${g.cle}`} type="number" min="0" step="0.01" className="form-control"
                  value={p.geometrie[g.cle] ?? ''} onChange={(e) => setP({ ...p, geometrie: { ...p.geometrie, [g.cle]: e.target.value } })} />
              </div>
            ))}
          </div>
        )}

        {manquants.length > 0 && <p className="texte-discret">À renseigner : {manquants.join(', ')}.</p>}
        <button type="submit" className="btn btn-success" disabled={enCours || manquants.length > 0}>
          <Plus size={16} aria-hidden="true" /> <span>{enCours ? 'Ajout…' : 'Ajouter le poste'}</span>
        </button>
      </form>
    </section>
  );
}
