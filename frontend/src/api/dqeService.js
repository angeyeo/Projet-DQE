// Service API du frontend DQE -- SEULE porte d'accès au backend Django.
//
// Règles :
// - aucune valeur par défaut inventée : un champ non saisi est envoyé à
//   null (ou omis) et c'est le backend qui répond avec la liste explicite
//   de ce qui manque ;
// - aucun calcul métier ici : les quantités, montants, épaisseurs, charges
//   viennent des réponses de l'API ;
// - toute erreur est transformée en Error lisible (champ `message`) avec
//   les détails structurés du backend dans `err.data` (champs_manquants,
//   problemes, erreurs par champ...).

const API_BASE_URL = (import.meta.env.VITE_API_URL || '/api').replace(/\/$/, '');

// --- Authentification JWT ------------------------------------------------

const ACCESS_KEY = 'dqe_access_token';
const REFRESH_KEY = 'dqe_refresh_token';

const lireStockage = (cle) => {
  try { return localStorage.getItem(cle); } catch { return null; }
};
const ecrireStockage = (cle, valeur) => {
  try {
    if (valeur === null || valeur === undefined) localStorage.removeItem(cle);
    else localStorage.setItem(cle, valeur);
  } catch { /* stockage indisponible (navigation privée) : session non persistée */ }
};

function getAccessToken() { return lireStockage(ACCESS_KEY); }
function getRefreshToken() { return lireStockage(REFRESH_KEY); }

function setTokens({ access, refresh }) {
  if (access) ecrireStockage(ACCESS_KEY, access);
  if (refresh) ecrireStockage(REFRESH_KEY, refresh);
}

function clearTokens() {
  ecrireStockage(ACCESS_KEY, null);
  ecrireStockage(REFRESH_KEY, null);
}

function isAuthenticated() {
  return !!getAccessToken();
}

async function rafraichirToken() {
  const refresh = getRefreshToken();
  if (!refresh) return null;
  try {
    const response = await fetch(`${API_BASE_URL}/auth/token/refresh/`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ refresh }),
    });
    if (!response.ok) return null;
    const data = await response.json();
    setTokens({ access: data.access, refresh: data.refresh });
    return data.access;
  } catch {
    return null;
  }
}

async function publicFetch(url, options = {}) {
  try {
    return await fetch(url, options);
  } catch {
    throw erreurReseau();
  }
}

async function apiFetch(url, options = {}) {
  const access = getAccessToken();
  const headers = { ...(options.headers || {}) };
  if (access) headers.Authorization = `Bearer ${access}`;

  let response;
  try {
    response = await fetch(url, { ...options, headers });
    if (response.status === 401 && getRefreshToken()) {
      const nouvelAccess = await rafraichirToken();
      if (nouvelAccess) {
        response = await fetch(url, {
          ...options,
          headers: { ...(options.headers || {}), Authorization: `Bearer ${nouvelAccess}` },
        });
      }
    }
  } catch {
    throw erreurReseau();
  }

  if (response.status === 401) {
    clearTokens();
    window.dispatchEvent(new CustomEvent('dqe:auth-expired'));
  }
  return response;
}

// --- Erreurs lisibles ------------------------------------------------------

function erreurReseau() {
  const err = new Error(
    "Serveur injoignable : vérifiez votre connexion ou réessayez dans un instant."
  );
  err.status = 0;
  return err;
}

const MESSAGES_STATUT = {
  401: 'Votre session a expiré : reconnectez-vous.',
  403: "Vous n'avez pas les droits nécessaires pour cette action.",
  404: 'Élément introuvable (supprimé, ou appartenant à un autre cabinet).',
  409: "Action impossible dans l'état actuel de l'élément.",
  413: 'Fichier trop volumineux.',
  429: 'Trop de requêtes : patientez quelques instants avant de réessayer.',
  502: 'Le service externe (IA) a renvoyé une erreur.',
  503: 'Service momentanément indisponible sur le serveur.',
};

// Transforme n'importe quelle réponse d'erreur DRF en phrase lisible.
export function messageErreur(data, status) {
  if (data) {
    if (typeof data === 'string') return data;
    if (data.erreur) return data.erreur;
    if (data.detail) return data.detail;
    if (Array.isArray(data)) return data.join(' ');
    // Erreurs par champ DRF : {"champ": ["message", ...], ...}
    const parties = Object.entries(data)
      .filter(([, v]) => v && (typeof v === 'string' || Array.isArray(v)))
      .map(([champ, v]) => `${champ === 'non_field_errors' ? '' : `${champ} : `}${[].concat(v).join(' ')}`);
    if (parties.length) return parties.join(' — ');
  }
  return MESSAGES_STATUT[status] || `Erreur inattendue du serveur (code ${status}).`;
}

async function lireReponse(response) {
  if (response.status === 204) return null;
  const data = await response.json().catch(() => null);
  if (!response.ok) {
    const err = new Error(messageErreur(data, response.status));
    err.status = response.status;
    err.data = data;
    throw err;
  }
  return data;
}

const json = (methode, body) => ({
  method: methode,
  headers: { 'Content-Type': 'application/json' },
  body: body !== undefined ? JSON.stringify(body) : undefined,
});

const getJSON = async (url) => lireReponse(await apiFetch(url));
const postJSON = async (url, body) => lireReponse(await apiFetch(url, json('POST', body)));
const patchJSON = async (url, body) => lireReponse(await apiFetch(url, json('PATCH', body)));
const postJSONPublic = async (url, body) => lireReponse(await publicFetch(url, json('POST', body)));

async function telechargerBlob(url, nomParDefaut) {
  const response = await apiFetch(url);
  if (!response.ok) {
    const data = await response.json().catch(() => null);
    const err = new Error(messageErreur(data, response.status));
    err.status = response.status;
    err.data = data;
    throw err;
  }
  const blob = await response.blob();
  const disposition = response.headers.get('Content-Disposition') || '';
  const match = disposition.match(/filename="?([^"]+)"?/);
  const lien = window.URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = lien;
  a.download = match ? match[1] : nomParDefaut;
  document.body.appendChild(a);
  a.click();
  a.remove();
  window.URL.revokeObjectURL(lien);
}

// --- Conversion formulaire -> API (aucune valeur inventée) ---------------

const nombreOuNull = (v) => {
  if (v === '' || v === null || v === undefined) return null;
  const n = Number(v);
  return Number.isFinite(n) ? n : null;
};
const entierOuNull = (v) => {
  const n = nombreOuNull(v);
  return n === null ? null : Math.trunc(n);
};

// Couche de plancher saisie -> format moteur (catalogue OU valeurs explicites).
const versCouche = (c) => {
  const out = { designation: (c.designation || '').trim() || undefined };
  if (c.type) out.type = c.type;
  if (c.poidsSurfacique !== '' && c.poidsSurfacique != null) out.poids_surfacique_kn_m2 = nombreOuNull(c.poidsSurfacique);
  if (c.epaisseur !== '' && c.epaisseur != null) out.epaisseur_m = nombreOuNull(c.epaisseur);
  if (c.poidsVolumique !== '' && c.poidsVolumique != null) out.poids_volumique_kn_m3 = nombreOuNull(c.poidsVolumique);
  return out;
};

export function formulaireVersProjet(f) {
  return {
    nom: (f.nomProjet || '').trim(),
    numero_devis: f.numeroDevis || '',
    usage_batiment: f.typeUsage || '',
    nb_niveaux: entierOuNull(f.nombreNiveaux),
    nb_travees_x: entierOuNull(f.nbTraveesX),
    nb_travees_y: entierOuNull(f.nbTraveesY),
    portee_x: nombreOuNull(f.porteeX),
    portee_y: nombreOuNull(f.porteeY),
    hauteur_etage: nombreOuNull(f.hauteurEtage),
    charge_exploitation: nombreOuNull(f.chargeExploitation),
    contrainte_sol_kn_m2: nombreOuNull(f.contrainteSol),
    charge_permanente_kn_m2: nombreOuNull(f.chargePermanente),
    couches_permanentes: (f.couchesPermanentes || []).map(versCouche),
    methode_semelles: f.methodeSemelles || 'ELU',
    inclure_poids_propre_ossature: !!f.inclurePoidsPropre,
  };
}

const versTexte = (v) => (v === null || v === undefined ? '' : String(v));

export function projetVersFormulaire(p) {
  return {
    id: p.id,
    nomProjet: p.nom || '',
    numeroDevis: p.numero_devis || '',
    typeUsage: p.usage_batiment || '',
    nombreNiveaux: versTexte(p.nb_niveaux),
    nbTraveesX: versTexte(p.nb_travees_x),
    nbTraveesY: versTexte(p.nb_travees_y),
    porteeX: versTexte(p.portee_x),
    porteeY: versTexte(p.portee_y),
    hauteurEtage: versTexte(p.hauteur_etage),
    chargeExploitation: versTexte(p.charge_exploitation),
    contrainteSol: versTexte(p.contrainte_sol_kn_m2),
    chargePermanente: versTexte(p.charge_permanente_kn_m2),
    couchesPermanentes: (p.couches_permanentes || []).map((c) => ({
      type: c.type || '',
      designation: c.designation || '',
      poidsSurfacique: versTexte(c.poids_surfacique_kn_m2),
      epaisseur: versTexte(c.epaisseur_m),
      poidsVolumique: versTexte(c.poids_volumique_kn_m3),
    })),
    methodeSemelles: p.methode_semelles || 'ELU',
    inclurePoidsPropre: !!p.inclure_poids_propre_ossature,
    ifcImporte: !!p.fichier_import_origine,
  };
}

// --- API métier ------------------------------------------------------------

export const dqeService = {
  // Référentiel technique (usages, charges, lots, types de postes, clés de
  // prix) -- source unique : le moteur de calcul côté serveur.
  getReferentiel: async () => getJSON(`${API_BASE_URL}/referentiel/`),

  // Projets
  listerProjets: async () => getJSON(`${API_BASE_URL}/projets/`),
  getProjet: async (projetId) => getJSON(`${API_BASE_URL}/projets/${projetId}/`),
  createProjet: async (formulaire) =>
    postJSON(`${API_BASE_URL}/projets/`, formulaireVersProjet(formulaire)),
  patchProjet: async (projetId, champs) => patchJSON(`${API_BASE_URL}/projets/${projetId}/`, champs),
  supprimerProjet: async (projetId) =>
    lireReponse(await apiFetch(`${API_BASE_URL}/projets/${projetId}/`, { method: 'DELETE' })),

  // Enregistre le formulaire (création ou mise à jour) puis génère les
  // éléments : import IFC confirmé si un plan a été déposé, sinon trame
  // régulière. Renvoie {projetId, hypotheses, avertissements}.
  enregistrerEtGenerer: async (formulaire) => {
    const champs = formulaireVersProjet(formulaire);
    const projet = formulaire.id
      ? await patchJSON(`${API_BASE_URL}/projets/${formulaire.id}/`, champs)
      : await postJSON(`${API_BASE_URL}/projets/`, champs);
    let resultat;
    try {
      resultat = formulaire.ifcImporte
        ? await postJSON(`${API_BASE_URL}/projets/${projet.id}/importer_plan/`, { confirmer: true })
        : await postJSON(`${API_BASE_URL}/projets/${projet.id}/generer_trame/`, undefined);
    } catch (err) {
      // Le projet EST enregistré même si la génération échoue : l'appelant
      // doit le rouvrir, sinon un nouvel essai créerait un doublon.
      err.projetId = projet.id;
      throw err;
    }
    return {
      projetId: projet.id,
      hypotheses: resultat.hypotheses || [],
      avertissements: resultat.avertissements || [],
    };
  },

  importerPlanIFC: async (projetId, file) => {
    const formData = new FormData();
    formData.append('fichier', file);
    return lireReponse(await apiFetch(`${API_BASE_URL}/projets/${projetId}/importer_plan/`, {
      method: 'POST',
      body: formData,
    }));
  },

  analyserPlanImage: async (projetId, file) => {
    const formData = new FormData();
    formData.append('fichier', file);
    return lireReponse(await apiFetch(`${API_BASE_URL}/projets/${projetId}/analyser_plan_image/`, {
      method: 'POST',
      body: formData,
    }));
  },

  // Éléments
  creerElement: async (champs) => postJSON(`${API_BASE_URL}/elements/`, champs),
  calculerElement: async (elementId) => postJSON(`${API_BASE_URL}/elements/${elementId}/calculer/`),
  supprimerElement: async (elementId) =>
    lireReponse(await apiFetch(`${API_BASE_URL}/elements/${elementId}/`, { method: 'DELETE' })),
  validerElement: async (elementId, resultatValide) =>
    postJSON(`${API_BASE_URL}/elements/${elementId}/valider/`,
      resultatValide ? { resultat_valide: resultatValide } : {}),
  deverrouillerElement: async (elementId) =>
    postJSON(`${API_BASE_URL}/elements/${elementId}/deverrouiller/`),

  // Postes complémentaires
  listerPostesComplementaires: async (projetId) =>
    getJSON(`${API_BASE_URL}/postes-complementaires/?projet=${projetId}`),
  ajouterPosteComplementaire: async (projetId, poste) => {
    const payload = { projet: projetId, lot: poste.lot, mode: poste.mode };
    if (poste.mode === 'simple') {
      payload.designation = poste.designation;
      payload.unite = poste.unite;
      payload.quantite = nombreOuNull(poste.quantite);
      payload.prix_unitaire = nombreOuNull(poste.prixUnitaire);
    } else {
      payload.type_poste = poste.typePoste;
      payload.geometrie = poste.geometrie;
    }
    return postJSON(`${API_BASE_URL}/postes-complementaires/`, payload);
  },
  supprimerPosteComplementaire: async (posteId) =>
    lireReponse(await apiFetch(`${API_BASE_URL}/postes-complementaires/${posteId}/`, { method: 'DELETE' })),

  // Plan de fondation
  recupererPlanFondation: async (projetId) => getJSON(`${API_BASE_URL}/projets/${projetId}/plan_fondation/`),
  recupererPlanFondationPDF: async (projetId) => {
    const response = await apiFetch(`${API_BASE_URL}/projets/${projetId}/plan_fondation/?export=pdf`);
    if (!response.ok) {
      const data = await response.json().catch(() => null);
      const err = new Error(messageErreur(data, response.status));
      err.status = response.status;
      err.data = data;
      throw err;
    }
    return response.blob();
  },
  // "export" et non "format" : "format" est réservé par la négociation de
  // contenu DRF et provoque un 404 avant la vue.
  telechargerPlanFondationDXF: async (projetId) =>
    telechargerBlob(`${API_BASE_URL}/projets/${projetId}/plan_fondation/?export=dxf`, `Plan_fondation_${projetId}.dxf`),
  validerPlanFondation: async (projetId) =>
    postJSON(`${API_BASE_URL}/projets/${projetId}/valider_plan_fondation/`),

  // Variantes recalculées par le moteur (rien n'est enregistré)
  calculerVariantes: async (projetId, variantes) =>
    postJSON(`${API_BASE_URL}/projets/${projetId}/variantes/`, { variantes }),

  // DQE (données brutes du backend : lots, lignes, synthèse, hypothèses)
  genererDQE: async (projetId) => postJSON(`${API_BASE_URL}/projets/${projetId}/generer-dqe/`),
  telechargerDQEFichier: async (projetId, format) =>
    telechargerBlob(
      `${API_BASE_URL}/projets/${projetId}/generer-dqe/?export=${format}`,
      `DQE_projet_${projetId}.${format === 'pdf' ? 'pdf' : 'xlsx'}`,
    ),

  // Assistant IA
  structurerProjetIA: async (description) =>
    postJSON(`${API_BASE_URL}/assistant/structurer-projet/`, { description }),
  expliquerElementIA: async (elementId) =>
    postJSON(`${API_BASE_URL}/assistant/expliquer-element/`, { element_id: elementId }),
  suggererPosteIA: async (description) =>
    postJSON(`${API_BASE_URL}/assistant/suggerer-poste/`, { description }),
  analyserCoherenceProjet: async (projetId) => getJSON(`${API_BASE_URL}/projets/${projetId}/analyse-coherence/`),
  expliquerCoherenceElement: async (elementId) =>
    postJSON(`${API_BASE_URL}/elements/${elementId}/expliquer-coherence/`),

  // Cabinet
  getEntreprise: async () => getJSON(`${API_BASE_URL}/entreprise/`),
  updateEntreprise: async (champs, logoFile) => {
    const formData = new FormData();
    Object.entries(champs || {}).forEach(([cle, valeur]) => {
      formData.append(cle, ['prix_unitaires', 'prix_origines'].includes(cle) ? JSON.stringify(valeur || {}) : (valeur ?? ''));
    });
    if (logoFile) formData.append('logo', logoFile);
    return lireReponse(await apiFetch(`${API_BASE_URL}/entreprise/`, { method: 'PATCH', body: formData }));
  },

  // Analytics (lecture seule)
  analyticsCabinet: async () => getJSON(`${API_BASE_URL}/analytics/cabinet/`),
  analyticsProjet: async (projetId) => getJSON(`${API_BASE_URL}/analytics/projets/${projetId}/`),
  analyticsStaff: async () => getJSON(`${API_BASE_URL}/analytics/staff/`),

  // Authentification & comptes
  isAuthenticated,
  getMe: async () => getJSON(`${API_BASE_URL}/me/`),

  login: async (username, motDePasse) => {
    const response = await publicFetch(`${API_BASE_URL}/auth/token/`, json('POST', { username, password: motDePasse }));
    const data = await response.json().catch(() => null);
    if (!response.ok) {
      const err = new Error(response.status === 401 ? 'Identifiant ou mot de passe incorrect.' : messageErreur(data, response.status));
      err.status = response.status;
      err.data = data;
      throw err;
    }
    setTokens(data);
    return data;
  },

  logout: async () => {
    const refresh = getRefreshToken();
    try {
      if (refresh) await apiFetch(`${API_BASE_URL}/auth/logout/`, json('POST', { refresh }));
    } catch { /* déconnexion locale garantie ci-dessous */ } finally {
      clearTokens();
    }
  },

  inscription: async ({ nomEntreprise, username, email, motDePasse }) => {
    const response = await publicFetch(`${API_BASE_URL}/auth/inscription/`, json('POST', {
      nom_entreprise: nomEntreprise, username, email, mot_de_passe: motDePasse,
    }));
    const data = await response.json().catch(() => null);
    if (!response.ok) {
      const err = new Error('Impossible de créer le compte.');
      err.status = response.status;
      err.data = data;
      throw err;
    }
    setTokens(data);
    return data;
  },

  demanderReinitialisation: async (email) => postJSONPublic(`${API_BASE_URL}/auth/mot-de-passe-oublie/`, { email }),
  confirmerReinitialisation: async ({ uid, token, nouveauMotDePasse }) =>
    postJSONPublic(`${API_BASE_URL}/auth/reinitialiser-mot-de-passe/`, { uid, token, nouveau_mot_de_passe: nouveauMotDePasse }),
  activerCompte: async ({ uid, token, motDePasse }) =>
    postJSONPublic(`${API_BASE_URL}/auth/activer/`, { uid, token, mot_de_passe: motDePasse }),
  changerMotDePasse: async ({ ancienMotDePasse, nouveauMotDePasse }) =>
    postJSON(`${API_BASE_URL}/auth/changer-mot-de-passe/`, {
      ancien_mot_de_passe: ancienMotDePasse, nouveau_mot_de_passe: nouveauMotDePasse,
    }),
  getMoi: async () => getJSON(`${API_BASE_URL}/auth/moi/`),
  inviterUtilisateur: async ({ email, role }) => postJSON(`${API_BASE_URL}/auth/inviter/`, { email, role }),
  listerMembres: async () => getJSON(`${API_BASE_URL}/auth/membres/`),
  desactiverMembre: async (userId) => postJSON(`${API_BASE_URL}/auth/membres/${userId}/desactiver/`),
};

// --- Présentation des éléments renvoyés par l'API -------------------------

export const LIBELLES_TYPES = {
  poteau: 'Poteau',
  poutre: 'Poutre',
  semelle: 'Semelle',
  semelle_filante: 'Semelle filante',
  longrine: 'Longrine',
  chainage: 'Chaînage',
  dalle: 'Dalle',
};

const fmt = (v, unite) => (v === null || v === undefined ? null : `${v} ${unite}`);

export function formatSection(type, res = {}) {
  switch (type) {
    case 'poteau':
      return res.cote_cm ? `${res.cote_cm} x ${res.cote_cm} cm` : null;
    case 'poutre':
    case 'longrine':
    case 'chainage':
    case 'semelle_filante':
      return res.largeur_cm && res.hauteur_cm ? `${res.largeur_cm} x ${res.hauteur_cm} cm` : null;
    case 'semelle':
      if (res.grand_cote_cm && res.petit_cote_cm) return `${res.grand_cote_cm} x ${res.petit_cote_cm} cm`;
      return res.cote_cm ? `${res.cote_cm} x ${res.cote_cm} cm` : null;
    case 'dalle':
      return res.epaisseur_cm ? `ép. ${res.epaisseur_cm} cm` : null;
    default:
      return null;
  }
}

function formatArmatures(res = {}) {
  const barres = res.barres_proposees || res.barres_transversales;
  return barres && barres.diametre_mm && barres.nombre_barres
    ? `${barres.nombre_barres} HA ${barres.diametre_mm}`
    : null;
}

// Élément API -> objet d'affichage. Les champs absents restent null :
// l'interface affiche "—", jamais une valeur de remplacement.
export function formatElement(e) {
  const res = e.resultat_valide || e.resultat_calcul || {};
  const calculIndisponible = !e.resultat_calcul && !e.resultat_valide;
  return {
    id: e.id,
    elementId: e.id,
    name: e.identifiant,
    type: e.type_element,
    categorie: LIBELLES_TYPES[e.type_element] || e.type_element,
    section: formatSection(e.type_element, res),
    armatures: formatArmatures(res),
    charge: e.charge_calculee != null ? `${Math.round(e.charge_calculee * 10) / 10} kN` : null,
    chargeLineaire: e.charge_lineaire != null ? `${Math.round(e.charge_lineaire * 10) / 10} kN/m` : null,
    portee: e.portee != null ? `${e.portee.toFixed(2)} m` : null,
    longueur: e.longueur_m,
    surface: e.surface_m2,
    contrainteSol: e.taux_travail_sol != null ? `${e.taux_travail_sol} kN/m²` : null,
    hypotheseSol: res.hypothese_sol === true,
    hauteur: fmt(res.hauteur_cm, 'cm'),
    resultat: res,
    calculIndisponible,
    locked: e.statut === 'valide',
    statut: e.statut,
  };
}

export function elementsParType(elements = []) {
  const groupes = { poteaux: [], poutres: [], semelles: [], dalles: [], autres: [] };
  elements.forEach((e) => {
    const item = formatElement(e);
    if (e.type_element === 'poteau') groupes.poteaux.push(item);
    else if (e.type_element === 'poutre') groupes.poutres.push(item);
    else if (e.type_element === 'semelle') groupes.semelles.push(item);
    else if (e.type_element === 'dalle') groupes.dalles.push(item);
    else groupes.autres.push(item);
  });
  return groupes;
}

// Formatage monétaire (affichage uniquement -- les montants viennent du serveur).
export const formatFCFA = (n) =>
  n === null || n === undefined ? '—' : `${Number(n).toLocaleString('fr-FR')} FCFA`;