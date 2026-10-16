import React, { useState } from 'react';
import { FileSpreadsheet, Loader2, Truck } from 'lucide-react';
import { dqeService, formatFCFA } from '../../api/dqeService';
import useRessource from '../../hooks/useRessource';
import Alerte from '../ui/Alerte';
import { nf } from '../charts/palette';

const decimales = (unite) => (unite === 'u' ? 0 : 3);

// Fiche d'approvisionnement : matériaux à acheter, calculés par le serveur à
// partir du DQE. Le composant n'effectue aucun calcul : il affiche ce que le
// serveur renvoie, y compris ce qui manque (prix, capacité des camions).
export default function FicheApprovisionnement({ projetId, onParametres }) {
  const { data: fiche, erreur, chargement } = useRessource(() => dqeService.getApprovisionnement(projetId), [projetId]);
  const [exportEtat, setExportEtat] = useState({ enCours: false, erreur: null });

  const exporter = async () => {
    setExportEtat({ enCours: true, erreur: null });
    try {
      await dqeService.telechargerApprovisionnementExcel(projetId);
      setExportEtat({ enCours: false, erreur: null });
    } catch (err) {
      setExportEtat({ enCours: false, erreur: `Export Excel impossible : ${err.message}` });
    }
  };

  if (chargement && !fiche) return <div className="etat-chargement" role="status">Calcul de la fiche d'approvisionnement…</div>;
  if (erreur) return <Alerte type="erreur" titre="Fiche d'approvisionnement indisponible">{erreur}</Alerte>;
  if (!fiche) return null;

  const pmax = Math.max(1, ...fiche.lignes.map((l) => l.montant || 0));

  return (
    <div className="fiche-appro">
      <div className="fiche-appro-entete">
        <div>
          <p className="surtitre">Matériaux à commander</p>
          <p className="total-dqe-montant tabular">
            {fiche.total_ht != null ? formatFCFA(fiche.total_ht) : <span className="texte-discret">Total non calculé</span>}
          </p>
          <p className="texte-discret">
            Béton : {nf(fiche.volume_beton_m3, 3)} m³
            {fiche.total_ht == null && fiche.total_chiffre > 0 && <> · déjà chiffré : {formatFCFA(fiche.total_chiffre)}</>}
          </p>
        </div>
        <button type="button" className="btn btn-secondary" onClick={exporter} disabled={exportEtat.enCours || !fiche.lignes.length}>
          {exportEtat.enCours ? <Loader2 size={16} className="spin" /> : <FileSpreadsheet size={16} />} <span>Excel</span>
        </button>
      </div>

      {exportEtat.erreur && <Alerte type="erreur">{exportEtat.erreur}</Alerte>}
      {fiche.problemes.length > 0 && (
        <Alerte type="attention" titre={`${fiche.problemes.length} prix de matériau non renseigné(s)`}
          action={onParametres ? { libelle: 'Renseigner les prix', onClick: onParametres } : undefined}>
          <ul className="alerte-liste">{fiche.problemes.map((p) => <li key={p.cle_prix}>{p.message}</li>)}</ul>
        </Alerte>
      )}

      <ul className="cartes-materiaux">
        {fiche.lignes.map((l) => (
          <li key={l.cle} className="carte-materiau">
            <div className="carte-materiau-titre">
              <strong>{l.materiau}</strong>
              <span className="tabular quantite-commande">{nf(l.quantite_commande, decimales(l.unite))} {l.unite}</span>
            </div>
            <p className="texte-discret tabular">
              net {nf(l.quantite_nette, decimales(l.unite))} {l.unite} + {nf(l.pertes_pct, 1)} % de pertes
            </p>
            {l.conditionnement && <p className="conditionnement"><Truck size={14} aria-hidden="true" /> {l.conditionnement}</p>}
            {l.voyages && (
              <p className={l.voyages.nombre != null ? 'conditionnement' : 'texte-discret'}>
                <Truck size={14} aria-hidden="true" /> {l.voyages.message}
              </p>
            )}
            <div className="carte-materiau-prix">
              {l.montant != null ? (
                <>
                  <span className="tabular">{nf(l.prix_unitaire)} F × {nf(l.quantite_commande, decimales(l.unite))}</span>
                  <strong className="tabular">{formatFCFA(l.montant)}</strong>
                </>
              ) : <span className="texte-discret">prix non renseigné</span>}
            </div>
            {l.montant != null && (
              <div className="barre-part" aria-hidden="true"><span style={{ width: `${(l.montant / pmax) * 100}%` }} /></div>
            )}
            <details>
              <summary>Calcul</summary>
              <code>{l.formule}</code>
            </details>
          </li>
        ))}
      </ul>

      {(fiche.total_ht != null || fiche.messages.length > 0) && (
        <section className="recap-finances" aria-label="Total des matériaux">
          <dl>
            <dt>Total HT</dt><dd className="tabular">{fiche.total_ht != null ? formatFCFA(fiche.total_ht) : <span className="texte-discret">non calculé</span>}</dd>
            <dt>TVA{fiche.taux_tva_pct != null ? ` (${fiche.taux_tva_pct} %)` : ''}</dt>
            <dd className="tabular">{fiche.montant_tva != null ? formatFCFA(fiche.montant_tva) : <span className="texte-discret">non calculé</span>}</dd>
            <dt>Total TTC</dt><dd className="tabular">{fiche.total_ttc != null ? formatFCFA(fiche.total_ttc) : <span className="texte-discret">non calculé</span>}</dd>
          </dl>
          {fiche.messages.length > 0 && <ul className="notes">{fiche.messages.map((m) => <li key={m}>{m}</li>)}</ul>}
        </section>
      )}

      <details className="details-appro">
        <summary>Paramètres utilisés</summary>
        <table className="custom-table">
          <tbody>
            {Object.entries(fiche.parametres).map(([cle, p]) => (
              <tr key={cle}>
                <td>{p.libelle}</td>
                <td className="tabular">{p.valeur != null ? `${nf(p.valeur, 3)} ${p.unite}` : 'non renseigné'}</td>
                <td className="texte-discret">{p.source}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </details>

      {fiche.non_convertis.length > 0 && (
        <details className="details-appro">
          <summary>{fiche.non_convertis.length} ligne(s) du DQE non converties en matériaux</summary>
          <ul>{fiche.non_convertis.map((n, i) => <li key={`${n.repere}-${i}`}>{n.designation} — {n.raison}</li>)}</ul>
        </details>
      )}
      <ul className="notes texte-discret">{fiche.hypotheses.map((h) => <li key={h}>{h}</li>)}</ul>
    </div>
  );
}
