import React, { useState } from 'react';
import { ArrowLeft, ArrowRight, Calculator, Grid3x3, Plus, Trash2 } from 'lucide-react';
import { dqeService } from '../api/dqeService';
import Alerte from './ui/Alerte';

// Dalles du projet. Le frontend ne fait AUCUN calcul : il envoie Lx / Ly
// au serveur, qui valide (Lx ≤ Ly), déduit la surface, puis le moteur
// détermine le sens de portée (α = Lx/Ly) et l'épaisseur.
const VIDE = { identifiant: '', lx: '', ly: '' };

export default function StepDalles({ projetId, dalles = [], onChange, onBack, onNext }) {
  const [saisie, setSaisie] = useState(VIDE);
  const [etat, setEtat] = useState({ enCours: null, erreur: null });

  const executer = async (cle, action) => {
    setEtat({ enCours: cle, erreur: null });
    try {
      await action();
      await onChange();
      setEtat({ enCours: null, erreur: null });
      return true;
    } catch (err) {
      await onChange();
      setEtat({ enCours: null, erreur: err.message });
      return false;
    }
  };

  const ajouter = async (e) => {
    e.preventDefault();
    const ok = await executer('ajout', async () => {
      const el = await dqeService.creerElement({
        projet: projetId,
        type_element: 'dalle',
        position: 'superstructure',
        identifiant: saisie.identifiant.trim(),
        portee: saisie.lx === '' ? null : Number(saisie.lx),
        longueur_m: saisie.ly === '' ? null : Number(saisie.ly),
      });
      await dqeService.calculerElement(el.id);
    });
    if (ok) setSaisie(VIDE);
  };

  const incomplet = !saisie.identifiant.trim() || saisie.lx === '' || saisie.ly === '';

  return (
    <div className="glass-panel">
      <header className="etape-entete">
        <div>
          <p className="surtitre">Étape 2 bis</p>
          <h2>Dalles & planchers</h2>
          <p className="texte-discret">
            Pré-dimensionnement BAEL 91 : α = Lx/Ly ≥ 0,4 → dalle portant dans deux sens, sinon un sens.
            L'épaisseur est calculée par le moteur côté serveur.
          </p>
          <p className="texte-discret">
            Mesurez Lx et Ly entre axes des poteaux. Au DQE, l'emprise des poutres est déduite du béton de la dalle.
          </p>
        </div>
        <Grid3x3 size={28} color="var(--accent)" aria-hidden="true" />
      </header>

      {etat.erreur && <Alerte type="erreur" titre="Opération impossible">{etat.erreur}</Alerte>}

      <form className="formulaire-ligne" onSubmit={ajouter}>
        <div className="form-group">
          <label className="form-label" htmlFor="dalle-id">Repère</label>
          <input id="dalle-id" className="form-control" placeholder="ex : D1" value={saisie.identifiant}
            onChange={(e) => setSaisie({ ...saisie, identifiant: e.target.value })} />
        </div>
        <div className="form-group">
          <label className="form-label" htmlFor="dalle-lx">Petite portée Lx (m)</label>
          <input id="dalle-lx" type="number" min="0" step="0.01" className="form-control" value={saisie.lx}
            onChange={(e) => setSaisie({ ...saisie, lx: e.target.value })} />
        </div>
        <div className="form-group">
          <label className="form-label" htmlFor="dalle-ly">Grande portée Ly (m)</label>
          <input id="dalle-ly" type="number" min="0" step="0.01" className="form-control" value={saisie.ly}
            onChange={(e) => setSaisie({ ...saisie, ly: e.target.value })} />
        </div>
        <button type="submit" className="btn btn-primary" disabled={incomplet || etat.enCours === 'ajout'}>
          <Plus size={16} aria-hidden="true" />
          <span>{etat.enCours === 'ajout' ? 'Calcul…' : 'Ajouter et calculer'}</span>
        </button>
      </form>

      {dalles.length === 0 ? (
        <p className="texte-discret etat-vide-compact">
          Aucune dalle dans ce projet. Les dalles sont optionnelles : sans dalle, le DQE ne comporte aucun poste de plancher.
        </p>
      ) : (
        <div className="table-scroll">
          <table className="custom-table">
            <thead>
              <tr>
                <th>Repère</th><th>Lx × Ly</th><th>Surface</th><th>α</th><th>Sens</th><th>Épaisseur</th><th>Statut</th><th><span className="sr-only">Actions</span></th>
              </tr>
            </thead>
            <tbody>
              {dalles.map((d) => {
                const r = d.resultat || {};
                return (
                  <tr key={d.elementId}>
                    <td><strong>{d.name}</strong></td>
                    <td className="tabular">{d.portee || '—'} × {d.longueur != null ? `${d.longueur} m` : '—'}</td>
                    <td className="tabular">{d.surface != null ? `${d.surface} m²` : '—'}</td>
                    <td className="tabular">{r.alpha ?? '—'}</td>
                    <td>
                      {d.calculIndisponible ? '—' : r.portant_deux_sens ? 'Deux sens' : 'Un sens'}
                      {r.hypothese_sens_portee && <div className="texte-discret">{r.hypothese_sens_portee}</div>}
                    </td>
                    <td className="tabular">
                      {r.epaisseur_cm != null ? (
                        <span title={`Théorique ${r.epaisseur_theorique_cm} cm, minimum constructif appliqué`}>{r.epaisseur_cm} cm</span>
                      ) : <span className="texte-discret">non calculée</span>}
                    </td>
                    <td><span className={d.locked ? 'badge badge-locked' : 'badge badge-unlocked'}>{d.locked ? 'Validée' : 'À valider'}</span></td>
                    <td className="cellule-actions">
                      {!d.locked && (
                        <>
                          <button type="button" className="btn btn-secondary btn-compact" disabled={!!etat.enCours}
                            onClick={() => executer(`calc-${d.elementId}`, () => dqeService.calculerElement(d.elementId))}
                            aria-label={`Recalculer ${d.name}`}>
                            <Calculator size={14} aria-hidden="true" />
                          </button>
                          <button type="button" className="btn btn-secondary btn-compact" disabled={!!etat.enCours}
                            onClick={() => executer(`del-${d.elementId}`, () => dqeService.supprimerElement(d.elementId))}
                            aria-label={`Supprimer ${d.name}`}>
                            <Trash2 size={14} color="var(--status-critical)" aria-hidden="true" />
                          </button>
                        </>
                      )}
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      )}

      <div className="navigation-etapes">
        <button type="button" className="btn btn-secondary" onClick={onBack}><ArrowLeft size={18} /> <span>Calculs</span></button>
        <button type="button" className="btn btn-primary" onClick={onNext}><span>Validation ingénieur</span> <ArrowRight size={18} /></button>
      </div>
    </div>
  );
}