import React, { useState } from 'react';
import { Compass, Mail, ArrowRight, Info, CheckCircle2 } from 'lucide-react';

export default function ForgotPasswordPage({ onBackToLanding, onGoToLogin }) {
  const [email, setEmail] = useState('');
  const [envoye, setEnvoye] = useState(false);

  // Il n'existe aucune API d'envoi d'email de réinitialisation côté
  // backend. On n'affiche donc jamais "email envoyé" comme s'il l'avait
  // réellement été -- on montre l'état "demande enregistrée localement"
  // et on explique honnêtement que rien n'est encore branché.
  const handleSubmit = (e) => {
    e.preventDefault();
    if (!email.trim()) return;
    setEnvoye(true);
  };

  return (
    <div className="login-screen">
      <div className="login-visual">
        <div className="login-visual-inner">
          <div className="brand-wrapper" style={{ marginBottom: '2rem' }}>
            <div className="brand-icon-box"><Compass size={20} /></div>
            <span className="landing-brand-name" style={{ color: 'var(--side-text-active)' }}>BTP Innovation Ivoire</span>
          </div>
          <h2>Mot de passe oublié ?</h2>
          <p>Indiquez l'email associé à votre compte entreprise.</p>
        </div>
      </div>

      <div className="login-form-side">
        <form className="login-form fade-in-up" onSubmit={handleSubmit}>
          <button type="button" className="login-back" onClick={onBackToLanding}>← Retour</button>
          <h1>Réinitialiser le mot de passe</h1>
          <p className="login-sub">
            Saisissez votre email professionnel, un lien de réinitialisation vous sera envoyé.
          </p>

          {!envoye ? (
            <>
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

              <button type="submit" className="btn btn-primary" style={{ width: '100%', padding: '0.85rem' }}>
                <span>Envoyer le lien</span>
                <ArrowRight size={17} />
              </button>

              <div className="login-notice">
                <Info size={14} />
                <span>
                  L'envoi d'email de réinitialisation n'est pas encore
                  branché côté serveur : aucun email ne sera réellement
                  envoyé tant que cette fonctionnalité n'est pas déployée.
                </span>
              </div>
            </>
          ) : (
            <div className="login-notice" style={{ background: 'var(--status-ok-soft)' }}>
              <CheckCircle2 size={14} style={{ color: 'var(--status-ok)' }} />
              <span>
                Demande enregistrée pour <strong>{email}</strong>. Aucun
                email n'a réellement été envoyé -- cette fonctionnalité
                arrive avec l'authentification par compte entreprise.
              </span>
            </div>
          )}

          <p className="login-switch">
            <button type="button" className="login-link-inline" onClick={onGoToLogin}>
              ← Retour à la connexion
            </button>
          </p>
        </form>
      </div>
    </div>
  );
}