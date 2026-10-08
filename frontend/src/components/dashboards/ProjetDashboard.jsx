import React from 'react';
import { Boxes, RefreshCw, ShieldCheck, Wallet, Weight } from 'lucide-react';
import { dqeService, LIBELLES_TYPES } from '../../api/dqeService';
import useRessource from '../../hooks/useRessource';
import Alerte from '../ui/Alerte';
import KPI from '../charts/KPI';
import Progress from '../charts/Progress';
import DonutChart from '../charts/DonutChart';
import BarChart from '../charts/BarChart';
import AlertCard from '../charts/AlertCard';
import ActivityTimeline from '../charts/ActivityTimeline';
import { couleurCategorie, dateCourte, dateHeure, libelleCategorie, nf } from '../charts/palette';
import { STATUTS } from '../MesProjetsView';
import VariantesPanel from './VariantesPanel';

const LIBELLES_GROUPES = {
  ouvrages: 'Ouvrages (fourni-posé)',
  postes_saisis: 'Postes saisis',
  autres: 'Autres',
};

// Règle graduée : position du ratio acier/béton obtenu par rapport à la
// fourchette de référence (constantes du moteur).
function RegleRatio({ r }) {
  const [mini, maxi] = r.fourchette;
  const borneMax = Math.max(maxi * 1.5, r.ratio_kg_m3 * 1.1);
  const pos = (v) => `${Math.min(100, (v / borneMax) * 100)}%`;
  return (
    <div className="regle-ratio">
      <div className="regle-ratio-entete">
        <strong>{LIBELLES_TYPES[r.type_element.toLowerCase()] || r.type_element}</strong>
        <span className="tabular">{nf(r.ratio_kg_m3, 1)} kg/m³</span>
        {r.acier_estime ? (
          <span className="type-donnee type-estimé" title="Acier estimé au ratio de référence : la comparaison ne prouve rien">estimé</span>
        ) : (
          <span className={`statut-pastille ${r.dans_fourchette ? 'statut-dqe_genere' : 'statut-attention'}`}>
            {r.dans_fourchette ? 'dans la fourchette' : 'hors fourchette'}
          </span>
        )}
      </div>
      <div className="regle-ratio-piste" aria-hidden="true">
        <span className="regle-ratio-zone" style={{ left: pos(mini), width: `calc(${pos(maxi)} - ${pos(mini)})` }} />
        <span className="regle-ratio-curseur" style={{ left: pos(r.ratio_kg_m3) }} />
      </div>
      <div className="regle-ratio-legende texte-discret tabular">
        Fourchette de référence {mini}–{maxi} kg/m³ · béton {nf(r.beton_m3, 3)} m³ · acier {nf(r.acier_kg, 1)} kg
      </div>
    </div>
  );
}

export default function ProjetDashboard({ projetId, onNaviguer }) {
  const { data, erreur, chargement, recharger } = useRessource(() => dqeService.analyticsProjet(projetId), [projetId]);
  if (chargement && !data) return <div className="glass-panel etat-chargement" role="status">Analyse du projet…</div>;
  if (erreur) return <Alerte type="erreur" action={{ libelle: 'Réessayer', onClick: recharger }}>{erreur}</Alerte>;
  if (!data) return null;

  const { projet, progression, cout, alertes } = data;
  const synthese = cout?.synthese;

  return (
    <div className="dashboard">
      <header className="dashboard-entete">
        <div>
          <p className="surtitre">Analyse du projet</p>
          <h2>{projet.nom} <span className={`statut-pastille statut-${data.statut}`}>{STATUTS[data.statut]?.libelle}</span></h2>
          <p className="texte-discret">Modifié le {dateCourte(projet.date_modification)}</p>
        </div>
        <button type="button" className="btn btn-secondary" onClick={recharger} disabled={chargement}>
          <RefreshCw size={16} className={chargement ? 'spin' : ''} aria-hidden="true" /> <span>Actualiser</span>
        </button>
      </header>

      <section className="dashboard-kpis">
        <KPI
          libelle={cout?.partiel ? 'Coût des éléments validés (partiel)' : 'Coût estimé'} icone={Wallet} type="calculé"
          ton={cout?.partiel ? 'attention' : 'neutre'}
          valeur={cout ? nf(cout.total) : null} unite="FCFA"
          detail={cout?.partiel ? `${cout.elements_exclus} élément(s) non validé(s) exclu(s) du coût` : 'Tous les éléments validés'}
          vide={data.problemes_dqe.length ? 'Données manquantes : voir ci-dessous.' : 'Aucun élément validé à chiffrer.'}
        />
        <KPI libelle="Béton structurel" icone={Boxes} type="calculé"
          valeur={synthese ? nf(synthese.beton_m3, 3) : null} unite="m³" vide="Non calculé." />
        <KPI libelle="Acier" icone={Weight} type={synthese?.acier_estime_par_ratio_kg ? 'estimé' : 'calculé'}
          valeur={synthese ? nf(synthese.acier_kg, 1) : null} unite="kg"
          detail={synthese ? `Ratio global ${nf(synthese.ratio_acier_kg_m3, 1)} kg/m³${synthese.acier_estime_par_ratio_kg ? ` · dont ${nf(synthese.acier_estime_par_ratio_kg, 1)} kg estimés au ratio` : ''}` : null}
          vide="Non calculé." />
        <KPI libelle="Validation ingénieur" icone={ShieldCheck}
          valeur={progression.elements ? `${progression.valides}/${progression.elements}` : null}
          vide="Aucun élément : générez la trame."
          detail={progression.taux != null ? `${Math.round(progression.taux * 100)} % validés` : null} />
      </section>

      {progression.elements > 0 && (
        <section className="glass-panel carte">
          <Progress valeur={progression.valides} total={progression.elements} libelle="Éléments validés" />
          {data.elements_non_valides.length > 0 && (
            <p className="texte-discret">
              En attente : {data.elements_non_valides.slice(0, 15).map((e) => e.identifiant).join(', ')}
              {data.elements_non_valides.length > 15 ? ` … (+${data.elements_non_valides.length - 15})` : ''}{' '}
              <button type="button" className="lien" onClick={() => onNaviguer('step3')}>Aller à la validation</button>
            </p>
          )}
        </section>
      )}

      {data.problemes_dqe.length > 0 && (
        <Alerte type="attention" titre="Coût non calculable" liste={data.problemes_dqe.map((p) => p.message)}
          action={{ libelle: 'Paramètres cabinet', onClick: () => onNaviguer('settingsEntreprise') }}>
          Le coût n'est pas affiché tant que ces données manquent (aucun montant partiel présenté comme complet).
        </Alerte>
      )}

      {alertes.length > 0 && (
        <section className="glass-panel carte">
          <h3>Alertes</h3>
          <div className="pile-alertes">
            {alertes.map((a, i) => (
              <AlertCard key={`${a.code || a.niveau}-${i}`} niveau={a.niveau} message={a.message} elements={a.elements}
                action={a.niveau === 'INFORMATION' ? { libelle: 'Régénérer le DQE', onClick: () => onNaviguer('step4') } : undefined} />
            ))}
          </div>
        </section>
      )}

      {cout && (
        <div className="dashboard-grille">
          <section className="glass-panel carte">
            <h3>Répartition par catégorie</h3>
            <DonutChart
              items={Object.entries(cout.par_categorie).map(([cle, valeur], i) => ({ cle, libelle: libelleCategorie(cle), valeur, couleur: couleurCategorie(cle, i) }))}
              centre={nf(cout.total / 1e6, 2)} sousCentre="M FCFA"
            />
            <p className="texte-discret">{cout.note_ventilation}</p>
          </section>
          <section className="glass-panel carte">
            <h3>Par lot</h3>
            <BarChart items={cout.par_lot.map((l) => ({ cle: l.lot, libelle: l.libelle, valeur: l.montant }))} />
            <h4 className="sous-titre">Par nature</h4>
            <BarChart items={Object.entries(cout.par_groupe).filter(([, v]) => v > 0).map(([cle, valeur]) => ({ cle, libelle: LIBELLES_GROUPES[cle] || cle, valeur }))} />
          </section>
        </div>
      )}

      {cout?.ratios_acier?.length > 0 && (
        <section className="glass-panel carte">
          <h3>Ratios acier / béton</h3>
          <p className="texte-discret">Contrôle de plausibilité : un ratio hors fourchette n'est pas une erreur, c'est une valeur à vérifier.</p>
          {cout.ratios_acier.map((r) => <RegleRatio key={r.type_element} r={r} />)}
        </section>
      )}

      {cout?.hypotheses?.length > 0 && (
        <section className="glass-panel carte">
          <h3>Hypothèses retenues</h3>
          <ul className="notes">{cout.hypotheses.map((h, i) => <li key={i}>{typeof h === 'string' ? h : h.message || JSON.stringify(h)}</li>)}</ul>
        </section>
      )}

      {progression.elements > 0 && <VariantesPanel projetId={projetId} />}

      <section className="glass-panel carte">
        <h3>Dernières actions</h3>
        {data.dernier_dqe && (
          <p className="texte-discret">Dernier DQE : {dateHeure(data.dernier_dqe.date)} · {nf(data.dernier_dqe.total_general)} FCFA</p>
        )}
        <ActivityTimeline evenements={data.dernieres_actions} afficherProjet={false} />
      </section>
    </div>
  );
}
