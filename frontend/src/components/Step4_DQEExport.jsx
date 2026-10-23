import React, { useState } from 'react';
import { ArrowLeft, BarChart3, Download, FileSpreadsheet, Loader2, RefreshCw } from 'lucide-react';
import { dqeService, formatFCFA } from '../api/dqeService';
import useRessource from '../hooks/useRessource';
import Alerte from './ui/Alerte';
import FicheApprovisionnement from './approvisionnement/FicheApprovisionnement';
import { nf } from './charts/palette';
import BoutonNoteCalcul from './structure/BoutonNoteCalcul';
import HistoriqueDQE from './historique/HistoriqueDQE';

// Conseil d'action par code de problème renvoyé par le moteur DQE.
const CONSEILS = {
  PRIX_MANQUANT: 'Renseignez ce prix dans Paramètres cabinet › Barème.',
  PRIX_INVALIDE: 'Corrigez ce prix dans Paramètres cabinet › Barème.',
  PRIX_UNITE_A_CONFIRMER: 'Saisissez le prix au m² dans Paramètres cabinet › Barème (l’ancien prix au m³ n’est pas converti).',
  RESULTAT_VALIDE_ABSENT: "Revalidez l'élément à l'étape Validation.",
  DIMENSION_MANQUANTE: "Recalculez l'élément ou saisissez ses dimensions à l'étape Validation.",
  POSTE_RATIO_INCOMPLET: 'Complétez la géométrie du poste (étape Validation › Postes complémentaires).',
  GEOMETRIE_INCOMPLETE: 'Complétez la géométrie du poste.',
  GEOMETRIE_INVALIDE: 'Corrigez la géométrie du poste.',
  POSTE_RATIO_VIDE: 'La géométrie ne produit aucune quantité : vérifiez-la.',
  POSTE_INCOMPLET: 'Complétez le poste (quantité, prix, unité).',
  CABINET_ABSENT: 'Le projet doit être rattaché à un cabinet (administrateur).',
};

const SOURCES = {
  calcul_moteur: { libelle: 'calculé', classe: 'calculé', titre: 'Quantité issue du résultat validé du moteur' },
  ratio_reference: { libelle: 'estimé', classe: 'estimé', titre: 'Quantité estimée par un ratio de référence (voir hypothèse)' },
  saisie: { libelle: 'saisi', classe: 'saisi', titre: "Quantité saisie par l'utilisateur" },
};

function RecapFinances({ f }) {
  const lignes = [];
  if (f.nature_prix === 'debourse_sec') {
    lignes.push(['Déboursé sec', f.debourse_sec]);
    lignes.push([`Marge${f.taux_marge_pct != null ? ` (${f.taux_marge_pct} %)` : ''}`, f.montant_marge]);
  }
  lignes.push(['Total HT', f.total_ht]);
  lignes.push([`TVA${f.taux_tva_pct != null ? ` (${f.taux_tva_pct} %)` : ''}`, f.montant_tva]);
  lignes.push(['Total TTC', f.total_ttc]);
  return (
    <section className="recap-finances" aria-label="Récapitulatif financier">
      <dl>
        {lignes.map(([l, v]) => (
          <React.Fragment key={l}>
            <dt>{l}</dt>
            <dd className="tabular">{v != null ? formatFCFA(v) : <span className="texte-discret">non calculé</span>}</dd>
          </React.Fragment>
        ))}
      </dl>
      {f.messages?.length > 0 && <ul className="notes">{f.messages.map((m) => <li key={m}>{m}</li>)}</ul>}
    </section>
  );
}

// Répartition matériaux / main-d'œuvre du total (issue #92). La part
// « non décomposé » reste visible : elle n'est jamais répartie.
function RepartitionPrix({ d, total }) {
  if (!total) return null;
  const parts = [
    { cle: 'materiaux', libelle: 'Matériaux', v: d.materiaux },
    { cle: 'main_oeuvre', libelle: "Main-d'œuvre", v: d.main_oeuvre },
    { cle: 'non_decompose', libelle: 'Non décomposé', v: d.non_decompose },
  ].filter((x) => x.v > 0);
  const pct = (v) => `${nf((v / total) * 100, 1)} %`;
  return (
    <section className="repartition-prix" aria-label="Répartition matériaux et main-d'œuvre">
      <div className="repartition-barre" aria-hidden="true">
        {parts.map((x) => <span key={x.cle} className={`seg seg-${x.cle}`} style={{ flexGrow: x.v }} />)}
      </div>
      <dl className="repartition-legende">
        {parts.map((x) => (
          <div key={x.cle}>
            <dt><span className={`pastille seg-${x.cle}`} aria-hidden="true" />{x.libelle}</dt>
            <dd className="tabular">{formatFCFA(x.v)} <span className="texte-discret">{pct(x.v)}</span></dd>
          </div>
        ))}
      </dl>
      {d.lignes_non_decomposees > 0 && (
        <p className="texte-discret">
          {d.lignes_non_decomposees} ligne(s) au prix non décomposé : renseignez leurs parts dans la bibliothèque, le barème
          ou le poste pour les répartir. Aucune répartition n'est estimée.
        </p>
      )}
    </section>
  );
}

const SousTotalParts = ({ d }) => (
  <span className="parts-prix">mat. {formatFCFA(d.materiaux)} · MO {formatFCFA(d.main_oeuvre)}
    {d.non_decompose > 0 && <> · non décomposé {formatFCFA(d.non_decompose)}</>}</span>
);

const TITRES = {
  dqe: { titre: 'Devis quantitatif estimatif', sous_titre: 'généré à partir des seuls éléments validés et du barème du cabinet.' },
  appro: { titre: "Fiche d'approvisionnement", sous_titre: 'matériaux à acheter, calculés à partir des quantités du DQE.' },
  historique: { titre: 'Historique du DQE', sous_titre: 'versions figées et comparaison poste par poste.' },
};

export default function Step4_DQEExport({ projetId, nomProjet, onBack, onCorriger, onAnalyse, onParametres }) {
  const [onglet, setOnglet] = useState('dqe');
  const { data: dqe, erreur, detail, chargement, recharger } = useRessource(() => dqeService.genererDQE(projetId), [projetId]);
  const [exportEtat, setExportEtat] = useState({ enCours: null, erreur: null });
  // Colonnes matériaux / main-d'œuvre dès qu'au moins une ligne est décomposée.
  const avecParts = !!dqe?.lignes?.some((l) => l.decomposition === 'decompose');

  const exporter = async (format) => {
    setExportEtat({ enCours: format, erreur: null });
    try {
      await dqeService.telechargerDQEFichier(projetId, format);
      setExportEtat({ enCours: null, erreur: null });
    } catch (err) {
      setExportEtat({ enCours: null, erreur: `Export ${format === 'pdf' ? 'PDF' : 'Excel'} impossible : ${err.message}` });
    }
  };

  return (
    <div className="glass-panel etape">
      <header className="etape-entete">
        <div>
          <p className="surtitre">Étape 4</p>
          <h2>{TITRES[onglet].titre}{onglet === 'dqe' && dqe?.version ? <span className="badge-version">v{dqe.version.numero}</span> : null}</h2>
          <p className="texte-discret">{nomProjet} — {TITRES[onglet].sous_titre}</p>
        </div>
        {onglet === 'dqe' && <div className="actions-ligne">
          <BoutonNoteCalcul projetId={projetId} />
          <button type="button" className="btn btn-secondary" onClick={recharger} disabled={chargement}>
            <RefreshCw size={16} className={chargement ? 'spin' : ''} aria-hidden="true" /> <span>Régénérer</span>
          </button>
          <button type="button" className="btn btn-secondary" disabled={!dqe || !!exportEtat.enCours} onClick={() => exporter('excel')}>
            {exportEtat.enCours === 'excel' ? <Loader2 size={16} className="spin" /> : <FileSpreadsheet size={16} />} <span>Excel</span>
          </button>
          <button type="button" className="btn btn-primary" disabled={!dqe || !!exportEtat.enCours} onClick={() => exporter('pdf')}>
            {exportEtat.enCours === 'pdf' ? <Loader2 size={16} className="spin" /> : <Download size={16} />} <span>PDF</span>
          </button>
        </div>}
      </header>

      <div className="onglets" role="tablist" aria-label="Documents du projet">
        <button type="button" role="tab" aria-selected={onglet === 'dqe'} className={onglet === 'dqe' ? 'onglet actif' : 'onglet'}
          onClick={() => setOnglet('dqe')}>Devis (DQE)</button>
        <button type="button" role="tab" aria-selected={onglet === 'appro'} className={onglet === 'appro' ? 'onglet actif' : 'onglet'}
          onClick={() => setOnglet('appro')} disabled={!dqe}
          title={!dqe ? "Disponible quand le DQE est calculé" : undefined}>Fiche d'approvisionnement</button>
        <button type="button" role="tab" aria-selected={onglet === 'historique'} className={onglet === 'historique' ? 'onglet actif' : 'onglet'}
          onClick={() => setOnglet('historique')}>Historique</button>
      </div>

      {onglet === 'appro' && dqe && <FicheApprovisionnement projetId={projetId} onParametres={onParametres} />}
      {onglet === 'historique' && <HistoriqueDQE key={dqe?.version?.numero ?? 'aucune'} projetId={projetId} />}

      {onglet === 'dqe' && <>
      {exportEtat.erreur && <Alerte type="erreur">{exportEtat.erreur}</Alerte>}
      {chargement && !dqe && <div className="etat-chargement" role="status">Calcul du DQE…</div>}

      {erreur && (
        <div className="pile-alertes">
          <Alerte type="erreur" titre="Le DQE ne peut pas être généré" action={{ libelle: 'Corriger', onClick: onCorriger }}>
            {erreur}
          </Alerte>
          {detail?.elements_en_attente?.length > 0 && (
            <Alerte type="attention" titre={`${detail.elements_en_attente.length} élément(s) en attente de validation`}>
              {detail.elements_en_attente.join(', ')}
            </Alerte>
          )}
          {detail?.problemes?.length > 0 && (
            <ul className="liste-problemes">
              {detail.problemes.map((p, i) => (
                <li key={`${p.code}-${p.cle_prix || p.element_id || p.poste_id || i}`}>
                  <code>{p.code}</code>
                  <span>{p.message}</span>
                  {CONSEILS[p.code] && <span className="texte-discret">{CONSEILS[p.code]}</span>}
                </li>
              ))}
            </ul>
          )}
        </div>
      )}

      {dqe && (
        <>
          <section className="total-dqe" aria-label="Montant total">
            <div>
              <p className="surtitre">Total des ouvrages</p>
              <p className="total-dqe-montant tabular">{formatFCFA(dqe.total_general)}</p>
              <p className="texte-discret">{dqe.montant_lettres}</p>
            </div>
            <dl className="grille-donnees">
              <dt>Béton structurel</dt><dd className="tabular">{nf(dqe.synthese.beton_m3, 3)} m³</dd>
              <dt>Acier</dt><dd className="tabular">{nf(dqe.synthese.acier_kg, 1)} kg</dd>
              <dt>Ratio acier/béton</dt><dd className="tabular">{dqe.synthese.ratio_acier_kg_m3 != null ? `${nf(dqe.synthese.ratio_acier_kg_m3, 1)} kg/m³` : '—'}</dd>
              {dqe.synthese.acier_estime_par_ratio_kg > 0 && (
                <><dt>dont acier estimé</dt><dd className="tabular">{nf(dqe.synthese.acier_estime_par_ratio_kg, 1)} kg</dd></>
              )}
            </dl>
            <button type="button" className="btn btn-secondary" onClick={onAnalyse}><BarChart3 size={16} /> <span>Analyse</span></button>
          </section>

          {avecParts && <RepartitionPrix d={dqe.decomposition} total={dqe.total_general} />}

          {dqe.finances && <RecapFinances f={dqe.finances} />}

          {dqe.hypotheses_projet?.length > 0 && (
            <Alerte type="info" titre="Hypothèses de calcul du projet" liste={dqe.hypotheses_projet} />
          )}

          {dqe.hypotheses.length > 0 && (
            <section className="hypotheses-dqe">
              <h3>Hypothèses de métré</h3>
              <ol>{dqe.hypotheses.map((h) => <li key={h}>{h}</li>)}</ol>
            </section>
          )}

          {dqe.lots.map((lot) => (
            <section key={lot.lot} className="lot-dqe">
              <div className="lot-dqe-entete">
                <h3>{lot.libelle}</h3>
                <span className="tabular">
                  {formatFCFA(lot.sous_total)}
                  {avecParts && lot.decomposition && <SousTotalParts d={lot.decomposition} />}
                </span>
              </div>
              {(lot.sous_lots || [{ libelle: null, lignes: lot.lignes }]).map((sl) => (
                <div key={sl.libelle || 'tout'} className="sous-lot-dqe">
                  {sl.libelle && (
                    <div className="sous-lot-entete"><h4>{sl.libelle}</h4><span className="tabular">{formatFCFA(sl.sous_total)}
                      {avecParts && sl.decomposition && <SousTotalParts d={sl.decomposition} />}</span></div>
                  )}
                  <div className="table-scroll">
                    <table className="custom-table table-dqe">
                      <thead>
                        <tr><th>Repère</th><th>Désignation</th><th>U</th><th>Quantité</th><th>PU</th>
                          {avecParts && <><th>dont matériaux</th><th>dont main-d'œuvre</th></>}<th>Montant</th></tr>
                      </thead>
                      <tbody>
                        {sl.lignes.map((l, i) => {
                          const src = SOURCES[l.source_quantite] || { libelle: l.type_donnee || l.source_quantite, classe: 'saisi' };
                          const nHyp = l.hypothese ? dqe.hypotheses.indexOf(l.hypothese) + 1 : 0;
                          return (
                            <tr key={`${l.repere}-${l.designation}-${i}`}>
                              <td>{l.repere || '—'}</td>
                              <td>
                                {l.designation}
                                {l.formule_quantite && <div className="formule-ligne"><code>{l.formule_quantite}</code></div>}
                              </td>
                              <td>{l.unite}</td>
                              <td className="tabular">
                                {nf(l.quantite, 3)}{' '}
                                <span className={`type-donnee type-${src.classe}`} title={src.titre}>{src.libelle}</span>
                                {nHyp > 0 && <sup className="renvoi-hyp" title={l.hypothese}>H{nHyp}</sup>}
                              </td>
                              <td className="tabular" title={l.prix_source ? `${l.prix_source}${l.prix_date ? ` — ${l.prix_date}` : ''}` : undefined}>
                                {nf(l.prix_unitaire, 2)}
                                {l.prix_source && <div className="texte-discret prix-source">{l.prix_date || 'date non tracée'}</div>}
                              </td>
                              {avecParts && (l.decomposition === 'decompose' ? (
                                <><td className="tabular">{nf(l.montant_materiaux)}</td><td className="tabular">{nf(l.montant_main_oeuvre)}</td></>
                              ) : (
                                <td colSpan={2} className="cellule-non-decompose">non décomposé</td>
                              ))}
                              <td className="tabular"><strong>{nf(l.montant)}</strong></td>
                            </tr>
                          );
                        })}
                      </tbody>
                    </table>
                  </div>
                </div>
              ))}
            </section>
          ))}
          <p className="texte-discret">
            Montant de ligne = quantité (arrondie au millième) × prix unitaire du barème, arrondi au FCFA.
            Parts : matériaux = quantité × prix matériaux, arrondi au FCFA ; main-d'œuvre = montant − matériaux.
            Un prix sans parts saisies reste « non décomposé » (fourni-posé) : aucune répartition n'est estimée.
          </p>
        </>
      )}
      </>}

      <div className="navigation-etapes">
        <button type="button" className="btn btn-secondary" onClick={onBack}><ArrowLeft size={18} /> <span>Plan de fondation</span></button>
      </div>
    </div>
  );
}
