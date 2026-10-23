import React, { useEffect, useMemo, useState } from 'react';
import { ArrowRight, Download, GitCompare, History, Loader2 } from 'lucide-react';
import { dqeService, formatFCFA } from '../../api/dqeService';
import useRessource from '../../hooks/useRessource';
import Alerte from '../ui/Alerte';
import { nf } from '../charts/palette';

const STATUTS = {
  ajoute: { libelle: 'ajouté', classe: 'ajoute' },
  supprime: { libelle: 'supprimé', classe: 'supprime' },
  modifie: { libelle: 'modifié', classe: 'modifie' },
  identique: { libelle: 'identique', classe: 'identique' },
};

const dateHeure = (iso) => new Date(iso).toLocaleString('fr-FR', { dateStyle: 'medium', timeStyle: 'short' });
const signe = (v) => (v > 0 ? `+${nf(v)}` : nf(v));

// Origine de l'écart total, calculée par le serveur (méthode des écarts :
// effet quantité + effet prix + postes ajoutés + postes supprimés + arrondi
// = écart exact). Barres proportionnelles à la valeur absolue.
function OrigineEcart({ c }) {
  const parts = [
    { cle: 'quantite', libelle: 'Quantités', v: c.effet_quantite, aide: '(q2 − q1) × PU avant' },
    { cle: 'prix', libelle: 'Prix unitaires', v: c.effet_prix, aide: 'q2 × (PU après − PU avant)' },
    { cle: 'ajoutes', libelle: 'Postes ajoutés', v: c.ecart_postes_ajoutes },
    { cle: 'supprimes', libelle: 'Postes supprimés', v: c.ecart_postes_supprimes },
    { cle: 'arrondi', libelle: 'Arrondis au FCFA', v: c.arrondi },
  ];
  const max = Math.max(1, ...parts.map((p) => Math.abs(p.v)));
  return (
    <section className="origine-ecart" aria-label="D'où vient l'écart">
      <h4>D&apos;où vient l&apos;écart</h4>
      <dl>
        {parts.map((p) => (
          <div key={p.cle} className={`ligne-ecart ${p.v > 0 ? 'hausse' : p.v < 0 ? 'baisse' : 'nul'}`}>
            <dt>{p.libelle}{p.aide && <small className="texte-discret"> {p.aide}</small>}</dt>
            <dd>
              <span className="barre-ecart" aria-hidden="true"><span style={{ width: `${(Math.abs(p.v) / max) * 100}%` }} /></span>
              <span className="tabular">{signe(p.v)}</span>
            </dd>
          </div>
        ))}
      </dl>
    </section>
  );
}

function Comparaison({ projetId, de, a }) {
  const [tout, setTout] = useState(false);
  const { data: c, erreur, chargement, recharger } = useRessource(
    () => dqeService.comparerVersionsDQE(projetId, de, a), [projetId, de, a]);
  // Les plus gros écarts d'abord (en valeur absolue) : là où l'œil doit aller.
  const postes = useMemo(() => (c?.postes || []).filter((p) => tout || p.statut !== 'identique')
    .sort((x, y) => Math.abs(y.ecart) - Math.abs(x.ecart)), [c, tout]);

  if (chargement && !c) return <div className="etat-chargement" role="status">Comparaison…</div>;
  if (erreur) return <Alerte type="erreur" action={{ libelle: 'Réessayer', onClick: recharger }}>{erreur}</Alerte>;
  if (!c) return null;
  const sens = c.ecart > 0 ? 'hausse' : c.ecart < 0 ? 'baisse' : 'nul';
  return (
    <div className="comparaison-dqe">
      <section className={`ecart-total ${sens}`} aria-label="Écart total">
        <div>
          <p className="surtitre">v{c.de.numero} → v{c.a.numero}</p>
          <p className="ecart-total-montants tabular">
            {formatFCFA(c.total_avant)} <ArrowRight size={18} aria-hidden="true" /> {formatFCFA(c.total_apres)}
          </p>
        </div>
        <p className="ecart-total-valeur tabular">
          {signe(c.ecart)} FCFA{c.ecart_pct != null && <span> ({c.ecart_pct > 0 ? '+' : ''}{nf(c.ecart_pct, 1)} %)</span>}
        </p>
      </section>

      <div className="comparaison-grille">
        <OrigineEcart c={c} />
        <section className="ecart-lots" aria-label="Écart par lot">
          <h4>Par lot</h4>
          <ul>
            {c.lots.map((l) => (
              <li key={l.lot}>
                <span>{l.libelle}</span>
                <span className={`tabular ${l.ecart > 0 ? 'hausse' : l.ecart < 0 ? 'baisse' : ''}`}>{l.ecart ? signe(l.ecart) : '='}</span>
              </li>
            ))}
          </ul>
          <p className="texte-discret">
            {c.compte.modifie} modifié(s) · {c.compte.ajoute} ajouté(s) · {c.compte.supprime} supprimé(s) · {c.compte.identique} identique(s)
          </p>
        </section>
      </div>

      <div className="entete-postes">
        <h4>Poste par poste</h4>
        <label className="case-a-cocher">
          <input type="checkbox" checked={tout} onChange={(e) => setTout(e.target.checked)} /> Afficher aussi les postes identiques
        </label>
      </div>
      {postes.length === 0 ? (
        <p className="texte-discret">Aucun poste n&apos;a changé entre ces deux versions.</p>
      ) : (
        <div className="table-scroll">
          <table className="custom-table table-comparaison">
            <thead>
              <tr><th>Poste</th><th>Quantité</th><th>Prix unitaire</th><th>Montant</th><th>Écart</th></tr>
            </thead>
            <tbody>
              {postes.map((p) => (
                <tr key={`${p.lot}|${p.designation}|${p.unite}`} className={`statut-${p.statut}`}>
                  <td>
                    <strong>{p.designation}</strong>
                    <div className="texte-discret">{p.lot_libelle} · <span className={`pastille-statut ${STATUTS[p.statut].classe}`}>{STATUTS[p.statut].libelle}</span></div>
                  </td>
                  <td className="tabular">{nf(p.quantite_avant, 3)} → {nf(p.quantite_apres, 3)} <span className="texte-discret">{p.unite}</span></td>
                  <td className="tabular">{nf(p.prix_unitaire_avant, 2)} → {nf(p.prix_unitaire_apres, 2)}</td>
                  <td className="tabular">{nf(p.montant_avant)} → {nf(p.montant_apres)}</td>
                  <td className="tabular">
                    <strong className={p.ecart > 0 ? 'hausse' : p.ecart < 0 ? 'baisse' : ''}>{signe(p.ecart)}</strong>
                    {p.effet_quantite != null && p.ecart !== 0 && (
                      <div className="texte-discret detail-effets">
                        qté {signe(p.effet_quantite)} · prix {signe(p.effet_prix)}{p.arrondi ? ` · arrondi ${signe(p.arrondi)}` : ''}
                      </div>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}

// Historique des versions du DQE (issue #82) : chaque DQE généré qui diffère
// du précédent est figé par le serveur ; aucune version n'est modifiable.
export default function HistoriqueDQE({ projetId }) {
  const { data: versions, erreur, chargement, recharger } = useRessource(
    () => dqeService.listerVersionsDQE(projetId), [projetId]);
  const [choix, setChoix] = useState({ de: null, a: null });
  const [export_, setExport] = useState({ enCours: null, erreur: null });

  useEffect(() => {
    if (versions?.length >= 2) setChoix({ de: versions[1].numero, a: versions[0].numero });
  }, [versions]);

  const exporter = async (numero, format) => {
    setExport({ enCours: `${numero}-${format}`, erreur: null });
    try {
      await dqeService.telechargerVersionDQE(projetId, numero, format);
      setExport({ enCours: null, erreur: null });
    } catch (err) {
      setExport({ enCours: null, erreur: `Export de la version ${numero} impossible : ${err.message}` });
    }
  };

  if (chargement && !versions) return <div className="etat-chargement" role="status">Chargement de l&apos;historique…</div>;
  if (erreur) return <Alerte type="erreur" action={{ libelle: 'Réessayer', onClick: recharger }}>{`Historique indisponible : ${erreur}`}</Alerte>;
  if (!versions?.length) {
    return (
      <div className="etat-vide-compact">
        <History size={28} aria-hidden="true" />
        <p>Aucune version enregistrée : chaque DQE généré (onglet « Devis ») qui diffère du précédent devient une version.</p>
      </div>
    );
  }

  return (
    <div className="historique-dqe">
      {export_.erreur && <Alerte type="erreur">{export_.erreur}</Alerte>}
      <ol className="frise-versions" aria-label="Versions du DQE">
        {versions.map((v, i) => {
          const precedente = versions[i + 1];
          const delta = precedente ? v.total_general - precedente.total_general : null;
          return (
            <li key={v.numero}>
              <span className="numero-version">v{v.numero}</span>
              <div className="corps-version">
                <strong className="tabular">{formatFCFA(v.total_general)}</strong>
                {delta != null && delta !== 0 && (
                  <span className={`delta tabular ${delta > 0 ? 'hausse' : 'baisse'}`}>{signe(delta)}</span>
                )}
                <span className="texte-discret">{dateHeure(v.date)}{v.auteur ? ` · ${v.auteur}` : ''} · {v.nb_lignes} ligne(s)</span>
              </div>
              <div className="actions-version">
                {['pdf', 'excel'].map((f) => (
                  <button key={f} type="button" className="btn btn-secondary btn-compact" disabled={!!export_.enCours}
                    aria-label={`Télécharger la version ${v.numero} en ${f === 'pdf' ? 'PDF' : 'Excel'}`}
                    onClick={() => exporter(v.numero, f)}>
                    {export_.enCours === `${v.numero}-${f}` ? <Loader2 size={14} className="spin" /> : <Download size={14} aria-hidden="true" />}
                    <span>{f === 'pdf' ? 'PDF' : 'Excel'}</span>
                  </button>
                ))}
              </div>
            </li>
          );
        })}
      </ol>

      {versions.length < 2 ? (
        <p className="texte-discret">Une seule version pour l&apos;instant : la comparaison sera possible dès la prochaine version.</p>
      ) : (
        <section className="bloc-comparaison" aria-labelledby="titre-comparaison">
          <div className="choix-comparaison">
            <h3 id="titre-comparaison"><GitCompare size={18} aria-hidden="true" /> Comparer</h3>
            <select aria-label="Version de départ" className="form-select" value={choix.de ?? ''}
              onChange={(e) => setChoix({ ...choix, de: Number(e.target.value) })}>
              {versions.map((v) => <option key={v.numero} value={v.numero}>v{v.numero} — {formatFCFA(v.total_general)}</option>)}
            </select>
            <ArrowRight size={16} aria-hidden="true" />
            <select aria-label="Version d'arrivée" className="form-select" value={choix.a ?? ''}
              onChange={(e) => setChoix({ ...choix, a: Number(e.target.value) })}>
              {versions.map((v) => <option key={v.numero} value={v.numero}>v{v.numero} — {formatFCFA(v.total_general)}</option>)}
            </select>
          </div>
          {choix.de != null && choix.a != null && (choix.de === choix.a
            ? <p className="texte-discret">Choisissez deux versions différentes.</p>
            : <Comparaison projetId={projetId} de={choix.de} a={choix.a} />)}
        </section>
      )}
    </div>
  );
}
