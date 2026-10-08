import React, { useState } from 'react';
import { AlertCircle, ArrowLeft, ArrowRight, Loader2, Sparkles } from 'lucide-react';
import { dqeService } from '../api/dqeService';
import Alerte from './ui/Alerte';

const ND = <span className="texte-discret" title="Aucun résultat de calcul pour cet élément">ND</span>;

const SOURCES_IA = { GEMINI: 'Gemini', MOCK: 'SIMULATION (non IA)', FALLBACK_LOCAL: 'Explication locale (sans IA)' };

// Ligne d'élément + explication IA à la demande (l'IA commente un résultat
// du moteur ; elle ne le produit ni ne le modifie).
function LigneElement({ item, colonnes, nbColonnes, explication, onExpliquer }) {
  return (
    <>
      <tr>
        {colonnes}
        <td>
          <button type="button" className="btn btn-ia btn-compact" disabled={explication?.chargement || item.calculIndisponible}
            onClick={() => onExpliquer(item)}
            title={item.calculIndisponible ? 'Aucun calcul à expliquer' : "Demander une explication à l'IA"}>
            {explication?.chargement ? <Loader2 size={14} className="spin" /> : <Sparkles size={14} />}
            <span className="sr-only">Expliquer {item.name} avec l'IA</span>
          </button>
        </td>
      </tr>
      {explication && !explication.chargement && (
        <tr className="ligne-explication">
          <td colSpan={nbColonnes}>
            {explication.erreur ? (
              <span className="texte-erreur"><AlertCircle size={14} aria-hidden="true" /> {explication.erreur}</span>
            ) : (
              <>
                <span className="type-donnee">RECOMMANDATION IA · {SOURCES_IA[explication.source] || explication.source}</span>
                <p>{explication.texte}</p>
              </>
            )}
          </td>
        </tr>
      )}
    </>
  );
}

function Tableau({ titre, elements, entetes, cellules, explications, onExpliquer }) {
  if (!elements.length) return null;
  return (
    <section className="bloc-tableau">
      <h3>{titre} <span className="texte-discret">({elements.length})</span></h3>
      <div className="table-scroll">
        <table className="custom-table">
          <thead><tr>{entetes.map((e) => <th key={e}>{e}</th>)}<th><span className="sr-only">IA</span></th></tr></thead>
          <tbody>
            {elements.map((item) => (
              <LigneElement key={item.elementId} item={item} nbColonnes={entetes.length + 1}
                explication={explications[item.elementId]} onExpliquer={onExpliquer}
                colonnes={cellules(item).map((c, i) => <td key={i} className={i ? 'tabular' : ''}>{c ?? ND}</td>)} />
            ))}
          </tbody>
        </table>
      </div>
    </section>
  );
}

export default function Step2_Calculs({ sections, projet, hypotheses = [], avertissements = [], alertes = [], onBack, onNext }) {
  const { poteaux = [], poutres = [], semelles = [], autres = [] } = sections || {};
  const total = poteaux.length + poutres.length + semelles.length + autres.length;
  const sansResultat = [...poteaux, ...poutres, ...semelles, ...autres].filter((e) => e.calculIndisponible).length;
  const [explications, setExplications] = useState({});

  const expliquer = async (item) => {
    setExplications((p) => ({ ...p, [item.elementId]: { chargement: true } }));
    try {
      const res = await dqeService.expliquerElementIA(item.elementId);
      setExplications((p) => ({ ...p, [item.elementId]: { texte: res.explication, source: res.source } }));
    } catch (err) {
      setExplications((p) => ({ ...p, [item.elementId]: { erreur: err.message } }));
    }
  };

  const communs = { explications, onExpliquer: expliquer };

  return (
    <div className="glass-panel etape">
      <header className="etape-entete">
        <div>
          <p className="surtitre">Étape 2</p>
          <h2>Descente de charges & sections proposées</h2>
          <p className="texte-discret">
            {projet?.nom} — {total} élément(s) générés par le moteur (BAEL 91). « ND » : aucun résultat de calcul.
          </p>
        </div>
      </header>

      {hypotheses.length > 0 && <Alerte type="info" titre="Hypothèses retenues par le moteur" liste={hypotheses} />}
      {avertissements.length > 0 && <Alerte type="attention" titre="Avertissements" liste={avertissements} />}
      {alertes.length > 0 && (
        <Alerte type="attention" titre={`${alertes.length} valeur(s) inhabituelle(s)`} liste={alertes.map((a) => a.message)}>
          Contrôles de plausibilité : rien n'a été modifié, à vérifier par l'ingénieur.
        </Alerte>
      )}
      {sansResultat > 0 && (
        <Alerte type="attention">
          {sansResultat} élément(s) sans résultat de calcul : ils devront être saisis manuellement par l'ingénieur à l'étape Validation.
        </Alerte>
      )}

      {total === 0 && <p className="texte-discret etat-vide-compact">Aucun élément : enregistrez les paramètres à l'étape 1 pour générer la trame.</p>}

      <Tableau titre="Poteaux" {...communs} elements={poteaux}
        entetes={['Repère', 'Effort normal', 'Section', 'Armatures']}
        cellules={(i) => [<strong>{i.name}</strong>, i.charge, i.section, i.armatures]} />
      <Tableau titre="Poutres" {...communs} elements={poutres}
        entetes={['Repère', 'Portée', 'Charge linéaire', 'Section', 'Armatures']}
        cellules={(i) => [<strong>{i.name}</strong>, i.portee, i.chargeLineaire, i.section, i.armatures]} />
      <Tableau titre="Semelles" {...communs} elements={semelles}
        entetes={['Repère', 'Effort', 'Contrainte sol', 'Dimensions', 'Hauteur']}
        cellules={(i) => [<strong>{i.name}</strong>, i.charge,
          i.contrainteSol && <>{i.contrainteSol}{i.hypotheseSol && <span className="type-donnee type-hypothèse"> hypothèse</span>}</>,
          i.section, i.hauteur]} />
      <Tableau titre="Autres ouvrages (longrines, chaînages, semelles filantes)" {...communs} elements={autres}
        entetes={['Repère', 'Type', 'Longueur / portée', 'Section']}
        cellules={(i) => [<strong>{i.name}</strong>, i.categorie, i.portee || (i.longueur != null ? `${i.longueur} m` : null), i.section]} />

      <div className="navigation-etapes">
        <button type="button" className="btn btn-secondary" onClick={onBack}><ArrowLeft size={18} /> <span>Paramètres</span></button>
        <button type="button" className="btn btn-primary" onClick={onNext}><span>Dalles</span> <ArrowRight size={18} /></button>
      </div>
    </div>
  );
}