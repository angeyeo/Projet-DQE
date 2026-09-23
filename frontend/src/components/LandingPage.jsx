import React from 'react';
import {
  Compass, ArrowRight, FileUp, Calculator, ShieldCheck, FileSpreadsheet,
  Sparkles, Lock, Layers, Building2, CheckCircle2, Ruler,
} from 'lucide-react';

function HeroVisual() {
  // Représentation visuelle du logiciel -- pas une image générique : une
  // reconstitution stylisée du tableau de bord réel (cartes KPI + tableau
  // d'éléments + repères de cotation), en CSS pur.
  return (
    <div className="hero-visual">
      <div className="hero-visual-glow" />
      <div className="hero-mock-window">
        <div className="hero-mock-titlebar">
          <span /><span /><span />
          <div className="hero-mock-title">BTP Innovation Ivoire — Tableau de bord</div>
        </div>
        <div className="hero-mock-body">
          <div className="hero-mock-kpis">
            <div className="hero-mock-kpi">
              <Layers size={16} />
              <div>
                <div className="hero-mock-kpi-value">128</div>
                <div className="hero-mock-kpi-label">Éléments calculés</div>
              </div>
            </div>
            <div className="hero-mock-kpi accent">
              <ShieldCheck size={16} />
              <div>
                <div className="hero-mock-kpi-value">94%</div>
                <div className="hero-mock-kpi-label">Verrouillé</div>
              </div>
            </div>
          </div>
          <div className="hero-mock-table">
            <div className="hero-mock-row header">
              <span>Élément</span><span>Section</span><span>Statut</span>
            </div>
            {[
              ['P1 — Poteau', '20×20', 'ok'],
              ['R2 — Poutre', '20×40', 'ok'],
              ['S3 — Semelle', '120×120', 'warn'],
            ].map(([label, section, status]) => (
              <div className="hero-mock-row" key={label}>
                <span>{label}</span>
                <span className="tabular">{section}</span>
                <span className={`hero-mock-dot ${status}`} />
              </div>
            ))}
          </div>
          <div className="hero-mock-chart">
            {[38, 62, 45, 80, 55, 70, 90].map((h, i) => (
              <div key={i} className="hero-mock-bar" style={{ height: `${h}%`, animationDelay: `${i * 0.06}s` }} />
            ))}
          </div>
        </div>
      </div>

      {/* Cotation flottante -- clin d'œil "plan technique" */}
      <div className="hero-cote hero-cote-1">Ø 12 HA</div>
      <div className="hero-cote hero-cote-2">BAEL 91</div>
    </div>
  );
}

const FEATURES = [
  {
    icon: FileUp,
    title: 'Import de plans IFC',
    text: "Importez vos fichiers IFC et laissez le moteur détecter automatiquement la trame structurelle, les poteaux, poutres et semelles.",
  },
  {
    icon: Calculator,
    title: 'Calcul BAEL 91 automatisé',
    text: "Descente de charge, ferraillage et pré-dimensionnement calculés selon les normes en vigueur, élément par élément.",
  },
  {
    icon: Sparkles,
    title: 'Assistant IA intégré',
    text: "Structuration de projet en langage naturel, explication des sections proposées, contrôle de cohérence structurelle avant validation.",
  },
  {
    icon: FileSpreadsheet,
    title: 'DQE exportable',
    text: "Génération du devis quantitatif estimatif au format lots CIMBAT, prêt pour l'export PDF et Excel.",
  },
];

const STEPS = [
  { title: 'Importez votre plan', text: 'Déposez un fichier IFC ou décrivez votre projet en langage naturel.' },
  { title: 'Vérifiez les calculs', text: "Le moteur propose les sections ; l'assistant IA explique chaque proposition." },
  { title: 'Validez en ingénieur', text: 'Verrouillez les sections : seul un ingénieur peut engager le calcul.' },
  { title: 'Exportez le DQE', text: 'Devis quantitatif prêt, structuré par lots, exportable immédiatement.' },
];

export default function LandingPage({ onGetStarted, onLogin }) {
  return (
    <div className="landing">
      <nav className="landing-nav">
        <div className="brand-wrapper">
          <div className="brand-icon-box"><Compass size={20} /></div>
          <span className="landing-brand-name">BTP Innovation Ivoire</span>
        </div>
        <button className="btn btn-secondary" onClick={onLogin}>
          <span>Se connecter</span>
        </button>
      </nav>

      {/* Hero */}
      <section className="landing-hero">
        <div className="landing-hero-text fade-in-up">
          <span className="badge badge-info" style={{ marginBottom: '1.1rem' }}>
            <Ruler size={13} /> Logiciel professionnel DQE / BTP
          </span>
          <h1>
            Le calcul structurel<br />et le DQE, <span className="accent-text">sans ressaisie</span>.
          </h1>
          <p>
            BTP Innovation Ivoire transforme vos plans IFC en pré-dimensionnement BAEL 91
            et en devis quantitatif estimatif — avec un assistant IA qui
            explique chaque section, et un verrou d'ingénieur qui garde la
            responsabilité là où elle doit être.
          </p>
          <div className="landing-hero-cta">
            <button className="btn btn-primary" onClick={onGetStarted} style={{ padding: '0.9rem 1.6rem' }}>
              <span>Commencer un projet</span>
              <ArrowRight size={17} />
            </button>
            <button className="btn btn-secondary" onClick={onLogin} style={{ padding: '0.9rem 1.6rem' }}>
              <span>Se connecter</span>
            </button>
          </div>
        </div>
        <HeroVisual />
      </section>

      {/* Ce que fait le logiciel */}
      <section className="landing-section">
        <h2>Un logiciel, tout le flux DQE</h2>
        <p className="landing-section-sub">
          De l'import du plan à l'export du devis, sans tableur intermédiaire.
        </p>
        <div className="grid-4 stagger" style={{ marginTop: '2rem' }}>
          {FEATURES.map((f) => (
            <div className="plan-card" key={f.title}>
              <div className="kpi-icon orange" style={{ marginBottom: '0.9rem' }}>
                <f.icon size={20} />
              </div>
              <h3 style={{ fontSize: '1rem', fontWeight: 700, marginBottom: '0.4rem' }}>{f.title}</h3>
              <p style={{ fontSize: '0.85rem', color: 'var(--ink-500)', lineHeight: 1.55 }}>{f.text}</p>
            </div>
          ))}
        </div>
      </section>

      {/* À qui il s'adresse / pourquoi différent */}
      <section className="landing-section landing-section-alt">
        <div className="grid-2">
          <div className="fade-in-up">
            <span className="badge badge-info"><Building2 size={13} /> Pour qui</span>
            <h2 style={{ marginTop: '0.9rem' }}>Conçu pour les bureaux d'études structure</h2>
            <p style={{ color: 'var(--ink-500)', marginTop: '0.75rem', lineHeight: 1.6 }}>
              BTP Innovation Ivoire s'adresse aux bureaux d'études BTP qui produisent des
              plans de fondation et des DQE au quotidien, et qui veulent
              gagner le temps perdu en ressaisie entre le plan, le calcul et
              le devis — sans jamais sacrifier la validation par un ingénieur.
            </p>
          </div>
          <div className="fade-in-up">
            <span className="badge badge-info"><Lock size={13} /> Pourquoi différent</span>
            <h2 style={{ marginTop: '0.9rem' }}>L'IA propose, l'ingénieur décide</h2>
            <ul className="landing-check-list">
              <li><CheckCircle2 size={17} /> Chaque section calculée reste modifiable jusqu'au verrouillage</li>
              <li><CheckCircle2 size={17} /> L'assistant IA explique, il ne valide jamais à votre place</li>
              <li><CheckCircle2 size={17} /> Contrôle de cohérence structurelle avant export du DQE</li>
              <li><CheckCircle2 size={17} /> Conventions CIMBAT natives, pas de mise en forme manuelle</li>
            </ul>
          </div>
        </div>
      </section>

      {/* Comment commencer */}
      <section className="landing-section">
        <h2>Comment démarrer un projet</h2>
        <div className="landing-steps stagger">
          {STEPS.map((s, i) => (
            <div className="landing-step" key={s.title}>
              <div className="landing-step-num">{String(i + 1).padStart(2, '0')}</div>
              <h3>{s.title}</h3>
              <p>{s.text}</p>
            </div>
          ))}
        </div>
        <div style={{ textAlign: 'center', marginTop: '2.5rem' }}>
          <button className="btn btn-primary" onClick={onGetStarted} style={{ padding: '0.9rem 1.8rem' }}>
            <span>Commencer un projet</span>
            <ArrowRight size={17} />
          </button>
        </div>
      </section>

      <footer className="landing-footer">
        <div className="brand-wrapper">
          <div className="brand-icon-box" style={{ width: 28, height: 28 }}><Compass size={15} /></div>
          <span style={{ fontWeight: 600 }}>BTP Innovation Ivoire</span>
        </div>
        <span style={{ color: 'var(--ink-500)', fontSize: '0.8rem' }}>
          Logiciel de calcul et gestion DQE pour le secteur BTP.
        </span>
      </footer>
    </div>
  );
}