import React, { useState } from 'react';
import { Compass, Mail, ArrowRight, Info, CheckCircle2, Loader2 } from 'lucide-react';
import { dqeService } from '../api/dqeService';

export default function ForgotPasswordPage({ onBackToLanding, onGoToLogin }) {
  const [email, setEmail] = useState('');
  const [envoye, setEnvoye] = useState(false);
  const [emailReellementEnvoye, setEmailReellementEnvoye] = useState(false);
  const [lienSecours, setLienSecours] = useState(null);
  const [loading, setLoading] = useState(false);

  // Appel réel : POST /api/auth/mot-de-passe-oublie/. Le backend ne révèle
  // jamais si l'email existe (email_envoye est identique que le compte
  // existe ou non, par design -- pas d'énumération de comptes) : voir
  // DemanderReinitialisationView. On peut donc afficher email_envoye tel
  // quel sans rien révéler sur l'existence du compte.
  const handleSubmit = async (e) => {
    e.preventDefault();
    if (!email.trim()) return;
    setLoading(true);
    try {
      const res = await dqeService.demanderReinitialisation(email.trim());
      setEmailReellementEnvoye(Boolean(res?.email_envoye));
      setLienSecours(res?.lien_reinitialisation || null);
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
                  Si un compte existe pour cette adresse, un lien de
                  réinitialisation vous sera transmis.
                </span>
              </div>
            </>
          ) : (
            <div className="login-notice" style={{ background: 'var(--status-ok-soft)' }}>
              <CheckCircle2 size={14} style={{ color: 'var(--status-ok)' }} />
              <span>
                {emailReellementEnvoye ? (
                  <>
                    Si un compte existe pour <strong>{email}</strong>, un email de
                    réinitialisation vient d'être envoyé -- vérifiez votre boîte de
                    réception (et vos spams).
                  </>
                ) : (
                  <>
                    Si un compte existe pour <strong>{email}</strong>, une
                    demande de réinitialisation a été enregistrée. Aucun email
                    n'a réellement été envoyé (pas de serveur SMTP configuré).
                    {lienSecours && (
                      <>
                        {' '}Lien de secours :{' '}
                        <a href={lienSecours}>{window.location.origin + lienSecours}</a>
                      </>
                    )}
                  </>
                )}
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