import React from 'react';
import { BrickWall, CheckCircle2, Grid3x3, Loader2 } from 'lucide-react';
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

// Dalles rectangulaires lues dans le DXF (issue #80), sur les poteaux du plan
// retenu. Aucune n'est créée sans être cochée ; Lx, Ly = côtés du rectangle.
function DallesProposees({ apercu, choisies, onDalles }) {
  const dalles = apercu.dalles_proposees || [];
  if (!dalles.length) return null;
  const pts = apercu.poteaux_apercu || [];
  const xs = [...pts.map((p) => p[0]), ...dalles.flatMap((d) => [d.emprise[0], d.emprise[2]])];
  const ys = [...pts.map((p) => p[1]), ...dalles.flatMap((d) => [d.emprise[1], d.emprise[3]])];
  const [x0, x1, y0, y1] = [Math.min(...xs), Math.max(...xs), Math.min(...ys), Math.max(...ys)];
  const t = Math.max(x1 - x0, y1 - y0, 1);
  const m = t * 0.06;
  const ensemble = new Set(choisies);
  const basculer = (id) => onDalles(ensemble.has(id) ? choisies.filter((c) => c !== id) : [...choisies, id]);
  const surface = dalles.filter((d) => ensemble.has(d.id)).reduce((s, d) => s + d.lx * d.ly, 0);
  return (
    <div className="dalles-dxf">
      <h4><Grid3x3 size={16} aria-hidden="true" /> {dalles.length} dalle(s) lue(s) dans le dessin</h4>
      <p className="texte-discret">
        Cochez celles à créer : elles seront calculées par le moteur et marquées « lues dans le plan ». Vérifiez Lx et Ly à
        l&apos;étape Dalles avant de les valider. Les dalles saisies à la main ne sont jamais modifiées.
      </p>
      <div className="dalles-dxf-corps">
        <svg className="vignette-dalles" viewBox={`${x0 - m} ${-y1 - m} ${x1 - x0 + 2 * m} ${y1 - y0 + 2 * m}`} aria-hidden="true">
          {dalles.map((d, i) => (
            <g key={d.id} className={ensemble.has(d.id) ? 'dalle gardee' : 'dalle'}>
              <rect x={d.emprise[0]} y={-d.emprise[3]} width={d.emprise[2] - d.emprise[0]} height={d.emprise[3] - d.emprise[1]} />
              <text x={d.x} y={-d.y} fontSize={t * 0.06} textAnchor="middle" dominantBaseline="middle">{i + 1}</text>
            </g>
          ))}
          {pts.map(([x, y], i) => <rect key={`p${i}`} className="poteau" x={x - t * 0.01} y={-y - t * 0.01} width={t * 0.02} height={t * 0.02} />)}
        </svg>
        <div>
          <ul className="liste-dalles-dxf">
            {dalles.map((d, i) => (
              <li key={d.id}>
                <label className="case-a-cocher">
                  <input type="checkbox" checked={ensemble.has(d.id)} onChange={() => basculer(d.id)} />
                  <span className="tabular"><strong>{i + 1}</strong> · Lx {nf(d.lx, 2)} × Ly {nf(d.ly, 2)} m
                    <span className="texte-discret"> · {nf(d.lx * d.ly, 2)} m² · {d.nom}</span></span>
                </label>
              </li>
            ))}
          </ul>
          <div className="actions-ligne">
            <button type="button" className="btn btn-secondary btn-compact" onClick={() => onDalles(dalles.map((d) => d.id))}>Tout cocher</button>
            <button type="button" className="btn btn-secondary btn-compact" disabled={!choisies.length} onClick={() => onDalles([])}>Tout décocher</button>
          </div>
          <p className="texte-discret tabular">{choisies.length} dalle(s) gardée(s){choisies.length ? ` · ${nf(surface, 2)} m²` : ''}</p>
        </div>
      </div>
    </div>
  );
}

// Aperçu d'un import DXF : choix du plan des fondations quand le fichier
// en contient plusieurs, puis reprise (optionnelle) des murs du dessin.
export default function ApercuDXF({ apercu, choixEnCours, onChoisirPlan, reprendreMurs, onReprendreMurs, dallesChoisies = [], onDalles }) {
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
          {onDalles && <DallesProposees apercu={apercu} choisies={dallesChoisies} onDalles={onDalles} />}
        </div>
      )}
    </section>
  );
}
