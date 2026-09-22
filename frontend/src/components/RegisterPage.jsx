import React, { useState } from 'react';
import { Compass, Building2, Mail, Lock, User, ArrowRight, Loader2, AlertCircle } from 'lucide-react';
import { dqeService } from '../api/dqeService';

export default function RegisterPage({ onEnterApp, onBackToLanding, onGoToLogin }) {
  const [nomEntreprise, setNomEntreprise] = useState('');
  const [nomContact, setNomContact] = useState('');
  const [email, setEmail] = useState('');
  const [motDePasse, setMotDePasse] = useState('');
  const [confirmation, setConfirmation] = useState('');
  const [loading, setLoading] = useState(false);
  const [erreurs, setErreurs] = useState({});

  const motsDePasseDifferents = motDePasse.length > 0 && confirmation.length > 0 && motDePasse !== confirmation;

  // Inscription réelle -- crée l'entreprise + le premier compte Admin
  // (voir projets/auth_views.py::InscriptionEntrepriseView). Pas de champ
  // "username" séparé dans ce formulaire : l'email sert d'identifiant.
  const handleSubmit = async (e) => {
    e.preventDefault();
    if (motsDePasseDifferents) return;
    setErreurs({});
    setLoading(true);
    try {
      await dqeService.inscription({
        nomEntreprise,
        username: email,
        email,
        motDePasse,
      });
      onEnterApp();
    } catch (err) {
      // err.data : erreurs par champ renvoyées par le backend
      // (nom_entreprise, username, mot_de_passe...) -- on les remappe sur
      // les noms de champs de ce formulaire.
      const d = err.data || {};
      setErreurs({
        nomEntreprise: d.nom_entreprise,
        email: d.username || d.email,
        motDePasse: d.mot_de_passe,
        generale: !d.nom_entreprise && !d.username && !d.mot_de_passe ? (err.message || 'Inscription impossible.') : null,
      });
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
          <h2>Un espace par cabinet.</h2>
          <p>
            Créez le compte de votre entreprise : vos projets, vos
            paramètres et vos devis restent isolés des autres cabinets.
          </p>
        </div>
      </div>

      <div className="login-form-side">
        <form className="login-form fade-in-up" onSubmit={handleSubmit}>
          <button type="button" className="login-back" onClick={onBackToLanding}>← Retour</button>
          <h1>Créer un compte</h1>
          <p className="login-sub">Inscrivez votre entreprise sur BTP Innovation Ivoire.</p>

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
            {erreurs.nomEntreprise && (
              <p style={{ color: 'var(--status-critical)', fontSize: '0.78rem', marginTop: '0.4rem' }}>
                {[].concat(erreurs.nomEntreprise).join(' ')}
              </p>
            )}
          </div>

          <div className="form-group">
            <label className="form-label">Nom du contact principal</label>
            <div className="input-icon-wrap">
              <User size={17} />
              <input
                className="form-control"
                style={{ paddingLeft: '2.4rem' }}
                placeholder="ex : Prénom Nom"
                value={nomContact}
                onChange={(e) => setNomContact(e.target.value)}
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
                autoComplete="username"
              />
            </div>
            {erreurs.email && (
              <p style={{ color: 'var(--status-critical)', fontSize: '0.78rem', marginTop: '0.4rem' }}>
                {[].concat(erreurs.email).join(' ')}
              </p>
            )}
          </div>

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
            {erreurs.motDePasse && (
              <p style={{ color: 'var(--status-critical)', fontSize: '0.78rem', marginTop: '0.4rem' }}>
                {[].concat(erreurs.motDePasse).join(' ')}
              </p>
            )}
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
              />
            </div>
            {motsDePasseDifferents && (
              <p style={{ color: 'var(--status-critical)', fontSize: '0.78rem', marginTop: '0.4rem' }}>
                Les mots de passe ne correspondent pas.
              </p>
            )}
          </div>

          {erreurs.generale && (
            <div style={{ display: 'flex', alignItems: 'center', gap: '0.4rem', color: 'var(--status-critical)', fontSize: '0.82rem', marginBottom: '1rem' }}>
              <AlertCircle size={14} />
              <span>{erreurs.generale}</span>
            </div>
          )}

          <button type="submit" className="btn btn-primary" style={{ width: '100%', padding: '0.85rem' }} disabled={motsDePasseDifferents || loading}>
            {loading ? <Loader2 size={17} className="spin" /> : <ArrowRight size={17} />}
            <span>{loading ? 'Création...' : 'Créer le compte'}</span>
          </button>

          <p className="login-switch">
            Déjà un compte ?{' '}
            <button type="button" className="login-link-inline" onClick={onGoToLogin}>
              Se connecter
            </button>
          </p>
        </form>
      </div>
    </div>
  );
}