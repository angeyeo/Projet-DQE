import React, { useState } from 'react';
import { GitCompare, Loader2, Plus, Trash2 } from 'lucide-react';
import { dqeService } from '../../api/dqeService';
import Alerte from '../ui/Alerte';
import { nf } from '../charts/palette';

const CHAMPS = [
  ['contrainte_sol_kn_m2', 'Contrainte du sol (kN/m²)', 'nombre'],
  ['charge_permanente_kn_m2', 'G planchers (kN/m²)', 'nombre'],
  ['charge_exploitation', 'Q (kN/m²)', 'nombre'],
  ['portee_x', 'Portée X (m)', 'nombre'],
  ['portee_y', 'Portée Y (m)', 'nombre'],
  ['nb_niveaux', 'Nombre de niveaux', 'nombre'],
  ['methode_semelles', 'Méthode des semelles', ['ELU', 'ELS']],
  ['inclure_poids_propre_ossature', 'Poids propre ossature', ['oui', 'non']],
];
const VIDE = () => ({ nom: '', champ: CHAMPS[0][0], valeur: '' });

const versValeur = (champ, v) => {
  if (champ === 'inclure_poids_propre_ossature') return v === 'oui';
  if (champ === 'methode_semelles') return v;
  return v === '' ? null : Number(v);
};

// Variantes « et si ? » : chaque ligne est recalculée par le moteur côté
// serveur (transaction annulée, rien n'est enregistré).
export default function VariantesPanel({ projetId }) {
  const [lignes, setLignes] = useState([VIDE()]);
  const [etat, setEtat] = useState({ chargement: false, erreur: null, data: null });

  const maj = (i, champs) => setLignes((l) => l.map((x, k) => (k === i ? { ...x, ...champs } : x)));
  const pret = lignes.every((l) => l.valeur !== '');

  const comparer = async () => {
    setEtat({ chargement: true, erreur: null, data: null });
    try {
      const data = await dqeService.calculerVariantes(projetId, lignes.map((l, i) => ({
        nom: l.nom.trim() || `Variante ${i + 1}`,
        modifications: { [l.champ]: versValeur(l.champ, l.valeur) },
      })));
      setEtat({ chargement: false, erreur: null, data });
    } catch (err) {
      setEtat({ chargement: false, erreur: err.message, data: null });
    }
  };

  return (
    <section className="glass-panel carte" aria-labelledby="titre-variantes">
      <div className="bloc-titre"><GitCompare size={20} aria-hidden="true" /><h3 id="titre-variantes">Comparer des variantes</h3></div>
      <p className="texte-discret">Chaque variante est recalculée par le moteur (trame, semelles, DQE) sans rien modifier dans le projet.</p>
      {lignes.map((l, i) => {
        const def = CHAMPS.find((c) => c[0] === l.champ);
        return (
          <div className="ligne-variante" key={i}>
            <input className="form-control" aria-label={`Nom de la variante ${i + 1}`} placeholder={`Variante ${i + 1}`}
              value={l.nom} onChange={(e) => maj(i, { nom: e.target.value })} />
            <select className="form-select" aria-label="Paramètre modifié" value={l.champ}
              onChange={(e) => maj(i, { champ: e.target.value, valeur: '' })}>
              {CHAMPS.map(([c, lib]) => <option key={c} value={c}>{lib}</option>)}
            </select>
            {Array.isArray(def[2]) ? (
              <select className="form-select" aria-label="Nouvelle valeur" value={l.valeur} onChange={(e) => maj(i, { valeur: e.target.value })}>
                <option value="">—</option>
                {def[2].map((o) => <option key={o} value={o}>{o}</option>)}
              </select>
            ) : (
              <input type="number" min="0" step="0.1" className="form-control" aria-label="Nouvelle valeur"
                value={l.valeur} onChange={(e) => maj(i, { valeur: e.target.value })} />
            )}
            <button type="button" className="btn btn-secondary btn-compact" aria-label="Retirer cette variante"
              disabled={lignes.length === 1} onClick={() => setLignes((x) => x.filter((_, k) => k !== i))}>
              <Trash2 size={14} aria-hidden="true" />
            </button>
          </div>
        );
      })}
      <div className="actions-ligne">
        <button type="button" className="btn btn-secondary btn-compact" disabled={lignes.length >= 5}
          onClick={() => setLignes((l) => [...l, VIDE()])}><Plus size={14} /> <span>Variante</span></button>
        <button type="button" className="btn btn-primary btn-compact" disabled={!pret || etat.chargement} onClick={comparer}>
          {etat.chargement ? <Loader2 size={14} className="spin" /> : <GitCompare size={14} />} <span>Comparer</span>
        </button>
      </div>

      {etat.erreur && <Alerte type="erreur">{etat.erreur}</Alerte>}
      {etat.data && (
        <>
          <div className="table-scroll">
            <table className="custom-table">
              <thead>
                <tr><th>Variante</th><th>Total ouvrages</th><th>Écart</th><th>Béton</th><th>Acier</th><th>Semelle max</th><th>Poteau max</th></tr>
              </thead>
              <tbody>
                {etat.data.variantes.map((v) => (
                  <tr key={v.nom}>
                    <td><strong>{v.nom}</strong></td>
                    {v.erreur ? (
                      <td colSpan={6} className="texte-erreur">{v.erreur}</td>
                    ) : !v.dqe ? (
                      <td colSpan={6} className="texte-discret">DQE non calculable : {v.problemes.map((p) => p.message).join(' · ')}</td>
                    ) : (
                      <>
                        <td className="tabular">{nf(v.dqe.total_general)} FCFA</td>
                        <td className="tabular">{v.ecart_pct == null ? '—' : `${v.ecart_pct > 0 ? '+' : ''}${nf(v.ecart_pct, 2)} %`}</td>
                        <td className="tabular">{nf(v.dqe.synthese.beton_m3, 2)} m³</td>
                        <td className="tabular">{nf(v.dqe.synthese.acier_kg, 0)} kg</td>
                        <td className="tabular">{v.semelle_cote_max_cm ?? '—'} cm</td>
                        <td className="tabular">{v.poteau_cote_max_cm ?? '—'} cm</td>
                      </>
                    )}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          <p className="texte-discret">{etat.data.note}</p>
        </>
      )}
    </section>
  );
}
