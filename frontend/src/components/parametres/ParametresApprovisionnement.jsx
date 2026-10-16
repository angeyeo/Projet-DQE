import React from 'react';
import { Truck } from 'lucide-react';

const nombre = (v) => (v == null ? '' : String(v).replace('.', ','));

// Paramètres de la fiche d'approvisionnement : dosages, pertes, camions, et
// prix des matériaux. Champ vide = valeur de référence de l'ingénieur (si
// elle existe), affichée en clair ; le CALCUL est fait par le serveur.
export default function ParametresApprovisionnement({ referentiel, params, onParam, prix, onPrix, origines, onPreremplir, estAdmin }) {
  const appro = referentiel?.approvisionnement;
  if (!appro) return null;
  const refPrix = appro.prix_reference?.valeurs || {};
  const prixVides = Object.keys(refPrix).filter((cle) => prix[cle] === undefined || prix[cle] === '' || prix[cle] === null);

  return (
    <section className="parametres-appro" aria-labelledby="titre-appro">
      <div className="titre-section-icone">
        <span className="pastille-icone"><Truck size={20} aria-hidden="true" /></span>
        <h2 id="titre-appro">Fiche d'approvisionnement</h2>
      </div>
      <p className="texte-discret">
        Dosages et pertes servent à convertir les quantités du DQE en matériaux à acheter. Laissé vide, un champ prend
        la valeur de référence indiquée en dessous.
      </p>

      <div className="grid-3">
        {appro.parametres.map((p) => (
          <div className="form-group" key={p.cle}>
            <label className="form-label" htmlFor={`appro-${p.cle}`}>
              {p.libelle} <span className="texte-discret">({p.unite})</span>
            </label>
            <input id={`appro-${p.cle}`} type="number" step="any" min={p.min} max={p.max} className="form-control"
              disabled={!estAdmin} value={params[p.cle] ?? ''} onChange={(e) => onParam(p.cle, e.target.value)}
              placeholder={p.valeur_reference != null ? `référence : ${nombre(p.valeur_reference)}` : 'non renseigné'} />
            <small className="aide-champ">
              {params[p.cle] !== undefined && params[p.cle] !== ''
                ? 'Valeur du cabinet'
                : p.valeur_reference != null ? `Référence : ${p.source}` : 'Non renseigné : non calculé sur la fiche'}
            </small>
          </div>
        ))}
      </div>

      <h3 className="sous-titre">Prix des matériaux</h3>
      {estAdmin && prixVides.length > 0 && (
        <p className="texte-discret">
          <button type="button" className="btn btn-secondary btn-compact" onClick={() => onPreremplir(refPrix)}>
            Pré-remplir {prixVides.length} prix avec ceux de l'ingénieur
          </button>{' '}
          {appro.prix_reference.source}.
        </p>
      )}
      <div className="grid-3">
        {appro.cles_prix.map(({ cle, libelle }) => (
          <div className="form-group" key={cle}>
            <label className="form-label" htmlFor={`prix-${cle}`}>{libelle}</label>
            <input id={`prix-${cle}`} type="number" min="0" step="1" className="form-control" disabled={!estAdmin}
              value={prix[cle] ?? ''} onChange={onPrix(cle)} placeholder="Non renseigné : montant non calculé" />
            {origines[cle] === 'reference' && <small className="aide-champ">Pré-rempli — non enregistré</small>}
          </div>
        ))}
      </div>
    </section>
  );
}
