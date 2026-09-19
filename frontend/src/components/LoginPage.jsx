import React, { useState } from 'react';
import { Compass, Building2, Mail, Lock, ArrowRight, Info } from 'lucide-react';

export default function LoginPage({ onEnterApp, onBackToLanding, onGoToRegister, onGoToForgotPassword }) {
  const [nomEntreprise, setNomEntreprise] = useState('');
  const [email, setEmail] = useState('');
  const [motDePasse, setMotDePasse] = useState('');

  // IMPORTANT : il n'existe pas encore d'API d'authentification côté
  // backend (Entreprise/Profil/JWT -- prévu au sprint permissions). On ne
  // simule donc PAS une connexion réussie avec des données inventées : on
  // le dit clairement et on laisse entrer en mode direct, sans prétendre
  // qu'un compte a été vérifié.
  const handleSubmit = (e) => {
    e.preventDefault();
    onEnterApp();
  };

  return (
    <div className="login-screen">
      <div className="login-visual">
        <div className="login-visual-inner">
          <div className="brand-wrapper" style={{ marginBottom: '2rem' }}>
            <div className="brand-icon-box"><Compass size={20} /></div>
            <span className="landing-brand-name" style={{ color: 'var(--side-text-active)' }}>BTP Innovation Ivoire</span>
          </div>
          <h2>Le calcul structurel, sans ressaisie.</h2>
          <p>
            Chaque cabinet accède à son propre espace : ses projets, ses
            paramètres d'entreprise, ses devis.
          </p>
        </div>
      </div>

      <div className="login-form-side">
        <form className="login-form fade-in-up" onSubmit={handleSubmit}>
          <button type="button" className="login-back" onClick={onBackToLanding}>← Retour</button>
          <h1>Connexion</h1>
          <p className="login-sub">Accédez à l'espace de votre entreprise.</p>

          <div className="form-group">
            <label className="form-label">Nom de l'entreprise</label>
            <div className="input-icon-wrap">
              <Building2 size={17} />
              <input
                className="form-control"
                style={{ paddingLeft: '2.4rem' }}
                placeholder="ex : BATI-PRO SARL"
                value={nomEntreprise}
                onChange={(e) => setNomEntreprise(e.target.value)}
              />
            </div>
          </div>

          <div className="form-group">
            <label className="form-label">Email professionnel</label>
            <div className="input-icon-wrap">
              <Mail size={17} />
              <input
                type="email"
                className="form-control"
                style={{ paddingLeft: '2.4rem' }}
                placeholder="vous@entreprise.com"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
              />
            </div>
          </div>

          <div className="form-group">
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '0.45rem' }}>
              <label className="form-label" style={{ marginBottom: 0 }}>Mot de passe</label>
              <button type="button" className="login-link-inline" onClick={onGoToForgotPassword}>
                Mot de passe oublié ?
              </button>
            </div>
            <div className="input-icon-wrap">
              <Lock size={17} />
              <input
                type="password"
                className="form-control"
                style={{ paddingLeft: '2.4rem' }}
                placeholder="••••••••"
                value={motDePasse}
                onChange={(e) => setMotDePasse(e.target.value)}
              />
            </div>
          </div>

          <button type="submit" className="btn btn-primary" style={{ width: '100%', padding: '0.85rem' }}>
            <span>Se connecter</span>
            <ArrowRight size={17} />
          </button>

          <p className="login-switch">
            Pas encore de compte entreprise ?{' '}
            <button type="button" className="login-link-inline" onClick={onGoToRegister}>
              Créer un compte
            </button>
          </p>

          <div className="login-notice">
            <Info size={14} />
            <span>
              L'authentification par compte d'entreprise est en cours de
              déploiement côté serveur. En attendant, ce bouton vous fait
              entrer directement dans l'application.
            </span>
          </div>
        </form>
      </div>
    </div>
  );
}