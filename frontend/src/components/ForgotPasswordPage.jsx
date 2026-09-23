import React, { useState } from 'react';
import { Compass, Mail, ArrowRight, Info, CheckCircle2, Loader2 } from 'lucide-react';
import { dqeService } from '../api/dqeService';

export default function ForgotPasswordPage({ onBackToLanding, onGoToLogin }) {
  const [email, setEmail] = useState('');
  const [envoye, setEnvoye] = useState(false);
  const [loading, setLoading] = useState(false);

  // Appel réel : POST /api/auth/mot-de-passe-oublie/. Le backend ne
  // révèle jamais si l'email existe (email_envoye est toujours false
  // dans la réponse, par design -- pas d'énumération de comptes) : voir
  // DemanderReinitialisationView. Aucun SMTP n'est configuré ce jour, donc
  // aucun email n'est réellement envoyé -- ça reste vrai à dire, mais la
  // demande elle-même est désormais bien traitée côté serveur.
  const handleSubmit = async (e) => {
    e.preventDefault();
    if (!email.trim()) return;
    setLoading(true);
    try {
      await dqeService.demanderReinitialisation(email.trim());
    } finally {
      setLoading(false);
      setEnvoye(true);
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

              <button type="submit" className="btn btn-primary" style={{ width: '100%', padding: '0.85rem' }} disabled={loading}>
                {loading ? <Loader2 size={17} className="spin" /> : <ArrowRight size={17} />}
                <span>{loading ? 'Envoi...' : 'Envoyer le lien'}</span>
              </button>

              <div className="login-notice">
                <Info size={14} />
                <span>
                  Aucun serveur d'envoi d'email n'est encore configuré :
                  la demande est bien traitée, mais aucun email ne sera
                  réellement reçu pour l'instant.
                </span>
              </div>
            </>
          ) : (
            <div className="login-notice" style={{ background: 'var(--status-ok-soft)' }}>
              <CheckCircle2 size={14} style={{ color: 'var(--status-ok)' }} />
              <span>
                Si un compte existe pour <strong>{email}</strong>, une
                demande de réinitialisation a été enregistrée. Aucun email
                n'a réellement été envoyé (pas de serveur SMTP configuré).
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