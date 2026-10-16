import React, { useMemo, useState } from 'react';
import { ChevronDown, Lock, Unlock } from 'lucide-react';
import Alerte from '../ui/Alerte';

// Saisie manuelle quand le moteur n'a produit AUCUN résultat : l'ingénieur
// fournit lui-même les dimensions qu'il valide (donnée SAISIE, tracée
// comme telle dans le résultat validé). Clés = celles lues par le DQE.
export const CHAMPS_MANUELS = {
  poteau: [['cote_cm', 'Côté (cm)']],
  poutre: [['largeur_cm', 'Largeur (cm)'], ['hauteur_cm', 'Hauteur (cm)']],
  longrine: [['largeur_cm', 'Largeur (cm)'], ['hauteur_cm', 'Hauteur (cm)']],
  chainage: [['largeur_cm', 'Largeur (cm)'], ['hauteur_cm', 'Hauteur (cm)']],
  semelle_filante: [['largeur_cm', 'Largeur (cm)'], ['hauteur_cm', 'Hauteur (cm)']],
  semelle: [['cote_cm', 'Côté (cm)'], ['hauteur_cm', 'Hauteur (cm)']],
  dalle: [['epaisseur_cm', 'Épaisseur (cm)']],
};
const CHAMP_ACIER = ['poids_acier_total_kg', 'Acier total (kg) — facultatif'];

// Renvoie {resultat} ou {erreur}. Aucun champ requis ne peut manquer.
export function construireResultatManuel(type, valeurs = {}) {
  const champs = CHAMPS_MANUELS[type];
  if (!champs) return { erreur: `Saisie manuelle non prévue pour le type « ${type} ».` };
  const resultat = { source: 'saisie_manuelle_ingenieur' };
  for (const [cle, libelle] of champs) {
    const v = Number(valeurs[cle]);
    if (valeurs[cle] === undefined || valeurs[cle] === '' || !Number.isFinite(v) || v <= 0) {
      return { erreur: `${libelle} : valeur strictement positive requise.` };
    }
    resultat[cle] = v;
  }
  if (valeurs[CHAMP_ACIER[0]] !== undefined && valeurs[CHAMP_ACIER[0]] !== '') {
    const a = Number(valeurs[CHAMP_ACIER[0]]);
    if (!Number.isFinite(a) || a < 0) return { erreur: 'Acier total : valeur positive attendue.' };
    resultat[CHAMP_ACIER[0]] = a;
  }
  return { resultat };
}

const LIBELLES_CLES = {
  cote_cm: 'Côté (cm)', largeur_cm: 'Largeur (cm)', hauteur_cm: 'Hauteur (cm)', epaisseur_cm: 'Épaisseur (cm)',
  grand_cote_cm: 'Grand côté (cm)', petit_cote_cm: 'Petit côté (cm)', poids_acier_total_kg: 'Acier total (kg)',
  section_acier_cm2: 'Section d’acier (cm²)', epaisseur_theorique_cm: 'Épaisseur théorique (cm)',
  portant_deux_sens: 'Porte dans deux sens', alpha: 'α = Lx/Ly', source: 'Source',
};

const valeurLisible = (v) => {
  if (v === true) return 'oui';
  if (v === false) return 'non';
  if (v && typeof v === 'object') {
    if (v.nombre_barres && v.diametre_mm) return `${v.nombre_barres} HA ${v.diametre_mm}`;
    return Object.entries(v).map(([k, x]) => `${k} : ${valeurLisible(x)}`).join(' · ');
  }
  return String(v);
};

const CLES_TECHNIQUES = new Set(['trace', 'hypotheses_calcul']);
const ORIGINES_G = { forfait: 'HYPOTHÈSE (forfait du moteur)', saisie: 'SAISIE', couches: 'CALCULÉE (composition)' };

// « Voir le calcul » : étapes produites PAR LE MOTEUR (formule, valeurs
// numériques, résultat, unité) puis résultat brut. Rien n'est recalculé ici.
function DetailCalcul({ item }) {
  const res = item.resultat || {};
  const trace = Array.isArray(res.trace) ? res.trace : [];
  const h = res.hypotheses_calcul;
  const entrees = Object.entries(res).filter(([k]) => !CLES_TECHNIQUES.has(k));
  return (
    <div className="detail-calcul">
      {trace.length > 0 ? (
        <ol className="trace-calcul">
          {trace.map((e, i) => (
            <li key={i}>
              <span className="trace-etape">{e.etape}</span>
              <code className="trace-formule">{e.formule}</code>
              {e.calcul && <span className="trace-calcul-valeurs tabular">{e.calcul}</span>}
              <strong className="tabular">= {valeurLisible(e.resultat)} {e.unite !== '—' ? e.unite : ''}</strong>
            </li>
          ))}
        </ol>
      ) : (
        <p className="texte-discret">
          Étapes de calcul non disponibles pour ce résultat (calculé avant la traçabilité ou saisi manuellement) :
          régénérez la trame pour les obtenir.
        </p>
      )}
      {h && (
        <p className="hypotheses-element texte-discret">
          G = {h.g_plancher_kn_m2} kN/m² — {ORIGINES_G[h.origine_g] || h.origine_g} · Q = {h.q_kn_m2} kN/m² ·
          σsol = {h.contrainte_sol_effective_kn_m2} kN/m²{h.contrainte_sol_kn_m2 == null ? ' (HYPOTHÈSE)' : ''} ·
          semelles {h.methode_semelles} · poids propre {h.inclure_poids_propre_ossature ? 'ajouté' : 'non ajouté'}
        </p>
      )}
      <details>
        <summary className="texte-discret">Résultat brut du moteur</summary>
        <dl className="grille-donnees">
          {item.charge && <><dt>Charge transmise</dt><dd className="tabular">{item.charge}</dd></>}
          {item.chargeLineaire && <><dt>Charge linéaire</dt><dd className="tabular">{item.chargeLineaire}</dd></>}
          {item.portee && <><dt>Portée</dt><dd className="tabular">{item.portee}</dd></>}
          {entrees.map(([k, v]) => (
            <React.Fragment key={k}><dt>{LIBELLES_CLES[k] || k}</dt><dd className="tabular">{valeurLisible(v)}</dd></React.Fragment>
          ))}
        </dl>
      </details>
    </div>
  );
}

const FILTRES = [['tous', 'Tous'], ['attente', 'À valider'], ['valides', 'Validés']];

export default function ListeElements({ elements, onBasculerVerrou, onBasculerTout, validation, onApresChangement }) {
  const [filtre, setFiltre] = useState('attente');
  const [ouvert, setOuvert] = useState(null);
  const [manuels, setManuels] = useState({});
  const [erreurLocale, setErreurLocale] = useState(null);

  const valides = elements.filter((e) => e.locked).length;
  const tousValides = elements.length > 0 && valides === elements.length;
  const visibles = useMemo(() => elements.filter((e) =>
    filtre === 'tous' || (filtre === 'valides' ? e.locked : !e.locked)), [elements, filtre]);

  const resultatManuel = (item) => {
    if (!item.calculIndisponible || item.locked) return { resultat: undefined };
    return construireResultatManuel(item.type, manuels[item.elementId]);
  };

  const basculer = async (item) => {
    setErreurLocale(null);
    const { resultat, erreur } = resultatManuel(item);
    if (erreur) {
      setOuvert(item.elementId);
      setErreurLocale(`${item.name} : ${erreur}`);
      return;
    }
    if (await onBasculerVerrou(item, resultat)) onApresChangement?.();
  };

  const basculerTout = async () => {
    setErreurLocale(null);
    const res = {};
    if (!tousValides) {
      elements.filter((e) => e.calculIndisponible && !e.locked).forEach((e) => {
        const { resultat } = construireResultatManuel(e.type, manuels[e.elementId]);
        if (resultat) res[e.elementId] = resultat;
      });
    }
    await onBasculerTout(!tousValides, res);
    onApresChangement?.();
  };

  const saisir = (id, cle, v) => setManuels((m) => ({ ...m, [id]: { ...(m[id] || {}), [cle]: v } }));

  return (
    <section aria-labelledby="titre-elements">
      <div className="bloc-entete">
        <div>
          <h3 id="titre-elements">Éléments structurels</h3>
          <p className="texte-discret">{valides}/{elements.length} validés par un ingénieur.</p>
        </div>
        {elements.length > 0 && (
          <button type="button" className={`btn ${tousValides ? 'btn-secondary' : 'btn-success'}`}
            disabled={validation.enCoursId === 'tous'} onClick={basculerTout}>
            {tousValides ? <Unlock size={16} /> : <Lock size={16} />}
            <span>{validation.enCoursId === 'tous' ? 'Traitement…' : tousValides ? 'Tout déverrouiller' : 'Tout valider'}</span>
          </button>
        )}
      </div>

      {(validation.erreur || erreurLocale) && (
        <Alerte type="erreur" titre="Validation incomplète">{erreurLocale || validation.erreur}</Alerte>
      )}

      <div className="filtres-statut" role="group" aria-label="Filtrer les éléments">
        {FILTRES.map(([k, l]) => (
          <button key={k} type="button" className={`chip ${filtre === k ? 'chip-actif' : ''}`} aria-pressed={filtre === k}
            onClick={() => setFiltre(k)}>
            {l} <span className="tabular">({k === 'tous' ? elements.length : k === 'valides' ? valides : elements.length - valides})</span>
          </button>
        ))}
      </div>

      {elements.length === 0 && <p className="texte-discret">Aucun élément : revenez à l'étape Paramètres pour générer la trame.</p>}
      {elements.length > 0 && visibles.length === 0 && <p className="texte-discret">Aucun élément dans ce filtre.</p>}

      <ul className="liste-elements">
        {visibles.map((item) => {
          const deplie = ouvert === item.elementId;
          return (
            <li key={item.elementId} className={`ligne-element ${item.locked ? 'est-valide' : ''}`}>
              <div className="ligne-element-resume">
                <button type="button" className="ligne-element-bascule" aria-expanded={deplie}
                  onClick={() => setOuvert(deplie ? null : item.elementId)}>
                  <ChevronDown size={16} className={deplie ? 'rotation-180' : ''} aria-hidden="true" />
                  <strong>{item.name}</strong>
                  <span className="texte-discret">{item.categorie}</span>
                </button>
                <span className="tabular ligne-element-section">
                  {item.section || <span className="texte-discret">{item.calculIndisponible ? 'sans résultat — saisie requise' : '—'}</span>}
                  {item.armatures && <span className="texte-discret"> · {item.armatures}</span>}
                </span>
                {item.hypotheseSol && <span className="type-donnee type-hypothèse" title="Contrainte du sol par défaut du moteur">sol par défaut</span>}
                {item.statut === 'modifie' && <span className="statut-pastille ton-info">déverrouillé</span>}
                <button type="button" className={`btn btn-compact ${item.locked ? 'btn-secondary' : 'btn-success'}`}
                  disabled={validation.enCoursId === item.elementId || validation.enCoursId === 'tous'}
                  onClick={() => basculer(item)}>
                  {item.locked ? <Unlock size={14} /> : <Lock size={14} />}
                  <span>{validation.enCoursId === item.elementId ? '…' : item.locked ? 'Déverrouiller' : 'Valider'}</span>
                </button>
              </div>
              {deplie && (
                <div className="ligne-element-detail">
                  <h4 className="sous-titre">Voir le calcul</h4>
                  <DetailCalcul item={item} />
                  {item.calculIndisponible && !item.locked && CHAMPS_MANUELS[item.type] && (
                    <fieldset className="saisie-manuelle">
                      <legend>Saisie manuelle de l'ingénieur (donnée SAISIE)</legend>
                      {[...CHAMPS_MANUELS[item.type], CHAMP_ACIER].map(([cle, libelle]) => (
                        <div className="form-group" key={cle}>
                          <label className="form-label" htmlFor={`m-${item.elementId}-${cle}`}>{libelle}</label>
                          <input id={`m-${item.elementId}-${cle}`} type="number" min="0" step="0.1" className="form-control"
                            value={manuels[item.elementId]?.[cle] ?? ''} onChange={(e) => saisir(item.elementId, cle, e.target.value)} />
                        </div>
                      ))}
                    </fieldset>
                  )}
                </div>
              )}
            </li>
          );
        })}
      </ul>
    </section>
  );
}
