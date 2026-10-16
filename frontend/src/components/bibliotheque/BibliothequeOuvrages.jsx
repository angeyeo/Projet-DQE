import React, { useCallback, useEffect, useMemo, useState } from 'react';
import { BookOpen, Check, FileSpreadsheet, Loader2, Pencil, Plus, Search, Trash2, X } from 'lucide-react';
import { dqeService, formatFCFA } from '../../api/dqeService';
import useReferentiel from '../../hooks/useReferentiel';
import Alerte from '../ui/Alerte';
import ImportDQEExcel from './ImportDQEExcel';

const UNITES = ['u', 'ens.', 'forfait', 'm²', 'm³', 'ml', 'kg', 'jour'];
const VIDE = { lot: '', designation: '', unite: '', prixUnitaire: '', sourcePrix: '', datePrix: '' };

const versFormulaire = (o) => ({
  lot: o.lot, designation: o.designation, unite: o.unite,
  prixUnitaire: o.prix_unitaire ?? '', sourcePrix: o.source_prix || '', datePrix: o.date_prix || '',
});
const dateFr = (iso) => (iso ? new Date(`${iso}T00:00:00`).toLocaleDateString('fr-FR') : null);

// Champs d'un ouvrage, partagés par le formulaire d'ajout et l'édition en ligne.
function ChampsOuvrage({ valeur, onChange, lots, prefixe, avecLot = true }) {
  const maj = (k) => (e) => onChange({ ...valeur, [k]: e.target.value });
  return (
    <>
      {avecLot && (
        <div className="form-group">
          <label className="form-label" htmlFor={`${prefixe}-lot`}>Lot</label>
          <select id={`${prefixe}-lot`} className="form-select" value={valeur.lot} onChange={maj('lot')}>
            <option value="">— Choisir —</option>
            {lots.map((l) => <option key={l.cle} value={l.cle}>{l.libelle}</option>)}
          </select>
        </div>
      )}
      <div className="form-group champ-large">
        <label className="form-label" htmlFor={`${prefixe}-des`}>Désignation</label>
        <input id={`${prefixe}-des`} className="form-control" maxLength={200} value={valeur.designation} onChange={maj('designation')}
          placeholder="ex : Porte isoplane 0,80 × 2,10 m" />
      </div>
      <div className="form-group">
        <label className="form-label" htmlFor={`${prefixe}-unite`}>Unité</label>
        <input id={`${prefixe}-unite`} className="form-control" maxLength={20} list="unites-ouvrage" value={valeur.unite} onChange={maj('unite')} />
      </div>
      <div className="form-group">
        <label className="form-label" htmlFor={`${prefixe}-pu`}>Prix unitaire HT (FCFA)</label>
        <input id={`${prefixe}-pu`} type="number" min="0" step="1" className="form-control" value={valeur.prixUnitaire}
          onChange={maj('prixUnitaire')} placeholder="facultatif" />
      </div>
      <div className="form-group">
        <label className="form-label" htmlFor={`${prefixe}-src`}>Origine du prix</label>
        <input id={`${prefixe}-src`} className="form-control" maxLength={200} value={valeur.sourcePrix} onChange={maj('sourcePrix')}
          placeholder="ex : DQE de l'ingénieur, devis fournisseur" />
      </div>
      <div className="form-group">
        <label className="form-label" htmlFor={`${prefixe}-date`}>Date du prix</label>
        <input id={`${prefixe}-date`} type="date" className="form-control" value={valeur.datePrix} onChange={maj('datePrix')} />
      </div>
    </>
  );
}

// Bibliothèque d'ouvrages du cabinet : désignation, unité et prix par lot,
// réutilisables dans tous les projets. Le logiciel n'en fournit aucun :
// chaque ouvrage est saisi par le cabinet, avec l'origine de son prix.
export default function BibliothequeOuvrages({ peutModifier }) {
  const { data: ref } = useReferentiel();
  const lots = ref?.lots || [];
  const [ouvrages, setOuvrages] = useState(null);
  const [erreur, setErreur] = useState(null);
  const [nouveau, setNouveau] = useState(VIDE);
  const [etat, setEtat] = useState({ enCours: null, erreur: null, info: null });
  const [filtre, setFiltre] = useState({ lot: '', q: '' });
  const [edition, setEdition] = useState(null);       // {id, valeur}
  const [aSupprimer, setASupprimer] = useState(null);
  const [importOuvert, setImportOuvert] = useState(false);

  const charger = useCallback(async () => {
    try {
      setOuvrages(await dqeService.listerOuvrages());
      setErreur(null);
    } catch (err) {
      // 404 sur la liste : le serveur ne connaît pas encore cette adresse,
      // il tourne avec un code antérieur à la bibliothèque d'ouvrages.
      setErreur(err.status === 404
        ? "Le serveur ne connaît pas la bibliothèque d'ouvrages : il fonctionne avec une version antérieure du code. "
          + 'Vérifiez que la mise à jour a bien été copiée (fichier api/urls.py), puis redémarrez le serveur Django.'
        : `Bibliothèque indisponible : ${err.message}`);
    }
  }, []);
  useEffect(() => { charger(); }, [charger]);

  const executer = async (cle, action, info) => {
    setEtat({ enCours: cle, erreur: null, info: null });
    try {
      await action();
      await charger();
      setEtat({ enCours: null, erreur: null, info });
      return true;
    } catch (err) {
      setEtat({ enCours: null, erreur: err.message, info: null });
      return false;
    }
  };

  const incomplet = (o) => !o.lot || !o.designation.trim() || !o.unite.trim() || (o.prixUnitaire !== '' && Number(o.prixUnitaire) < 0);

  const ajouter = async (e) => {
    e.preventDefault();
    if (incomplet(nouveau)) return;
    const ok = await executer('ajout', () => dqeService.creerOuvrage(nouveau), `« ${nouveau.designation.trim()} » ajouté.`);
    if (ok) setNouveau({ ...VIDE, lot: nouveau.lot, sourcePrix: nouveau.sourcePrix, datePrix: nouveau.datePrix });
  };

  const parLot = useMemo(() => {
    const q = filtre.q.trim().toLowerCase();
    const visibles = (ouvrages || []).filter((o) => (!filtre.lot || o.lot === filtre.lot)
      && (!q || o.designation.toLowerCase().includes(q)));
    return lots.map((l) => ({ ...l, ouvrages: visibles.filter((o) => o.lot === l.cle) })).filter((l) => l.ouvrages.length);
  }, [ouvrages, filtre, lots]);

  return (
    <div className="glass-panel etape bibliotheque">
      <header className="etape-entete">
        <div>
          <p className="surtitre">Configuration du cabinet</p>
          <h2>Bibliothèque d'ouvrages</h2>
          <p className="texte-discret">
            Vos ouvrages types par lot, avec leur prix et son origine. Dans un projet, ajoutez-les en un clic aux postes
            complémentaires : seule la quantité reste à saisir. Modifier un prix ici ne change pas les projets déjà chiffrés.
          </p>
        </div>
        {ouvrages && <p className="compteur-bibliotheque tabular"><strong>{ouvrages.length}</strong> ouvrage(s)</p>}
      </header>

      {!peutModifier && <Alerte type="info">Lecture seule : un ingénieur ou l'administrateur du cabinet modifie la bibliothèque.</Alerte>}
      {erreur && <Alerte type="erreur" action={{ libelle: 'Réessayer', onClick: charger }}>{erreur}</Alerte>}
      {etat.erreur && <Alerte type="erreur">{etat.erreur}</Alerte>}
      {etat.info && <p className="texte-discret" role="status"><Check size={14} aria-hidden="true" /> {etat.info}</p>}

      <datalist id="unites-ouvrage">{UNITES.map((u) => <option key={u} value={u} />)}</datalist>

      {peutModifier && ouvrages && (
        <form className="formulaire-ouvrage" onSubmit={ajouter} aria-label="Ajouter un ouvrage">
          <div className="grille-ouvrage">
            <ChampsOuvrage valeur={nouveau} onChange={setNouveau} lots={lots} prefixe="nouv" />
          </div>
          <button type="submit" className="btn btn-primary" disabled={incomplet(nouveau) || etat.enCours === 'ajout'}>
            {etat.enCours === 'ajout' ? <Loader2 size={16} className="spin" /> : <Plus size={16} />} <span>Ajouter à la bibliothèque</span>
          </button>
        </form>
      )}

      {peutModifier && ouvrages && (importOuvert ? (
        <ImportDQEExcel lots={lots} ouvrages={ouvrages} onTermine={charger} onFermer={() => setImportOuvert(false)} />
      ) : (
        <div className="ouvrir-import">
          <button type="button" className="btn btn-secondary" onClick={() => setImportOuvert(true)}>
            <FileSpreadsheet size={16} aria-hidden="true" /> <span>Importer un DQE Excel</span>
          </button>
        </div>
      ))}

      <div className="filtres-bibliotheque">
        <select aria-label="Filtrer par lot" className="form-select" value={filtre.lot} onChange={(e) => setFiltre({ ...filtre, lot: e.target.value })}>
          <option value="">Tous les lots</option>
          {lots.map((l) => <option key={l.cle} value={l.cle}>{l.libelle}</option>)}
        </select>
        <div className="champ-recherche">
          <Search size={16} aria-hidden="true" />
          <input aria-label="Rechercher un ouvrage" className="form-control" placeholder="Rechercher une désignation"
            value={filtre.q} onChange={(e) => setFiltre({ ...filtre, q: e.target.value })} />
        </div>
      </div>

      {ouvrages === null && !erreur && <div className="etat-chargement" role="status">Chargement de la bibliothèque…</div>}
      {ouvrages && ouvrages.length === 0 && (
        <div className="etat-vide-compact">
          <BookOpen size={28} aria-hidden="true" />
          <p>Aucun ouvrage pour l'instant. Ajoutez-les ici, importez un DQE Excel déjà chiffré, ou enregistrez un poste saisi dans un projet
            (case « Enregistrer aussi dans la bibliothèque »).</p>
        </div>
      )}
      {ouvrages && ouvrages.length > 0 && parLot.length === 0 && <p className="texte-discret">Aucun ouvrage ne correspond au filtre.</p>}

      {parLot.map((lot) => (
        <section key={lot.cle} className="bloc-tableau" aria-labelledby={`lot-${lot.cle}`}>
          <h3 id={`lot-${lot.cle}`}>{lot.libelle} <span className="texte-discret">({lot.ouvrages.length})</span></h3>
          <div className="table-scroll">
            <table className="custom-table">
              <thead><tr><th>Désignation</th><th>Unité</th><th>Prix unitaire HT</th><th>Origine du prix</th><th>Utilisé</th>
                {peutModifier && <th><span className="sr-only">Actions</span></th>}</tr></thead>
              <tbody>
                {lot.ouvrages.map((o) => (edition?.id === o.id ? (
                  <tr key={o.id} className="ligne-edition">
                    <td colSpan={peutModifier ? 6 : 5}>
                      <div className="grille-ouvrage">
                        <ChampsOuvrage valeur={edition.valeur} onChange={(v) => setEdition({ ...edition, valeur: v })} lots={lots} prefixe={`ed-${o.id}`} />
                      </div>
                      <div className="actions-ligne">
                        <button type="button" className="btn btn-primary btn-compact" disabled={incomplet(edition.valeur) || !!etat.enCours}
                          onClick={async () => { if (await executer(`ed-${o.id}`, () => dqeService.modifierOuvrage(o.id, edition.valeur), 'Ouvrage modifié.')) setEdition(null); }}>
                          <Check size={14} /> <span>Enregistrer</span>
                        </button>
                        <button type="button" className="btn btn-secondary btn-compact" onClick={() => setEdition(null)}><X size={14} /> <span>Annuler</span></button>
                      </div>
                    </td>
                  </tr>
                ) : (
                  <tr key={o.id}>
                    <td><strong>{o.designation}</strong></td>
                    <td>{o.unite}</td>
                    <td className="tabular">{o.prix_unitaire != null ? formatFCFA(o.prix_unitaire) : <span className="texte-discret">à saisir par projet</span>}</td>
                    <td className="texte-discret">{[o.source_prix, dateFr(o.date_prix)].filter(Boolean).join(' · ') || 'non précisée'}</td>
                    <td className="tabular">{o.nb_postes ? `${o.nb_postes} poste(s)` : '—'}</td>
                    {peutModifier && (
                      <td className="actions-cellule">
                        {aSupprimer === o.id ? (
                          <>
                            <button type="button" className="btn btn-danger btn-compact" disabled={!!etat.enCours}
                              onClick={() => executer(`del-${o.id}`, () => dqeService.supprimerOuvrage(o.id), 'Ouvrage supprimé (les postes des projets sont conservés).').then(() => setASupprimer(null))}>
                              Confirmer
                            </button>
                            <button type="button" className="btn btn-secondary btn-compact" onClick={() => setASupprimer(null)}>Annuler</button>
                          </>
                        ) : (
                          <>
                            <button type="button" className="btn btn-secondary btn-compact" aria-label={`Modifier ${o.designation}`}
                              onClick={() => { setASupprimer(null); setEdition({ id: o.id, valeur: versFormulaire(o) }); }}>
                              <Pencil size={14} aria-hidden="true" />
                            </button>
                            <button type="button" className="btn btn-secondary btn-compact" aria-label={`Supprimer ${o.designation}`}
                              onClick={() => setASupprimer(o.id)}>
                              <Trash2 size={14} color="var(--status-critical)" aria-hidden="true" />
                            </button>
                          </>
                        )}
                      </td>
                    )}
                  </tr>
                )))}
              </tbody>
            </table>
          </div>
        </section>
      ))}
    </div>
  );
}
