import React from 'react';
import { Plus, Trash2 } from 'lucide-react';

const COUCHE_VIDE = { type: '', designation: '', poidsSurfacique: '', epaisseur: '', poidsVolumique: '' };

// Hypothèses de charges du projet : G des planchers (composition > valeur
// saisie > forfait validé et signalé), poids propre de l'ossature, méthode des
// semelles. Le CALCUL de G est fait par le serveur : ici, saisie seulement.
export default function HypothesesCharges({ projectData, updateProjectData, referentiel }) {
  const cp = referentiel?.charges_permanentes;
  const catalogue = cp?.catalogue_couches || [];
  const couches = projectData.couchesPermanentes || [];
  const setCouches = (c) => updateProjectData({ couchesPermanentes: c });
  const majCouche = (i, champs) => setCouches(couches.map((c, k) => (k === i ? { ...c, ...champs } : c)));
  const ref = (type) => catalogue.find((c) => c.type === type);

  const origine = couches.length ? 'couches' : projectData.chargePermanente !== '' ? 'saisie' : 'forfait';

  return (
    <fieldset className="hypotheses-charges">
      <legend>Hypothèses de charges</legend>
      <p className="texte-discret">
        Combinaisons : ELU {referentiel?.combinaisons?.elu || '—'} · ELS {referentiel?.combinaisons?.els || '—'}.
      </p>

      <div className="grid-2">
        <div className="form-group">
          <label className="form-label" htmlFor="champ-s1-g">Charge permanente des planchers G (kN/m²)</label>
          <input id="champ-s1-g" type="number" min="0" step="0.1" className="form-control"
            disabled={couches.length > 0}
            placeholder={cp ? `vide = forfait ${cp.forfait_kn_m2} (hypothèse)` : ''}
            value={projectData.chargePermanente ?? ''} onChange={(e) => updateProjectData({ chargePermanente: e.target.value })} />
          <small className="aide-champ">
            {origine === 'couches' && 'G sera CALCULÉE par le serveur à partir de la composition ci-dessous (prioritaire).'}
            {origine === 'saisie' && 'Valeur SAISIE : elle remplace le forfait.'}
            {origine === 'forfait' && cp && `Laissée vide : G = ${cp.forfait_kn_m2} kN/m², valeur par défaut validée (${cp.contenu_forfait}). Signalée dans chaque résultat.`}
          </small>
        </div>
        <div className="form-group">
          <label className="form-label" htmlFor="champ-s1-meth">Dimensionnement des semelles</label>
          <select id="champ-s1-meth" className="form-select" value={projectData.methodeSemelles || 'ELU'}
            onChange={(e) => updateProjectData({ methodeSemelles: e.target.value })}>
            {(referentiel?.methodes_semelles || []).map((m) => <option key={m.cle} value={m.cle}>{m.libelle}</option>)}
          </select>
          <small className="aide-champ">ELU = méthode validée par le technicien BTP (A² ≥ Nu / σsol). ELS reste disponible pour comparer en variante.</small>
        </div>
      </div>

      {referentiel?.charge_exploitation_toiture_kn_m2 != null && (
        <p className="texte-discret">
          Toiture : Q = {String(referentiel.charge_exploitation_toiture_kn_m2).replace('.', ',')} kN/m² (valeur validée), quel que soit l'usage des étages.
        </p>
      )}

      <label className="case-a-cocher">
        <input type="checkbox" checked={!!projectData.inclurePoidsPropre}
          onChange={(e) => updateProjectData({ inclurePoidsPropre: e.target.checked })} />
        <span>Ajouter le poids propre des poutres, poteaux et semelles (b × h × 25 kN/m³). Coché par défaut : le forfait G ne les couvre pas (règle validée).</span>
      </label>

      <details className="composition" open={couches.length > 0}>
        <summary>Composition du plancher ({couches.length} couche(s))</summary>
        {cp?.avertissement && <p className="texte-discret">{cp.avertissement}</p>}
        {couches.map((c, i) => {
          const r = ref(c.type);
          const volumique = r ? r.poids_volumique_kn_m3 != null : c.poidsSurfacique === '';
          return (
            <div className="ligne-couche" key={i}>
              <select aria-label={`Type de la couche ${i + 1}`} className="form-select" value={c.type}
                onChange={(e) => majCouche(i, { type: e.target.value })}>
                <option value="">Valeurs saisies</option>
                {catalogue.map((t) => (
                  <option key={t.type} value={t.type}>
                    {t.libelle} ({t.poids_volumique_kn_m3 != null ? `${t.poids_volumique_kn_m3} kN/m³` : `${t.poids_surfacique_kn_m2} kN/m²`})
                  </option>
                ))}
              </select>
              <input aria-label={`Désignation de la couche ${i + 1}`} className="form-control" placeholder="Désignation"
                value={c.designation} onChange={(e) => majCouche(i, { designation: e.target.value })} />
              {volumique && (
                <input aria-label={`Épaisseur de la couche ${i + 1} (m)`} type="number" min="0" step="0.01" className="form-control"
                  placeholder="épaisseur (m)" value={c.epaisseur} onChange={(e) => majCouche(i, { epaisseur: e.target.value })} />
              )}
              {!c.type && (
                <>
                  <input aria-label={`Poids volumique de la couche ${i + 1}`} type="number" min="0" step="0.1" className="form-control"
                    placeholder="kN/m³" value={c.poidsVolumique} onChange={(e) => majCouche(i, { poidsVolumique: e.target.value })} />
                  <input aria-label={`Poids surfacique de la couche ${i + 1}`} type="number" min="0" step="0.01" className="form-control"
                    placeholder="ou kN/m²" value={c.poidsSurfacique} onChange={(e) => majCouche(i, { poidsSurfacique: e.target.value })} />
                </>
              )}
              <button type="button" className="btn btn-secondary btn-compact" aria-label={`Supprimer la couche ${i + 1}`}
                onClick={() => setCouches(couches.filter((_, k) => k !== i))}>
                <Trash2 size={14} aria-hidden="true" />
              </button>
            </div>
          );
        })}
        <button type="button" className="btn btn-secondary btn-compact" onClick={() => setCouches([...couches, { ...COUCHE_VIDE }])}>
          <Plus size={14} aria-hidden="true" /> <span>Ajouter une couche</span>
        </button>
      </details>
    </fieldset>
  );
}
