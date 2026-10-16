import React from 'react';
import { Building2, Cpu, FileSpreadsheet, RefreshCw, Users } from 'lucide-react';
import { dqeService } from '../../api/dqeService';
import useRessource from '../../hooks/useRessource';
import Alerte from '../ui/Alerte';
import KPI from '../charts/KPI';
import LineChart from '../charts/LineChart';
import { dateCourte, nf } from '../charts/palette';

// Pilotage produit (équipe interne uniquement -- l'API renvoie 403 sinon).
export default function StaffDashboard() {
  const { data, erreur, chargement, recharger } = useRessource(() => dqeService.analyticsStaff(), []);
  if (chargement && !data) return <div className="glass-panel etat-chargement" role="status">Chargement…</div>;
  if (erreur) return <Alerte type="erreur" action={{ libelle: 'Réessayer', onClick: recharger }}>{erreur}</Alerte>;
  if (!data) return null;
  const { totaux, funnel, mensuel, ia } = data;
  const base = funnel[0]?.cabinets || 0;

  return (
    <div className="dashboard">
      <header className="dashboard-entete">
        <div>
          <p className="surtitre">Équipe interne</p>
          <h2>Pilotage produit</h2>
        </div>
        <button type="button" className="btn btn-secondary" onClick={recharger} disabled={chargement}>
          <RefreshCw size={16} className={chargement ? 'spin' : ''} aria-hidden="true" /> <span>Actualiser</span>
        </button>
      </header>
      <p className="texte-discret">
        Journal d'événements {data.date_debut_fiabilite ? `tenu depuis le ${dateCourte(data.date_debut_fiabilite)}` : 'encore vide'} :
        l'activité antérieure n'est pas mesurée.
      </p>

      <section className="dashboard-kpis">
        <KPI libelle="Cabinets inscrits (journalisés)" icone={Building2} valeur={nf(totaux.cabinets_inscrits)}
          detail={`${nf(totaux.cabinets_actifs_30j)} actif(s) sur 30 jours`} />
        <KPI libelle="Utilisateurs actifs 30 j" icone={Users} valeur={nf(totaux.utilisateurs_actifs_30j)} />
        <KPI libelle="DQE générés" icone={FileSpreadsheet} valeur={nf(totaux.dqe_generes)}
          detail={`Montant traité : ${nf(totaux.montant_total_traite)} FCFA`} />
        <KPI libelle="Appels IA" icone={Cpu} valeur={nf(totaux.appels_ia)}
          detail={`${nf(ia.echecs)} échec(s) · ${Object.entries(ia.par_source).map(([s, n]) => `${s} ${n}`).join(' · ') || 'aucun'}`} />
      </section>

      <section className="glass-panel carte">
        <h3>Parcours d'adoption</h3>
        {base === 0 ? (
          <p className="texte-discret">Aucune inscription journalisée : le parcours ne peut pas encore être mesuré.</p>
        ) : (
          <ol className="funnel">
            {funnel.map((e) => (
              <li key={e.etape}>
                <span className="funnel-libelle">{e.libelle}</span>
                <span className="funnel-piste" aria-hidden="true">
                  <span className="funnel-barre" style={{ width: `${(e.cabinets / base) * 100}%` }} />
                </span>
                <span className="tabular">{e.cabinets} · {Math.round((e.cabinets / base) * 100)} %</span>
              </li>
            ))}
          </ol>
        )}
      </section>

      <section className="glass-panel carte">
        <h3>Activité mensuelle</h3>
        <LineChart series={[
          { cle: 'i', libelle: 'Inscriptions', points: mensuel.inscriptions },
          { cle: 'p', libelle: 'Projets créés', points: mensuel.projets_crees },
          { cle: 'd', libelle: 'DQE générés', points: mensuel.dqe_generes },
          { cle: 'c', libelle: 'Cabinets actifs', points: mensuel.cabinets_actifs },
        ]} />
      </section>

      <ul className="notes">{data.notes.map((n) => <li key={n}>{n}</li>)}</ul>
    </div>
  );
}
