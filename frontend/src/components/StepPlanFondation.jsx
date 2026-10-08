import React, { useEffect, useState } from 'react';
import { ArrowLeft, ArrowRight, CheckCircle2, Download, FileText, Layers } from 'lucide-react';
import { dqeService, formatSection } from '../api/dqeService';
import Alerte from './ui/Alerte';

// Plan de fondation : semelles positionnées (coordonnées réelles issues de
// la trame ou du plan importé), aperçu PDF généré par le serveur, exports.
export default function StepPlanFondation({ projetId, peutValider, onBack, onNext }) {
  const [semelles, setSemelles] = useState(null);
  const [erreurPlan, setErreurPlan] = useState(null);
  const [apercu, setApercu] = useState({ url: null, erreur: null, detail: null });
  const [action, setAction] = useState({ enCours: null, erreur: null, succes: null });

  useEffect(() => {
    let annule = false;
    let urlCree = null;
    setSemelles(null);
    setErreurPlan(null);
    setApercu({ url: null, erreur: null, detail: null });
    dqeService.recupererPlanFondation(projetId)
      .then((d) => { if (!annule) setSemelles(d.semelles || []); })
      .catch((err) => { if (!annule) setErreurPlan(err.message); });
    dqeService.recupererPlanFondationPDF(projetId)
      .then((blob) => {
        urlCree = window.URL.createObjectURL(blob);
        if (!annule) setApercu({ url: urlCree, erreur: null, detail: null });
      })
      .catch((err) => { if (!annule) setApercu({ url: null, erreur: err.message, detail: err.data?.elements || null }); });
    return () => {
      annule = true;
      if (urlCree) window.URL.revokeObjectURL(urlCree);
    };
  }, [projetId]);

  const executer = async (cle, fn, succes) => {
    setAction({ enCours: cle, erreur: null, succes: null });
    try {
      await fn();
      setAction({ enCours: null, erreur: null, succes });
      return true;
    } catch (err) {
      setAction({ enCours: null, erreur: err.message, succes: null });
      return false;
    }
  };

  const telechargerPDF = () => executer('pdf', async () => {
    const blob = await dqeService.recupererPlanFondationPDF(projetId);
    const url = window.URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `Plan_Coffrage_${projetId}.pdf`;
    document.body.appendChild(a);
    a.click();
    a.remove();
    window.URL.revokeObjectURL(url);
  }, null);

  const valider = async () => {
    if (await executer('valider', () => dqeService.validerPlanFondation(projetId), 'Plan de fondation validé.')) onNext();
  };

  return (
    <div className="glass-panel etape">
      <header className="etape-entete">
        <div>
          <p className="surtitre">Étape 3 bis</p>
          <h2>Plan de fondation</h2>
          <p className="texte-discret">Positions réelles des semelles et dimensions issues des résultats validés (sinon calculés).</p>
        </div>
        <div className="actions-ligne">
          <button type="button" className="btn btn-secondary" disabled={!!action.enCours || !apercu.url} onClick={telechargerPDF}>
            <FileText size={16} aria-hidden="true" /> <span>{action.enCours === 'pdf' ? 'Téléchargement…' : 'PDF'}</span>
          </button>
          <button type="button" className="btn btn-secondary" disabled={!!action.enCours || !apercu.url}
            onClick={() => executer('dxf', () => dqeService.telechargerPlanFondationDXF(projetId), null)}>
            <Download size={16} aria-hidden="true" /> <span>{action.enCours === 'dxf' ? 'Téléchargement…' : 'DXF'}</span>
          </button>
        </div>
      </header>

      {action.erreur && <Alerte type="erreur">{action.erreur}</Alerte>}
      {action.succes && <Alerte type="succes">{action.succes}</Alerte>}
      {erreurPlan && <Alerte type="erreur" titre="Plan indisponible">{erreurPlan}</Alerte>}

      <section className="apercu-plan" aria-label="Aperçu du plan de coffrage">
        <h3><Layers size={18} aria-hidden="true" /> Aperçu</h3>
        {apercu.url ? (
          <iframe src={`${apercu.url}#toolbar=0&navpanes=0`} title="Aperçu du plan de fondation" className="cadre-pdf" />
        ) : apercu.erreur ? (
          <Alerte type="attention" titre="Aperçu non généré" liste={apercu.detail}>{apercu.erreur}</Alerte>
        ) : (
          <div className="etat-chargement" role="status">Génération de l'aperçu…</div>
        )}
      </section>

      <section>
        <h3>Semelles</h3>
        {semelles === null && !erreurPlan && <p className="texte-discret" role="status">Chargement…</p>}
        {semelles?.length === 0 && <p className="texte-discret">Aucune semelle dans ce projet.</p>}
        {semelles?.length > 0 && (
          <div className="table-scroll">
            <table className="custom-table">
              <thead><tr><th>Repère</th><th>Dimensions</th><th>X (m)</th><th>Y (m)</th><th>Contrainte sol</th><th>Statut</th></tr></thead>
              <tbody>
                {semelles.map((s) => {
                  const res = s.resultat_valide || s.resultat_calcul || {};
                  return (
                    <tr key={s.id}>
                      <td><strong>{s.identifiant}</strong></td>
                      <td className="tabular">
                        {formatSection('semelle', res) || <span className="texte-discret">non calculée</span>}
                        {res.hauteur_cm && <span className="texte-discret"> · h {res.hauteur_cm} cm</span>}
                      </td>
                      <td className="tabular">{s.position_x ?? <span className="texte-erreur">manquante</span>}</td>
                      <td className="tabular">{s.position_y ?? <span className="texte-erreur">manquante</span>}</td>
                      <td className="tabular">{s.taux_travail_sol != null ? `${s.taux_travail_sol} kN/m²` : '—'}</td>
                      <td><span className={s.statut === 'valide' ? 'badge badge-locked' : 'badge badge-unlocked'}>{s.statut === 'valide' ? 'Validée' : 'Non validée'}</span></td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        )}
      </section>

      <div className="navigation-etapes">
        <button type="button" className="btn btn-secondary" onClick={onBack}><ArrowLeft size={18} /> <span>Validation</span></button>
        <div className="actions-ligne">
          <button type="button" className="btn btn-secondary" onClick={onNext}><span>Passer au DQE</span></button>
          {peutValider ? (
            <button type="button" className="btn btn-primary" disabled={!!action.enCours} onClick={valider}>
              <CheckCircle2 size={18} aria-hidden="true" /> <span>{action.enCours === 'valider' ? 'Validation…' : 'Valider le plan et continuer'}</span> <ArrowRight size={18} />
            </button>
          ) : (
            <span className="texte-discret">Validation du plan réservée aux ingénieurs et administrateurs.</span>
          )}
        </div>
      </div>
    </div>
  );
}