import React, { useState, useEffect, useCallback } from 'react';
import { UserPlus, Loader2, AlertCircle, Copy, Check, ShieldOff, ShieldAlert, MailCheck } from 'lucide-react';
import { dqeService } from '../api/dqeService';

const ROLES = [
  { value: 'technicien', label: 'Technicien' },
  { value: 'ingenieur', label: 'Ingénieur' },
  { value: 'admin', label: 'Admin' },
];

function CopyBox({ texte }) {
  const [copie, setCopie] = useState(false);
  return (
    <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', background: 'var(--core-bg)', border: '1px solid var(--core-border)', borderRadius: 'var(--radius-md)', padding: '0.6rem 0.8rem' }}>
      <code style={{ fontSize: '0.78rem', flex: 1, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{texte}</code>
      <button
        type="button"
        className="btn btn-secondary"
        style={{ padding: '0.3rem 0.6rem', fontSize: '0.75rem', flexShrink: 0 }}
        onClick={() => {
          navigator.clipboard?.writeText(window.location.origin + texte);
          setCopie(true);
          setTimeout(() => setCopie(false), 1500);
        }}
      >
        {copie ? <Check size={13} /> : <Copy size={13} />}
        <span>{copie ? 'Copié' : 'Copier'}</span>
      </button>
    </div>
  );
}

export default function TeamManagementView({ moiProfil }) {
  const [membres, setMembres] = useState([]);
  const [chargement, setChargement] = useState(true);
  const [erreurListe, setErreurListe] = useState(null);

  const [emailInvite, setEmailInvite] = useState('');
  const [roleInvite, setRoleInvite] = useState('technicien');
  const [invitationEnCours, setInvitationEnCours] = useState(false);
  const [erreurInvitation, setErreurInvitation] = useState(null);
  const [dernierLien, setDernierLien] = useState(null);
  const [dernierEmailEnvoye, setDernierEmailEnvoye] = useState(false);
  const [dernierEmailInvite, setDernierEmailInvite] = useState('');

  const [desactivationEnCours, setDesactivationEnCours] = useState(null);

  const chargerMembres = useCallback(async () => {
    setChargement(true);
    setErreurListe(null);
    try {
      const data = await dqeService.listerMembres();
      setMembres(data);
    } catch (err) {
      setErreurListe(
        err.status === 403
          ? "Cette page est réservée aux comptes Admin du cabinet."
          : (err.message || 'Impossible de charger les membres.')
      );
    } finally {
      setChargement(false);
    }
  }, []);

  useEffect(() => { chargerMembres(); }, [chargerMembres]);

  const handleInviter = async (e) => {
    e.preventDefault();
    if (!emailInvite.trim()) return;
    setInvitationEnCours(true);
    setErreurInvitation(null);
    setDernierLien(null);
    setDernierEmailEnvoye(false);
    const emailCible = emailInvite.trim();
    try {
      const res = await dqeService.inviterUtilisateur({ email: emailCible, role: roleInvite });
      setDernierLien(res.lien_activation);
      setDernierEmailEnvoye(Boolean(res.email_envoye));
      setDernierEmailInvite(emailCible);
      setEmailInvite('');
      chargerMembres();
    } catch (err) {
      const d = err.data || {};
      setErreurInvitation(d.email || d.role || err.message || "Impossible d'inviter cet utilisateur.");
    } finally {
      setInvitationEnCours(false);
    }
  };

  const handleDesactiver = async (userId) => {
    setDesactivationEnCours(userId);
    try {
      await dqeService.desactiverMembre(userId);
      chargerMembres();
    } catch (err) {
      setErreurListe(err.message || 'Impossible de désactiver ce membre.');
    } finally {
      setDesactivationEnCours(null);
    }
  };

  if (moiProfil && moiProfil.role !== 'admin') {
    return (
      <div className="glass-panel" style={{ display: 'flex', alignItems: 'center', gap: '0.75rem', color: 'var(--status-warn)' }}>
        <ShieldAlert size={20} />
        <span>Cette page est réservée aux comptes Admin du cabinet.</span>
      </div>
    );
  }

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '1.75rem' }}>
      <div>
        <h2 style={{ fontSize: '1.5rem', fontWeight: 700, fontFamily: 'var(--font-heading)' }}>Gestion de l'équipe</h2>
        <p style={{ color: 'var(--ink-500)', fontSize: '0.9rem', marginTop: '0.3rem' }}>
          Invitez des membres et gérez les accès de votre cabinet.
        </p>
      </div>

      {/* Invitation */}
      <div className="glass-panel">
        <h3 style={{ fontSize: '1rem', fontWeight: 600, marginBottom: '1rem' }}>Inviter un membre</h3>
        <form onSubmit={handleInviter} style={{ display: 'flex', gap: '0.75rem', flexWrap: 'wrap', alignItems: 'flex-end' }}>
          <div style={{ flex: '1 1 260px' }}>
            <label className="form-label">Email professionnel</label>
            <input
              type="email"
              className="form-control"
              placeholder="collegue@entreprise.com"
              value={emailInvite}
              onChange={(e) => setEmailInvite(e.target.value)}
            />
          </div>
          <div style={{ width: '180px' }}>
            <label className="form-label">Rôle</label>
            <select className="form-select" value={roleInvite} onChange={(e) => setRoleInvite(e.target.value)}>
              {ROLES.map((r) => <option key={r.value} value={r.value}>{r.label}</option>)}
            </select>
          </div>
          <button type="submit" className="btn btn-primary" disabled={invitationEnCours || !emailInvite.trim()}>
            {invitationEnCours ? <Loader2 size={16} className="spin" /> : <UserPlus size={16} />}
            <span>{invitationEnCours ? 'Envoi...' : 'Inviter'}</span>
          </button>
        </form>

        {erreurInvitation && (
          <div style={{ display: 'flex', alignItems: 'center', gap: '0.4rem', color: 'var(--status-critical)', fontSize: '0.82rem', marginTop: '0.85rem' }}>
            <AlertCircle size={14} />
            <span>{[].concat(erreurInvitation).join(' ')}</span>
          </div>
        )}

        {dernierLien && (
          <div style={{ marginTop: '1rem' }}>
            {dernierEmailEnvoye ? (
              <div style={{ display: 'flex', alignItems: 'center', gap: '0.4rem', color: 'var(--status-success, #16a34a)', fontSize: '0.85rem' }}>
                <MailCheck size={15} />
                <span>Email d'invitation envoyé à {dernierEmailInvite}.</span>
              </div>
            ) : (
              <>
                <p style={{ fontSize: '0.82rem', color: 'var(--ink-700)', marginBottom: '0.5rem' }}>
                  Compte créé. Aucun email n'est envoyé (pas de serveur SMTP configuré) -- transmettez ce lien vous-même :
                </p>
                <CopyBox texte={dernierLien} />
              </>
            )}
          </div>
        )}
      </div>

      {/* Liste des membres */}
      <div className="glass-panel">
        <h3 style={{ fontSize: '1rem', fontWeight: 600, marginBottom: '1rem' }}>Membres du cabinet</h3>

        {erreurListe && (
          <div style={{ display: 'flex', alignItems: 'center', gap: '0.4rem', color: 'var(--status-critical)', fontSize: '0.85rem', marginBottom: '1rem' }}>
            <AlertCircle size={14} />
            <span>{erreurListe}</span>
          </div>
        )}

        {chargement ? (
          <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', color: 'var(--ink-500)', padding: '1rem 0' }}>
            <Loader2 size={16} className="spin" /> Chargement...
          </div>
        ) : membres.length === 0 ? (
          !erreurListe && <p style={{ color: 'var(--ink-500)', fontSize: '0.85rem' }}>Aucun membre trouvé.</p>
        ) : (
          <table className="custom-table">
            <thead>
              <tr>
                <th>Utilisateur</th>
                <th>Email</th>
                <th>Rôle</th>
                <th>Statut</th>
                <th></th>
              </tr>
            </thead>
            <tbody>
              {membres.map((m) => (
                <tr key={m.id}>
                  <td style={{ fontWeight: 600 }}>{m.username}</td>
                  <td>{m.email || '—'}</td>
                  <td><span className="badge badge-info">{m.role_display}</span></td>
                  <td>
                    <span className={m.actif ? 'badge badge-success' : 'badge badge-locked'}>
                      {m.actif ? 'Actif' : 'Désactivé'}
                    </span>
                  </td>
                  <td>
                    {m.id !== moiProfil?.id && m.actif && (
                      <button
                        className="btn btn-secondary"
                        style={{ padding: '0.35rem 0.7rem', fontSize: '0.78rem' }}
                        disabled={desactivationEnCours === m.id}
                        onClick={() => handleDesactiver(m.id)}
                      >
                        {desactivationEnCours === m.id ? <Loader2 size={13} className="spin" /> : <ShieldOff size={13} />}
                        <span>Désactiver</span>
                      </button>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>
    </div>
  );
}