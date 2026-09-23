import React, { useState } from 'react';
import { Compass, Lock, ArrowRight, Loader2, AlertCircle, CheckCircle2 } from 'lucide-react';
import { dqeService } from '../api/dqeService';

// Page atteinte via le lien généré par InviterUtilisateurView
// (/activer-compte?uid=...&token=...). uid/token sont lus depuis l'URL
// par App.jsx (pas de routeur dans cette app) et passés ici en props.
export default function ActivateAccountPage({ uid, token, onGoToLogin }) {
  const [motDePasse, setMotDePasse] = useState('');
  const [confirmation, setConfirmation] = useState('');
  const [loading, setLoading] = useState(false);
  const [erreur, setErreur] = useState(null);
  const [succes, setSucces] = useState(false);

  const motsDePasseDifferents = motDePasse.length > 0 && confirmation.length > 0 && motDePasse !== confirmation;
  const lienInvalide = !uid || !token;

  const handleSubmit = async (e) => {
    e.preventDefault();
    if (motsDePasseDifferents || lienInvalide) return;
    setErreur(null);
    setLoading(true);
    try {
      await dqeService.activerCompte({ uid, token, motDePasse });
      setSucces(true);
    } catch (err) {
      const d = err.data || {};
      setErreur(d.mot_de_passe ? [].concat(d.mot_de_passe).join(' ') : (d.detail || err.message || "Lien d'activation invalide ou expiré."));
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
          <h2>Bienvenue dans l'équipe.</h2>
          <p>Définissez votre mot de passe pour activer votre compte.</p>
        </div>
      </div>

      <div className="login-form-side">
        <form className="login-form fade-in-up" onSubmit={handleSubmit}>
          <h1>Activer le compte</h1>
          <p className="login-sub">Choisissez votre mot de passe pour finaliser votre inscription.</p>

          {lienInvalide ? (
            <div className="login-notice" style={{ background: 'var(--status-critical-soft)' }}>
              <AlertCircle size={14} style={{ color: 'var(--status-critical)' }} />
              <span>Ce lien d'activation est incomplet ou invalide. Demandez à votre administrateur de vous en renvoyer un.</span>
            </div>
          ) : succes ? (
            <div className="login-notice" style={{ background: 'var(--status-ok-soft)' }}>
              <CheckCircle2 size={14} style={{ color: 'var(--status-ok)' }} />
              <span>Compte activé avec succès.</span>
            </div>
          ) : (
            <>
              <div className="form-group">
                <label className="form-label">Mot de passe</label>
                <div className="input-icon-wrap">
                  <Lock size={17} />
                  <input
                    type="password"
                    className="form-control"
                    style={{ paddingLeft: '2.4rem' }}
                    placeholder="••••••••"
                    value={motDePasse}
                    onChange={(e) => setMotDePasse(e.target.value)}
                    autoComplete="new-password"
                  />
                </div>
              </div>

              <div className="form-group">
                <label className="form-label">Confirmer le mot de passe</label>
                <div className="input-icon-wrap">
                  <Lock size={17} />
                  <input
                    type="password"
                    className="form-control"
                    style={{ paddingLeft: '2.4rem' }}
                    placeholder="••••••••"
                    value={confirmation}
                    onChange={(e) => setConfirmation(e.target.value)}
                    autoComplete="new-password"
                  />
                </div>
                {motsDePasseDifferents && (
                  <p style={{ color: 'var(--status-critical)', fontSize: '0.78rem', marginTop: '0.4rem' }}>
                    Les mots de passe ne correspondent pas.
                  </p>
                )}
              </div>

              {erreur && (
                <div style={{ display: 'flex', alignItems: 'center', gap: '0.4rem', color: 'var(--status-critical)', fontSize: '0.82rem', marginBottom: '1rem' }}>
                  <AlertCircle size={14} />
                  <span>{erreur}</span>
                </div>
              )}

              <button type="submit" className="btn btn-primary" style={{ width: '100%', padding: '0.85rem' }} disabled={loading || motsDePasseDifferents}>
                {loading ? <Loader2 size={17} className="spin" /> : <ArrowRight size={17} />}
                <span>{loading ? 'Activation...' : 'Activer mon compte'}</span>
              </button>
            </>
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