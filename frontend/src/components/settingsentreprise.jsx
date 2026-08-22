import React, { useEffect, useRef, useState } from 'react';
import { Building2, UploadCloud, Save, Loader2, CheckCircle2, AlertCircle, Image as ImageIcon } from 'lucide-react';
import { dqeService } from '../api/dqeService';

const CHAMPS_VIDES = {
  nom: '',
  siege_social: '',
  telephone: '',
  email: '',
  site_web: '',
  rccm: '',
  cc: '',
  cb: '',
  capital_social: '',
};

// Paramètres d'en-tête (logo + coordonnées) utilisés sur les exports
// DQE PDF/Excel -- voir projets/models.py::EntrepriseParametres et
// projets/services/dqe_exporters.py côté backend.
export default function SettingsEntreprise() {
  const [champs, setChamps] = useState(CHAMPS_VIDES);
  const [logoUrl, setLogoUrl] = useState(null);
  const [logoFile, setLogoFile] = useState(null);
  const [logoPreview, setLogoPreview] = useState(null);
  const [chargement, setChargement] = useState(true);
  const [enregistrement, setEnregistrement] = useState(false);
  const [erreur, setErreur] = useState(null);
  const [succes, setSucces] = useState(false);
  const fileInputRef = useRef(null);

  useEffect(() => {
    let annule = false;
    dqeService.getEntreprise()
      .then((data) => {
        if (annule || !data) return;
        setChamps({
          nom: data.nom || '',
          siege_social: data.siege_social || '',
          telephone: data.telephone || '',
          email: data.email || '',
          site_web: data.site_web || '',
          rccm: data.rccm || '',
          cc: data.cc || '',
          cb: data.cb || '',
          capital_social: data.capital_social || '',
        });
        setLogoUrl(data.logo || null);
      })
      .catch((err) => {
        if (!annule) setErreur(`Impossible de charger les paramètres : ${err.message}`);
      })
      .finally(() => {
        if (!annule) setChargement(false);
      });
    return () => { annule = true; };
  }, []);

  const handleChamp = (cle) => (e) => {
    setSucces(false);
    setChamps((prev) => ({ ...prev, [cle]: e.target.value }));
  };

  const handleLogoChange = (e) => {
    const file = e.target.files && e.target.files[0];
    if (!file) return;
    if (!file.type.startsWith('image/')) {
      setErreur("Le logo doit être une image (PNG, JPG...).");
      return;
    }
    setErreur(null);
    setSucces(false);
    setLogoFile(file);
    setLogoPreview(URL.createObjectURL(file));
  };

  const handleEnregistrer = async () => {
    setErreur(null);
    setSucces(false);
    setEnregistrement(true);
    try {
      const data = await dqeService.updateEntreprise(champs, logoFile);
      setLogoUrl(data.logo || logoUrl);
      setLogoFile(null);
      setLogoPreview(null);
      setSucces(true);
    } catch (err) {
      setErreur(`Échec de l'enregistrement : ${err.message}`);
    } finally {
      setEnregistrement(false);
    }
  };

  const apercuLogo = logoPreview || logoUrl;

  if (chargement) {
    return (
      <div className="glass-panel" style={{ display: 'flex', alignItems: 'center', gap: '0.75rem' }}>
        <Loader2 size={20} className="spin" />
        <span style={{ color: 'var(--text-muted)' }}>Chargement des paramètres entreprise...</span>
      </div>
    );
  }

  return (
    <div className="glass-panel">
      <div style={{ display: 'flex', alignItems: 'center', gap: '0.75rem', marginBottom: '0.5rem' }}>
        <div style={{ width: '36px', height: '36px', borderRadius: '10px', background: 'var(--accent-primary)', display: 'flex', alignItems: 'center', justifyContent: 'center', color: 'white' }}>
          <Building2 size={20} />
        </div>
        <h2 style={{ fontSize: '1.4rem', fontWeight: 700 }}>Paramètres Entreprise</h2>
      </div>
      <p style={{ color: 'var(--text-muted)', fontSize: '0.9rem', marginBottom: '2rem' }}>
        Votre logo et vos coordonnées apparaîtront en en-tête de tous les exports DQE (PDF et Excel).
      </p>

      {erreur && (
        <div style={{ padding: '1rem 1.25rem', borderRadius: '12px', background: 'rgba(239, 68, 68, 0.1)', border: '1px solid rgba(239, 68, 68, 0.35)', marginBottom: '1.5rem', display: 'flex', alignItems: 'flex-start', gap: '0.75rem' }}>
          <AlertCircle size={20} color="#ef4444" style={{ flexShrink: 0, marginTop: '0.1rem' }} />
          <span style={{ fontSize: '0.88rem', color: '#fca5a5' }}>{erreur}</span>
        </div>
      )}

      {succes && (
        <div style={{ padding: '1rem 1.25rem', borderRadius: '12px', background: 'rgba(16, 185, 129, 0.1)', border: '1px solid rgba(16, 185, 129, 0.35)', marginBottom: '1.5rem', display: 'flex', alignItems: 'center', gap: '0.75rem' }}>
          <CheckCircle2 size={20} color="#10b981" style={{ flexShrink: 0 }} />
          <span style={{ fontSize: '0.88rem', color: '#6ee7b7' }}>Paramètres enregistrés.</span>
        </div>
      )}

      {/* Logo */}
      <div className="form-group">
        <label className="form-label">Logo de l'entreprise</label>
        <div style={{ display: 'flex', alignItems: 'center', gap: '1.25rem' }}>
          <div
            style={{
              width: '110px',
              height: '80px',
              borderRadius: '12px',
              border: '1px dashed var(--core-border)',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              overflow: 'hidden',
              background: 'rgba(255,255,255,0.02)',
              flexShrink: 0,
            }}
          >
            {apercuLogo ? (
              <img src={apercuLogo} alt="Logo entreprise" style={{ maxWidth: '100%', maxHeight: '100%', objectFit: 'contain' }} />
            ) : (
              <ImageIcon size={24} color="var(--text-muted)" />
            )}
          </div>
          <div>
            <input
              ref={fileInputRef}
              type="file"
              accept="image/*"
              onChange={handleLogoChange}
              style={{ display: 'none' }}
            />
            <button type="button" className="btn btn-secondary" onClick={() => fileInputRef.current?.click()}>
              <UploadCloud size={16} />
              <span>{apercuLogo ? 'Changer le logo' : 'Choisir un logo'}</span>
            </button>
            <p style={{ fontSize: '0.78rem', color: 'var(--text-muted)', marginTop: '0.5rem' }}>
              PNG ou JPG, fond transparent de préférence.
            </p>
          </div>
        </div>
      </div>

      <div className="grid-2">
        <div className="form-group">
          <label className="form-label">Nom de l'entreprise</label>
          <input type="text" className="form-control" value={champs.nom} onChange={handleChamp('nom')} placeholder="ex: BATI-PRO SARL" />
        </div>
        <div className="form-group">
          <label className="form-label">Siège social</label>
          <input type="text" className="form-control" value={champs.siege_social} onChange={handleChamp('siege_social')} placeholder="ex: Cocody, Abidjan" />
        </div>
        <div className="form-group">
          <label className="form-label">Téléphone</label>
          <input type="text" className="form-control" value={champs.telephone} onChange={handleChamp('telephone')} placeholder="ex: 07 00 00 00 00" />
        </div>
        <div className="form-group">
          <label className="form-label">Email</label>
          <input type="email" className="form-control" value={champs.email} onChange={handleChamp('email')} placeholder="ex: contact@entreprise.ci" />
        </div>
        <div className="form-group">
          <label className="form-label">Site web</label>
          <input type="text" className="form-control" value={champs.site_web} onChange={handleChamp('site_web')} placeholder="ex: www.entreprise.ci" />
        </div>
        <div className="form-group">
          <label className="form-label">Capital social</label>
          <input type="text" className="form-control" value={champs.capital_social} onChange={handleChamp('capital_social')} placeholder="ex: 1 000 000 FCFA" />
        </div>
        <div className="form-group">
          <label className="form-label">N° R.C.C.M</label>
          <input type="text" className="form-control" value={champs.rccm} onChange={handleChamp('rccm')} placeholder="ex: CI-ABJ-2024-B-1234" />
        </div>
        <div className="form-group">
          <label className="form-label">CC N°</label>
          <input type="text" className="form-control" value={champs.cc} onChange={handleChamp('cc')} />
        </div>
        <div className="form-group">
          <label className="form-label">CB N°</label>
          <input type="text" className="form-control" value={champs.cb} onChange={handleChamp('cb')} />
        </div>
      </div>

      <div style={{ display: 'flex', justifyContent: 'flex-end', marginTop: '0.5rem' }}>
        <button className="btn btn-primary" onClick={handleEnregistrer} disabled={enregistrement}>
          {enregistrement ? <Loader2 size={18} className="spin" /> : <Save size={18} />}
          <span>{enregistrement ? 'Enregistrement...' : 'Enregistrer'}</span>
        </button>
      </div>
    </div>
  );
}