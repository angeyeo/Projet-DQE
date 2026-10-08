import React from 'react';
import { AlertTriangle, ArrowRight, FolderOpen, Plus, RefreshCw, ShieldCheck, Wallet } from 'lucide-react';
import { dqeService } from '../../api/dqeService';
import useRessource from '../../hooks/useRessource';
import useReferentiel from '../../hooks/useReferentiel';
import Alerte from '../ui/Alerte';
import KPI from '../charts/KPI';
import DonutChart from '../charts/DonutChart';
import BarChart from '../charts/BarChart';
import LineChart from '../charts/LineChart';
import ActivityTimeline from '../charts/ActivityTimeline';
import { couleurCategorie, dateCourte, libelleCategorie, nf } from '../charts/palette';
import { STATUTS } from '../MesProjetsView';

const ETAPES = ['brouillon', 'en_etude', 'valide', 'dqe_genere'];

export default function CabinetDashboard({ onOuvrirProjet, onNouveau, onNaviguer }) {
  const { data, erreur, chargement, recharger } = useRessource(() => dqeService.analyticsCabinet(), []);
  const { data: referentiel } = useReferentiel();
  const libelleLot = (cle) => referentiel?.lots.find((l) => l.cle === cle)?.libelle || cle;

  if (chargement && !data) return <div className="glass-panel etat-chargement" role="status">Chargement du tableau de bord…</div>;
  if (erreur) {
    return <Alerte type="erreur" titre="Tableau de bord indisponible" action={{ libelle: 'Réessayer', onClick: recharger }}>{erreur}</Alerte>;
  }
  if (!data) return null;

  const { projets, dqe, elements, anomalies, projets_a_traiter: aTraiter, bareme, activite_mensuelle: mensuel } = data;
  const categories = Object.entries(dqe.repartition_par_categorie || {}).map(([cle, valeur], i) => ({
    cle, libelle: libelleCategorie(cle), valeur, couleur: couleurCategorie(cle, i),
  }));

  if (projets.total === 0) {
    return (
      <div className="dashboard">
        <div className="glass-panel etat-vide">
          <FolderOpen size={36} color="var(--ink-300)" aria-hidden="true" />
          <h2>Aucun projet dans votre cabinet</h2>
          <p>Le tableau de bord se remplit à partir de vos projets réels : créez le premier pour commencer.</p>
          <div className="etat-vide-actions">
            <button type="button" className="btn btn-primary" onClick={onNouveau}><Plus size={16} /> <span>Nouveau projet</span></button>
          </div>
        </div>
        {bareme.prix_manquants.length > 0 && <AlerteBareme bareme={bareme} onNaviguer={onNaviguer} />}
      </div>
    );
  }

  return (
    <div className="dashboard">
      <header className="dashboard-entete">
        <div>
          <p className="surtitre">Cabinet</p>
          <h2>Tableau de bord</h2>
        </div>
        <button type="button" className="btn btn-secondary" onClick={recharger} disabled={chargement}>
          <RefreshCw size={16} className={chargement ? 'spin' : ''} aria-hidden="true" /> <span>Actualiser</span>
        </button>
      </header>

      {/* Pipeline des projets : où en est chaque dossier du cabinet. */}
      <section className="pipeline" aria-label="Avancement des projets">
        {ETAPES.map((s, i) => (
          <button type="button" key={s} className={`pipeline-etape pipeline-${s}`} onClick={() => onNaviguer('projets')}>
            <span className="pipeline-nombre tabular">{projets.par_statut[s]}</span>
            <span className="pipeline-libelle">{STATUTS[s].libelle}</span>
            {i < ETAPES.length - 1 && <ArrowRight size={14} className="pipeline-fleche" aria-hidden="true" />}
          </button>
        ))}
      </section>

      <section className="dashboard-kpis">
        <KPI
          libelle="Valeur des DQE générés" icone={Wallet} type="calculé"
          valeur={dqe.projets_chiffres ? nf(dqe.valeur_totale) : null} unite="FCFA"
          detail={`${dqe.projets_chiffres} projet(s) chiffré(s) — dernier DQE de chaque projet`}
          vide="Aucun DQE généré pour l'instant."
        />
        <KPI
          libelle="Éléments validés" icone={ShieldCheck}
          valeur={nf(elements.valides)}
          detail={`${nf(elements.en_attente)} en attente de validation ingénieur`}
        />
        <KPI
          libelle="Anomalies de cohérence" icone={AlertTriangle}
          ton={anomalies.critiques ? 'critique' : anomalies.attentions ? 'attention' : 'ok'}
          valeur={nf(anomalies.critiques + anomalies.attentions)}
          detail={`${anomalies.critiques} critique(s) · ${anomalies.attentions} attention(s) · ${anomalies.calculs_a_refaire} à recalculer`}
        />
      </section>

      {bareme.prix_manquants.length > 0 && <AlerteBareme bareme={bareme} onNaviguer={onNaviguer} />}

      <div className="dashboard-grille">
        <section className="glass-panel carte">
          <h3>À traiter</h3>
          {aTraiter.length === 0 ? (
            <p className="texte-discret">Rien en attente : tous les projets sont à jour.</p>
          ) : (
            <ul className="liste-a-traiter">
              {aTraiter.map((p) => (
                <li key={p.projet_id}>
                  <div>
                    <button type="button" className="lien lien-fort" onClick={() => onOuvrirProjet(p.projet_id, 'step3')}>{p.nom}</button>
                    <span className={`statut-pastille statut-${p.statut}`}>{STATUTS[p.statut]?.libelle}</span>
                    <span className="texte-discret"> · modifié le {dateCourte(p.date_modification)}</span>
                  </div>
                  <ul className="raisons">{p.raisons.map((r) => <li key={r}>{r}</li>)}</ul>
                </li>
              ))}
            </ul>
          )}
        </section>

        <section className="glass-panel carte">
          <h3>Répartition des coûts</h3>
          <p className="texte-discret">{dqe.source}</p>
          {categories.length ? (
            <DonutChart items={categories} centre={nf(dqe.valeur_totale / 1e6, 1)} sousCentre="M FCFA" />
          ) : (
            <p className="texte-discret">Aucun DQE généré : la répartition apparaîtra au premier DQE.</p>
          )}
        </section>
      </div>

      {Object.keys(dqe.repartition_par_lot || {}).length > 0 && (
        <section className="glass-panel carte">
          <h3>Montants par lot</h3>
          <BarChart items={Object.entries(dqe.repartition_par_lot).map(([cle, valeur]) => ({ cle, libelle: libelleLot(cle), valeur }))} />
        </section>
      )}

      {anomalies.projets_concernes.length > 0 && (
        <section className="glass-panel carte">
          <h3>Projets avec anomalies de cohérence</h3>
          <div className="table-scroll">
            <table className="custom-table">
              <thead><tr><th>Projet</th><th>Critiques</th><th>Attentions</th><th>À recalculer</th></tr></thead>
              <tbody>
                {anomalies.projets_concernes.map((p) => (
                  <tr key={p.projet_id}>
                    <td><button type="button" className="lien" onClick={() => onOuvrirProjet(p.projet_id, 'analyse')}>{p.nom}</button></td>
                    <td className="tabular">{p.critiques}</td>
                    <td className="tabular">{p.attentions}</td>
                    <td className="tabular">{p.calculs_a_refaire}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </section>
      )}

      <section className="glass-panel carte">
        <h3>Activité mensuelle</h3>
        <p className="texte-discret">
          Source : journal d'activité{data.date_debut_fiabilite ? `, tenu depuis le ${dateCourte(data.date_debut_fiabilite)}` : ' (vide)'}.
        </p>
        <LineChart series={[
          { cle: 'p', libelle: 'Projets créés', points: mensuel.projets_crees },
          { cle: 'v', libelle: 'Éléments validés', points: mensuel.elements_valides },
          { cle: 'd', libelle: 'DQE générés', points: mensuel.dqe_generes },
        ]} />
      </section>

      <section className="glass-panel carte">
        <h3>Activité récente</h3>
        <ActivityTimeline evenements={data.activite_recente} onOuvrirProjet={onOuvrirProjet} />
      </section>
    </div>
  );
}

function AlerteBareme({ bareme, onNaviguer }) {
  return (
    <Alerte
      type="attention"
      titre={`Barème incomplet : ${bareme.prix_manquants.length} prix unitaire(s) non renseigné(s)`}
      action={{ libelle: 'Compléter le barème', onClick: () => onNaviguer('settingsEntreprise') }}
    >
      Aucun DQE ne peut utiliser un prix absent : renseignez-les dans les paramètres du cabinet.
      <span className="texte-discret"> ({bareme.prix_manquants.map((p) => p.libelle).join(', ')})</span>
    </Alerte>
  );
}
