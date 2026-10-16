import React from 'react';
import { BrickWall, CheckCircle2, Loader2 } from 'lucide-react';
import { nf } from '../charts/palette';

// Vignette d'un plan : positions des poteaux lues dans le DXF (aucune
// donnée inventée), mises à l'échelle dans un cadre fixe.
function Vignette({ plan }) {
  const pts = plan.poteaux_apercu || [];
  const L = Math.max(plan.largeur_m, 1);
  const P = Math.max(plan.profondeur_m, 1);
  const marge = Math.max(L, P) * 0.08;
  return (
    <svg className="vignette-plan" viewBox={`${-marge} ${-P - marge} ${L + 2 * marge} ${P + 2 * marge}`} aria-hidden="true">
      {pts.map(([x, y], i) => (
        <rect key={i} x={x - Math.max(L, P) * 0.012} y={-y - Math.max(L, P) * 0.012}
          width={Math.max(L, P) * 0.024} height={Math.max(L, P) * 0.024} />
      ))}
    </svg>
  );
}

// Aperçu d'un import DXF : choix du plan des fondations quand le fichier
// en contient plusieurs, puis reprise (optionnelle) des murs du dessin.
export default function ApercuDXF({ apercu, choixEnCours, onChoisirPlan, reprendreMurs, onReprendreMurs }) {
  if (!apercu) return null;
  const retenu = apercu.plans.find((p) => p.id === apercu.plan_retenu);
  const nbMurs = apercu.murs_proposes?.length ?? 0;

  return (
    <section className="apercu-dxf" aria-labelledby="titre-apercu-dxf">
      <h3 id="titre-apercu-dxf">Plan DXF lu <span className="texte-discret">· unités : {apercu.unite}</span></h3>

      {apercu.plans.length > 1 && (
        <>
          <p className="texte-discret">
            Le fichier contient {apercu.plans.length} plans côte à côte. Choisissez celui du <strong>rez-de-chaussée</strong> :
            ses poteaux portent les fondations. Les autres plans ne sont pas utilisés.
          </p>
          <div className="choix-plans" role="radiogroup" aria-label="Plan des fondations">
            {apercu.plans.map((p) => {
              const actif = p.id === apercu.plan_retenu;
              return (
                <button key={p.id} type="button" role="radio" aria-checked={actif} disabled={choixEnCours}
                  className={actif ? 'carte-plan actif' : 'carte-plan'} onClick={() => onChoisirPlan(p.id)}>
                  <Vignette plan={p} />
                  <span className="carte-plan-titre">
                    {actif && <CheckCircle2 size={14} aria-hidden="true" />} Plan {p.id.replace('plan-', '')}
                  </span>
                  <span className="texte-discret tabular">
                    {p.nb_poteaux} poteaux · {p.nb_murs} murs · {nf(p.largeur_m, 1)} × {nf(p.profondeur_m, 1)} m
                  </span>
                  {p.nb_doublons > 0 && <span className="texte-discret">{p.nb_doublons} poteau(x) doublé(s)</span>}
                </button>
              );
            })}
          </div>
          {choixEnCours && <p className="texte-discret" role="status"><Loader2 size={14} className="spin" /> Lecture du plan…</p>}
        </>
      )}

      {retenu && (
        <div className="apercu-dxf-retenu">
          <p>
            <strong>{apercu.nb_poteaux_detectes} poteaux</strong> retenus pour la trame
            {apercu.plans.length > 1 && <> (plan {retenu.id.replace('plan-', '')})</>}.
          </p>
          {nbMurs > 0 ? (
            <label className="case-a-cocher">
              <input type="checkbox" checked={reprendreMurs} onChange={(e) => onReprendreMurs(e.target.checked)} />
              <span>
                <BrickWall size={14} aria-hidden="true" /> Reprendre les murs du dessin comme murs du rez-de-chaussée :
                {' '}{nbMurs} poutre(s) sur lesquelles un mur est dessiné. À vérifier ensuite sur le plan des murs.
              </span>
            </label>
          ) : (
            <p className="texte-discret">Aucun mur du dessin ne suit les poutres : placez les murs sur le plan des murs.</p>
          )}
        </div>
      )}
    </section>
  );
}
