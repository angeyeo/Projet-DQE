import React, { useState } from 'react';
import { Compass, Mail, Lock, ArrowRight, Loader2, AlertCircle } from 'lucide-react';
import { dqeService } from '../api/dqeService';

export default function LoginPage({ onEnterApp, onBackToLanding, onGoToRegister, onGoToForgotPassword }) {
  const [email, setEmail] = useState('');
  const [motDePasse, setMotDePasse] = useState('');
  const [loading, setLoading] = useState(false);
  const [erreur, setErreur] = useState(null);

  // Connexion réelle -- dqeService.login() appelle POST /api/auth/token/
  // et stocke access/refresh en localStorage (voir dqeService.js).
  const handleSubmit = async (e) => {
    e.preventDefault();
    setErreur(null);
    setLoading(true);
    try {
      await dqeService.login(email, motDePasse);
      onEnterApp();
    } catch (err) {
      setErreur(err.status === 401 ? 'Email ou mot de passe incorrect.' : (err.message || 'Connexion impossible.'));
    } finally {
      setLoading(false);
    }
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
                autoComplete="username"
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
                autoComplete="current-password"
              />
            </div>
          </div>

          {erreur && (
            <div style={{ display: 'flex', alignItems: 'center', gap: '0.4rem', color: 'var(--status-critical)', fontSize: '0.82rem', marginBottom: '1rem' }}>
              <AlertCircle size={14} />
              <span>{erreur}</span>
            </div>
          )}

          <button type="submit" className="btn btn-primary" style={{ width: '100%', padding: '0.85rem' }} disabled={loading}>
            {loading ? <Loader2 size={17} className="spin" /> : <ArrowRight size={17} />}
            <span>{loading ? 'Connexion...' : 'Se connecter'}</span>
          </button>

          <p className="login-switch">
            Pas encore de compte entreprise ?{' '}
            <button type="button" className="login-link-inline" onClick={onGoToRegister}>
              Créer un compte
            </button>
          </p>
        </form>
      </div>
    </div>
  );
}