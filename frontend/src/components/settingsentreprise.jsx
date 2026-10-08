import React, { useEffect, useRef, useState } from 'react';
import { Building2, UploadCloud, Save, Loader2, Image as ImageIcon, Coins } from 'lucide-react';
import { dqeService } from '../api/dqeService';
import useReferentiel from '../hooks/useReferentiel';
import Alerte from './ui/Alerte';

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
  nature_prix: 'vente_ht',
  taux_marge_pct: '',
  taux_tva_pct: '',
};

// Unité affichée à partir du suffixe de la clé du barème (beton_m3...).
const uniteDeCle = (cle) => {
  const suffixe = cle.split('_').pop();
  return { m3: 'FCFA / m³', m2: 'FCFA / m²', kg: 'FCFA / kg', ml: 'FCFA / ml', u: 'FCFA / u' }[suffixe] || 'FCFA';
};

export default function SettingsEntreprise({ estAdmin }) {
  const { data: referentiel, erreur: erreurReferentiel } = useReferentiel();
  const [champs, setChamps] = useState(CHAMPS_VIDES);
  const [prix, setPrix] = useState({});
  const [meta, setMeta] = useState({});
  const [origines, setOrigines] = useState({});
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
          nature_prix: data.nature_prix || 'vente_ht',
          taux_marge_pct: data.taux_marge_pct ?? '',
          taux_tva_pct: data.taux_tva_pct ?? '',
        });
        setMeta(data.prix_unitaires_meta || {});
        setLogoUrl(data.logo || null);
        setPrix(data.prix_unitaires || {});
      })
      .catch((err) => {
        if (!annule) setErreur(`Impossible de charger les paramètres du cabinet : ${err.message}`);
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

  // Champ vide = prix NON RENSEIGNÉ : aucun DQE ne pourra utiliser ce poste
  // (le moteur n'a plus de barème par défaut).
  const handlePrix = (cle) => (e) => {
    setSucces(false);
    const valeur = e.target.value;
    setOrigines((o) => { const n = { ...o }; delete n[cle]; return n; });
    setPrix((prev) => {
      const suivant = { ...prev };
      if (valeur === '') {
        delete suivant[cle];
      } else {
        suivant[cle] = Number(valeur);
      }
      return suivant;
    });
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
      const data = await dqeService.updateEntreprise({ ...champs, prix_unitaires: prix, prix_origines: origines }, logoFile);
      setMeta(data.prix_unitaires_meta || {});
      setOrigines({});
      setLogoUrl(data.logo || logoUrl);
      setPrix(data.prix_unitaires || prix);
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
  const clesPrix = referentiel?.cles_prix || [];
  const reference = referentiel?.prix_reference;
  const manquants = clesPrix.filter(({ cle }) => prix[cle] === undefined || prix[cle] === null || prix[cle] === '');

  // Pré-remplissage EXPLICITE (bouton) avec le barème de référence documenté,
  // uniquement pour les champs vides. Rien n'est enregistré sans « Enregistrer ».
  const preremplir = () => {
    setSucces(false);
    setPrix((prev) => {
      const suivant = { ...prev };
      const marques = {};
      Object.entries(reference?.valeurs || {}).forEach(([cle, v]) => {
        if (suivant[cle] === undefined || suivant[cle] === '' || suivant[cle] === null) {
          suivant[cle] = v;
          marques[cle] = 'reference';
        }
      });
      setOrigines((o) => ({ ...o, ...marques }));
      return suivant;
    });
  };

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

      {erreur && <Alerte type="erreur">{erreur}</Alerte>}
      {succes && <Alerte type="succes">Paramètres enregistrés.</Alerte>}
      {!estAdmin && <Alerte type="info">Lecture seule : seul un administrateur du cabinet peut modifier ces paramètres.</Alerte>}

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
          <label className="form-label" htmlFor="ent-nom">Nom de l'entreprise</label>
          <input id="ent-nom" disabled={!estAdmin} type="text" className="form-control" value={champs.nom} onChange={handleChamp('nom')} placeholder="ex: BATI-PRO SARL" />
        </div>
        <div className="form-group">
          <label className="form-label" htmlFor="ent-siege_social">Siège social</label>
          <input id="ent-siege_social" disabled={!estAdmin} type="text" className="form-control" value={champs.siege_social} onChange={handleChamp('siege_social')} placeholder="ex: Cocody, Abidjan" />
        </div>
        <div className="form-group">
          <label className="form-label" htmlFor="ent-telephone">Téléphone</label>
          <input id="ent-telephone" disabled={!estAdmin} type="text" className="form-control" value={champs.telephone} onChange={handleChamp('telephone')} placeholder="ex: 07 00 00 00 00" />
        </div>
        <div className="form-group">
          <label className="form-label" htmlFor="ent-email">Email</label>
          <input id="ent-email" disabled={!estAdmin} type="email" className="form-control" value={champs.email} onChange={handleChamp('email')} placeholder="ex: contact@entreprise.ci" />
        </div>
        <div className="form-group">
          <label className="form-label" htmlFor="ent-site_web">Site web</label>
          <input id="ent-site_web" disabled={!estAdmin} type="text" className="form-control" value={champs.site_web} onChange={handleChamp('site_web')} placeholder="ex: www.entreprise.ci" />
        </div>
        <div className="form-group">
          <label className="form-label" htmlFor="ent-capital_social">Capital social</label>
          <input id="ent-capital_social" disabled={!estAdmin} type="text" className="form-control" value={champs.capital_social} onChange={handleChamp('capital_social')} placeholder="ex: 1 000 000 FCFA" />
        </div>
        <div className="form-group">
          <label className="form-label" htmlFor="ent-rccm">N° R.C.C.M</label>
          <input id="ent-rccm" disabled={!estAdmin} type="text" className="form-control" value={champs.rccm} onChange={handleChamp('rccm')} placeholder="ex: CI-ABJ-2024-B-1234" />
        </div>
        <div className="form-group">
          <label className="form-label" htmlFor="ent-cc">CC N°</label>
          <input id="ent-cc" disabled={!estAdmin} type="text" className="form-control" value={champs.cc} onChange={handleChamp('cc')} />
        </div>
        <div className="form-group">
          <label className="form-label" htmlFor="ent-cb">CB N°</label>
          <input id="ent-cb" disabled={!estAdmin} type="text" className="form-control" value={champs.cb} onChange={handleChamp('cb')} />
        </div>
      </div>

      <div style={{ display: 'flex', alignItems: 'center', gap: '0.75rem', margin: '2rem 0 0.5rem' }}>
        <div style={{ width: '36px', height: '36px', borderRadius: '10px', background: 'var(--accent-primary)', display: 'flex', alignItems: 'center', justifyContent: 'center', color: 'white' }}>
          <Coins size={20} />
        </div>
        <h2 style={{ fontSize: '1.4rem', fontWeight: 700 }}>Tarifs du cabinet</h2>
      </div>
      <p className="texte-discret">
        Ces prix sont propres à votre cabinet. Un prix non renseigné bloque le DQE des ouvrages qui l'utilisent :
        le logiciel n'applique jamais de prix par défaut.
      </p>
      {erreurReferentiel && <Alerte type="erreur">Liste des prix indisponible : {erreurReferentiel}</Alerte>}
      {manquants.length > 0 && (
        <Alerte type="attention" titre={`${manquants.length} prix non renseigné(s)`}
          action={estAdmin && reference ? { libelle: 'Pré-remplir avec le barème de référence', onClick: preremplir } : undefined}>
          {reference && <>Barème de référence disponible : {reference.source}. Vérifiez chaque valeur avant d'enregistrer.</>}
          {reference?.avertissements?.length > 0 && <ul className="alerte-liste">{reference.avertissements.map((a) => <li key={a}>{a}</li>)}</ul>}
        </Alerte>
      )}
      <div className="grid-2">
        {clesPrix.map(({ cle, libelle }) => (
          <div className="form-group" key={cle}>
            <label className="form-label" htmlFor={`prix-${cle}`}>{libelle} <span className="texte-discret">({uniteDeCle(cle)})</span></label>
            <input id={`prix-${cle}`} type="number" min="0" step="1" className="form-control" disabled={!estAdmin}
              value={prix[cle] ?? ''} onChange={handlePrix(cle)} placeholder="Non renseigné : bloque le DQE" />
            <small className="aide-champ">
              {origines[cle] === 'reference' ? 'Pré-rempli avec le barème de référence — non enregistré'
                : meta[cle] ? `${meta[cle].source === 'reference' ? 'Barème de référence' : 'Saisi'} le ${meta[cle].date}${meta[cle].auteur ? ` par ${meta[cle].auteur}` : ''}`
                  : prix[cle] != null && prix[cle] !== '' ? 'Date de saisie non tracée (antérieure au suivi)' : ''}
            </small>
          </div>
        ))}
      </div>

      <h3 className="sous-titre">Prix de vente et taxes</h3>
      <div className="grid-3">
        <div className="form-group">
          <label className="form-label" htmlFor="ent-nature">Nature des prix du barème</label>
          <select id="ent-nature" className="form-select" disabled={!estAdmin} value={champs.nature_prix} onChange={handleChamp('nature_prix')}>
            <option value="vente_ht">Prix de vente HT (fourni-posé)</option>
            <option value="debourse_sec">Déboursé sec (coût de revient)</option>
          </select>
        </div>
        <div className="form-group">
          <label className="form-label" htmlFor="ent-marge">Marge sur déboursé (%)</label>
          <input id="ent-marge" type="number" min="0" step="0.1" className="form-control" disabled={!estAdmin || champs.nature_prix !== 'debourse_sec'}
            value={champs.taux_marge_pct} onChange={handleChamp('taux_marge_pct')} placeholder="non renseignée" />
        </div>
        <div className="form-group">
          <label className="form-label" htmlFor="ent-tva">TVA (%)</label>
          <input id="ent-tva" type="number" min="0" max="100" step="0.1" className="form-control" disabled={!estAdmin}
            value={champs.taux_tva_pct} onChange={handleChamp('taux_tva_pct')} placeholder="vide : TTC non calculé" />
        </div>
      </div>

      <div style={{ display: 'flex', justifyContent: 'flex-end', marginTop: '0.5rem' }}>
        <button type="button" className="btn btn-primary" onClick={handleEnregistrer} disabled={enregistrement || !estAdmin}>
          {enregistrement ? <Loader2 size={18} className="spin" /> : <Save size={18} />}
          <span>{enregistrement ? 'Enregistrement...' : 'Enregistrer'}</span>
        </button>
      </div>
    </div>
  );
}