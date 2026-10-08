import React, { useMemo, useState } from 'react';
import { FolderOpen, Plus, Search, Trash2, BarChart3, RefreshCw } from 'lucide-react';
import { dqeService } from '../api/dqeService';
import useRessource from '../hooks/useRessource';
import Alerte from './ui/Alerte';
import { dateCourte } from './charts/palette';

// Statut d'un projet : calculé côté serveur (ProjetResumeSerializer.statut).
export const STATUTS = {
  brouillon: { libelle: 'Brouillon', vue: 'step1' },
  en_etude: { libelle: 'En étude', vue: 'step3' },
  valide: { libelle: 'Validé', vue: 'step4' },
  dqe_genere: { libelle: 'DQE généré', vue: 'analyse' },
};

export default function MesProjetsView({ projetCourantId, onOuvrir, onNouveau, onProjetSupprime }) {
  const { data, erreur, chargement, recharger } = useRessource(() => dqeService.listerProjets(), []);
  const [recherche, setRecherche] = useState('');
  const [filtre, setFiltre] = useState('tous');
  const [aSupprimer, setASupprimer] = useState(null);
  const [suppression, setSuppression] = useState({ enCours: false, erreur: null });

  const projets = useMemo(() => {
    const liste = Array.isArray(data) ? data : data?.results || [];
    const q = recherche.trim().toLowerCase();
    return liste
      .filter((p) => filtre === 'tous' || p.statut === filtre)
      .filter((p) => !q || `${p.nom} ${p.numero_devis || ''} ${p.usage_batiment || ''}`.toLowerCase().includes(q));
  }, [data, recherche, filtre]);

  const supprimer = async (p) => {
    setSuppression({ enCours: true, erreur: null });
    try {
      await dqeService.supprimerProjet(p.id);
      setASupprimer(null);
      onProjetSupprime(p.id);
      await recharger();
      setSuppression({ enCours: false, erreur: null });
    } catch (err) {
      setSuppression({ enCours: false, erreur: `Suppression de « ${p.nom} » impossible : ${err.message}` });
    }
  };

  return (
    <div className="dashboard">
      <header className="dashboard-entete">
        <div>
          <p className="surtitre">Cabinet</p>
          <h2>Mes projets</h2>
        </div>
        <div className="actions-ligne">
          <button type="button" className="btn btn-secondary" onClick={recharger} disabled={chargement} aria-label="Actualiser la liste">
            <RefreshCw size={16} className={chargement ? 'spin' : ''} aria-hidden="true" />
          </button>
          <button type="button" className="btn btn-primary" onClick={onNouveau}>
            <Plus size={16} aria-hidden="true" /> <span>Nouveau projet</span>
          </button>
        </div>
      </header>

      <div className="barre-filtres">
        <label className="champ-recherche">
          <Search size={16} aria-hidden="true" />
          <span className="sr-only">Rechercher un projet</span>
          <input type="search" className="form-control" placeholder="Nom, n° de devis, usage…"
            value={recherche} onChange={(e) => setRecherche(e.target.value)} />
        </label>
        <div className="filtres-statut" role="group" aria-label="Filtrer par statut">
          {[['tous', 'Tous'], ...Object.entries(STATUTS).map(([k, v]) => [k, v.libelle])].map(([k, l]) => (
            <button key={k} type="button" className={`chip ${filtre === k ? 'chip-actif' : ''}`}
              aria-pressed={filtre === k} onClick={() => setFiltre(k)}>{l}</button>
          ))}
        </div>
      </div>

      {erreur && <Alerte type="erreur" action={{ libelle: 'Réessayer', onClick: recharger }}>{erreur}</Alerte>}
      {suppression.erreur && <Alerte type="erreur">{suppression.erreur}</Alerte>}
      {chargement && !data && <div className="glass-panel etat-chargement" role="status">Chargement des projets…</div>}

      {data && projets.length === 0 && (
        <div className="glass-panel etat-vide">
          <FolderOpen size={36} color="var(--ink-300)" aria-hidden="true" />
          <h2>{recherche || filtre !== 'tous' ? 'Aucun projet ne correspond' : 'Aucun projet'}</h2>
          <p>{recherche || filtre !== 'tous' ? 'Modifiez la recherche ou le filtre.' : 'Créez votre premier projet pour commencer.'}</p>
        </div>
      )}

      {projets.length > 0 && (
        <ul className="liste-projets">
          {projets.map((p) => (
            <li key={p.id} className={`carte-projet ${p.id === projetCourantId ? 'carte-projet-ouvert' : ''}`}>
              <div className="carte-projet-corps">
                <div className="carte-projet-titre">
                  <button type="button" className="lien lien-fort" onClick={() => onOuvrir(p.id, STATUTS[p.statut]?.vue || 'step1')}>
                    {p.nom}
                  </button>
                  <span className={`statut-pastille statut-${p.statut}`}>{STATUTS[p.statut]?.libelle || p.statut}</span>
                  {p.id === projetCourantId && <span className="texte-discret">(ouvert)</span>}
                </div>
                <div className="carte-projet-meta texte-discret">
                  {p.usage_batiment || 'usage non renseigné'} · {p.nb_niveaux ?? '—'} niveau(x)
                  {p.numero_devis && ` · devis ${p.numero_devis}`} · {p.nb_elements_valides}/{p.nb_elements} éléments validés
                  {' · '}modifié le {dateCourte(p.date_modification)}{p.cree_par_nom && ` par ${p.cree_par_nom}`}
                </div>
                {p.nb_elements > 0 && (
                  <div className="mini-progress" aria-hidden="true">
                    <span style={{ width: `${(p.nb_elements_valides / p.nb_elements) * 100}%` }} />
                  </div>
                )}
              </div>
              <div className="carte-projet-actions">
                <button type="button" className="btn btn-secondary btn-compact" onClick={() => onOuvrir(p.id, 'analyse')}>
                  <BarChart3 size={15} aria-hidden="true" /> <span>Analyse</span>
                </button>
                {aSupprimer === p.id ? (
                  <span className="confirmation">
                    Supprimer définitivement ?
                    <button type="button" className="btn btn-danger btn-compact" disabled={suppression.enCours} onClick={() => supprimer(p)}>
                      {suppression.enCours ? 'Suppression…' : 'Oui, supprimer'}
                    </button>
                    <button type="button" className="btn btn-secondary btn-compact" onClick={() => setASupprimer(null)}>Annuler</button>
                  </span>
                ) : (
                  <button type="button" className="btn btn-secondary btn-compact" onClick={() => setASupprimer(p.id)}
                    aria-label={`Supprimer le projet ${p.nom}`}>
                    <Trash2 size={15} color="var(--status-critical)" aria-hidden="true" />
                  </button>
                )}
              </div>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}