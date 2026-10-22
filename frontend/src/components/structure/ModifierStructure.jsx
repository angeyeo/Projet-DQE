import React, { useEffect, useMemo, useState } from 'react';
import { Loader2, PencilRuler, RotateCcw } from 'lucide-react';
import { dqeService } from '../../api/dqeService';
import Alerte from '../ui/Alerte';
import EditeurPoteaux from '../import/EditeurPoteaux';

// Étape 2 (issue #94) : l'ingénieur ajoute, déplace ou supprime des poteaux
// sur le dessin, puis le SERVEUR recalcule poutres, charges et semelles.
// Les modifications restent un brouillon local jusqu'au recalcul ; elles
// sont annulables avant (historique de l'éditeur) et après (bouton dédié).

const ORIGINE_PAR_SOURCE = { trame: 'trame', plan: 'plan', saisie: 'saisi' };
const TOLERANCE_M = 0.01; // même tolérance que le serveur

const memePosition = (a, b) => Math.hypot(a.x - b.x, a.y - b.y) <= TOLERANCE_M;

function poteauxDuProjet(projet) {
  const defaut = ORIGINE_PAR_SOURCE[projet?.source_structure] || '';
  return (projet?.elements || [])
    .filter((e) => e.type_element === 'poteau' && e.position_x != null && e.position_y != null)
    .map((e) => ({ x: e.position_x, y: e.position_y, origine: e.origine_geometrie || defaut }));
}

function traitsPoutres(projet) {
  const elements = projet?.elements || [];
  const poteaux = new Map(elements.filter((e) => e.type_element === 'poteau').map((p) => [p.id, p]));
  return elements
    .filter((e) => e.type_element === 'poutre')
    .map((e) => [poteaux.get(e.poteau_origine), poteaux.get(e.poteau_destination)])
    .filter(([a, b]) => a && b && a.position_x != null && b.position_x != null)
    .map(([a, b]) => [a.position_x, a.position_y, b.position_x, b.position_y]);
}

export default function ModifierStructure({ projet, onAppliquer, onRetablirOrigine }) {
  const initiaux = useMemo(() => poteauxDuProjet(projet), [projet]);
  const poutres = useMemo(() => traitsPoutres(projet), [projet]);
  const [ouvert, setOuvert] = useState(false);
  const [brouillon, setBrouillon] = useState(initiaux);
  const [cle, setCle] = useState(0); // remet l'historique de l'éditeur à zéro
  const [fond, setFond] = useState(null);
  const [etat, setEtat] = useState({ enCours: false, erreur: null, succes: null });
  const [precedent, setPrecedent] = useState(null); // {liste, source} avant le dernier recalcul

  // Le projet a été rechargé (recalcul, autre projet) : le brouillon repart de lui.
  useEffect(() => { setBrouillon(initiaux); setCle((c) => c + 1); }, [initiaux]);

  // Plan d'architecte : affiché en fond, comme à l'étape 1.
  const architecte = projet?.parametres_import?.mode === 'architecte';
  useEffect(() => {
    if (!ouvert || !architecte || fond || !projet?.id) return;
    dqeService.getFondPlan(projet.id).then(setFond).catch(() => setFond(null));
  }, [ouvert, architecte, fond, projet?.id]);

  const ajoutes = brouillon.filter((p) => !initiaux.some((q) => memePosition(p, q))).length;
  const retires = initiaux.filter((q) => !brouillon.some((p) => memePosition(p, q))).length;
  const modifie = ajoutes > 0 || retires > 0;
  const nbValides = (projet?.elements || []).filter((e) => e.statut === 'valide'
    && ['poteau', 'semelle', 'poutre'].includes(e.type_element)).length;

  const recalculer = async () => {
    setEtat({ enCours: true, erreur: null, succes: null });
    const avant = { liste: initiaux, source: projet?.source_structure };
    try {
      const res = await onAppliquer(brouillon);
      setPrecedent(avant);
      setEtat({ enCours: false, erreur: null, succes: res?.poteaux });
    } catch (err) {
      setEtat({ enCours: false, erreur: err.message, succes: null });
    }
  };

  const annulerDerniere = async () => {
    if (!precedent) return;
    setEtat({ enCours: true, erreur: null, succes: null });
    try {
      // Revenir à la trame ou au plan d'origine : on relance leur propre
      // calcul (origines exactes) ; sinon on renvoie la liste précédente.
      if (['trame', 'plan'].includes(precedent.source)) await onRetablirOrigine();
      else await onAppliquer(precedent.liste);
      setPrecedent(null);
      setEtat({ enCours: false, erreur: null, succes: null });
    } catch (err) {
      setEtat({ enCours: false, erreur: `Annulation impossible : ${err.message}`, succes: null });
    }
  };

  if (!initiaux.length) return null;

  return (
    <section className="modifier-structure" aria-labelledby="titre-modifier-structure">
      <div className="modifier-structure-entete">
        <div>
          <h3 id="titre-modifier-structure">Modifier les poteaux sur le plan</h3>
          <p className="texte-discret">
            Ajoutez, déplacez ou supprimez des poteaux, puis recalculez : poutres, charges et semelles sont refaites par le
            moteur. Les poteaux ajoutés ou déplacés sont marqués « saisi ».
          </p>
        </div>
        <button type="button" className="btn btn-secondary" aria-expanded={ouvert} onClick={() => setOuvert((o) => !o)}>
          <PencilRuler size={16} /> <span>{ouvert ? 'Fermer l’éditeur' : 'Modifier la structure'}</span>
        </button>
      </div>

      {etat.succes && (
        <Alerte type="succes" titre="Structure recalculée">
          {etat.succes.total} poteaux, dont {etat.succes.saisis} saisi(s) à la main. Vérifiez les sections ci-dessous.
        </Alerte>
      )}
      {precedent && (
        <div className="modifier-structure-actions">
          <button type="button" className="btn btn-secondary" onClick={annulerDerniere} disabled={etat.enCours}>
            <RotateCcw size={16} /> <span>Annuler cette modification</span>
          </button>
          <span className="texte-discret">
            {['trame', 'plan'].includes(precedent.source)
              ? `Revient à la structure d'origine (${precedent.source === 'trame' ? 'trame' : 'plan importé'}).`
              : 'Revient aux poteaux d’avant le recalcul.'}
          </span>
        </div>
      )}
      {etat.erreur && <Alerte type="erreur" titre="Recalcul refusé">{etat.erreur}</Alerte>}

      {ouvert && (
        <>
          <EditeurPoteaux key={cle} fond={architecte ? fond : null} traitsStructure={poutres}
            poteaux={brouillon} onChange={setBrouillon} desactive={etat.enCours} libelleCompte="poteau(x)" />

          {modifie && nbValides > 0 && (
            <Alerte type="attention">
              {nbValides} poteau(x), poutre(s) ou semelle(s) déjà validé(s) seront recalculés et devront être validés à nouveau.
            </Alerte>
          )}
          <div className="modifier-structure-actions">
            <button type="button" className="btn btn-primary" onClick={recalculer} disabled={!modifie || etat.enCours}>
              {etat.enCours ? <Loader2 size={16} className="spin" /> : null}
              <span>{etat.enCours ? 'Recalcul…' : 'Recalculer avec ces poteaux'}</span>
            </button>
            <button type="button" className="btn btn-secondary" disabled={!modifie || etat.enCours}
              onClick={() => { setBrouillon(initiaux); setCle((c) => c + 1); }}>
              Abandonner les modifications
            </button>
            <span className="modifier-structure-bilan" aria-live="polite">
              {modifie ? `${ajoutes} poteau(x) ajouté(s) ou déplacé(s), ${retires} retiré(s) ou déplacé(s)` : 'Aucune modification'}
            </span>
          </div>
        </>
      )}
    </section>
  );
}
