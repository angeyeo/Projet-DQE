// Service API Frontend pour le Projet DQE
// Aligné sur l'API Django REST Framework réelle d'Ange Yeo (voir api/urls.py, projets/models.py)
//
// Endpoints DRF utilisés :
// - POST /api/projets/
// - POST /api/elements/
// - POST /api/elements/{id}/calculer/
// - POST /api/elements/{id}/valider/
// - GET|POST /api/projets/{id}/generer_dqe/
// - GET|POST /api/projets/{id}/plan_fondation/
// - POST /api/projets/{id}/valider_plan_fondation/
// - GET|POST|DELETE /api/postes-complementaires/
// - POST /api/assistant/structurer-projet/
// - POST /api/assistant/expliquer-element/
// - POST /api/assistant/suggerer-poste/
// - POST /api/projets/{id}/analyser_plan_image/ (Vision IA)
// - GET  /api/projets/{id}/analyse-coherence/ (Contrôle de cohérence)
// - POST /api/elements/{id}/expliquer-coherence/ (Explication IA d'un signal)

const API_BASE_URL = (import.meta.env.VITE_API_URL || '/api').replace(/\/$/, '');

// --- Authentification JWT (sprint Comptes & Permissions) ---------------
// Jetons stockés en localStorage : survivent au rechargement de page. Un
// vrai backend d'auth existe maintenant (voir projets/auth_views.py),
// donc toutes les routes métier ci-dessous passent par apiFetch, qui
// attache le token et gère le rafraîchissement silencieux sur 401.

const ACCESS_KEY = 'dqe_access_token';
const REFRESH_KEY = 'dqe_refresh_token';

function getAccessToken() {
  return localStorage.getItem(ACCESS_KEY);
}

function getRefreshToken() {
  return localStorage.getItem(REFRESH_KEY);
}

function setTokens({ access, refresh }) {
  if (access) localStorage.setItem(ACCESS_KEY, access);
  if (refresh) localStorage.setItem(REFRESH_KEY, refresh);
}

function clearTokens() {
  localStorage.removeItem(ACCESS_KEY);
  localStorage.removeItem(REFRESH_KEY);
}

function isAuthenticated() {
  return !!getAccessToken();
}

// Rafraîchit le token d'accès via le refresh token. Renvoie le nouveau
// access token, ou null si le refresh a échoué (token expiré/révoqué).
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

// Fetch "public" -- n'attache jamais de token. Nécessaire pour les
// routes AllowAny (login, inscription, mot de passe oublié...) : un
// access token expiré présent en localStorage ferait échouer
// l'authentification JWT avant même d'atteindre la vue AllowAny.
async function publicFetch(url, options = {}) {
  return fetch(url, options);
}

// Fetch authentifié -- attache le token courant, rafraîchit une fois et
// réessaie sur 401, puis prévient l'app (événement) si la session est
// définitivement expirée pour qu'elle renvoie l'utilisateur au login.
async function apiFetch(url, options = {}) {
  const access = getAccessToken();
  const headers = { ...(options.headers || {}) };
  if (access) headers['Authorization'] = `Bearer ${access}`;

  let response = await fetch(url, { ...options, headers });

  if (response.status === 401 && getRefreshToken()) {
    const nouvelAccess = await rafraichirToken();
    if (nouvelAccess) {
      response = await fetch(url, {
        ...options,
        headers: { ...(options.headers || {}), Authorization: `Bearer ${nouvelAccess}` },
      });
    }
  }

  if (response.status === 401) {
    clearTokens();
    window.dispatchEvent(new CustomEvent('dqe:auth-expired'));
  }

  return response;
}

async function postJSON(url, body) {
  const response = await apiFetch(url, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: body !== undefined ? JSON.stringify(body) : undefined,
  });
  const data = await response.json().catch(() => null);
  if (!response.ok) {
    const err = new Error((data && (data.erreur || data.detail)) || `Erreur ${response.status}`);
    err.status = response.status;
    err.data = data;
    throw err;
  }
  return data;
}

// Variante de postJSON pour les routes AllowAny (mot de passe oublié,
// réinitialisation, activation) -- utilise publicFetch, jamais apiFetch,
// pour la même raison que le login (cf. publicFetch ci-dessus).
async function postJSONPublic(url, body) {
  const response = await publicFetch(url, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: body !== undefined ? JSON.stringify(body) : undefined,
  });
  const data = await response.json().catch(() => null);
  if (!response.ok) {
    const err = new Error((data && (data.erreur || data.detail)) || `Erreur ${response.status}`);
    err.status = response.status;
    err.data = data;
    throw err;
  }
  return data;
}

async function getJSON(url) {
  const response = await apiFetch(url);
  const data = await response.json().catch(() => null);
  if (!response.ok) {
    const err = new Error((data && (data.erreur || data.detail)) || `Erreur ${response.status}`);
    err.status = response.status;
    err.data = data;
    throw err;
  }
  return data;
}

export const dqeService = {
  // Créer un projet -- champs alignés sur projets/models.py::Projet
  createProjet: async (projectData) => {
    const payload = {
      nom: projectData.nomProjet || 'Projet sans nom',
      usage_batiment: projectData.typeUsage || 'habitation',
      nb_niveaux: parseInt(projectData.nombreNiveaux || 1, 10),
      numero_devis: projectData.numeroDevis || '',
    };
    return postJSON(`${API_BASE_URL}/projets/`, payload);
  },

  // Synchronise sur le projet les paramètres de trame éventuellement
  // corrigés par l'utilisateur après le pré-remplissage (IFC ou saisie
  // manuelle) -- generer_trame/ et importer_plan (confirmer) lisent ces
  // champs directement sur le Projet, pas depuis la requête.
  patchProjet: async (projetId, champs) => {
    const response = await apiFetch(`${API_BASE_URL}/projets/${projetId}/`, {
      method: 'PATCH',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(champs),
    });
    const data = await response.json().catch(() => null);
    if (!response.ok) {
      const err = new Error((data && (data.detail || JSON.stringify(data))) || `Erreur ${response.status}`);
      err.status = response.status;
      err.data = data;
      throw err;
    }
    return data;
  },

  // Génère la grille complète (poteaux + semelles + poutres) à partir
  // de projet.nb_travees_x/y, portee_x/y -- chemin "saisie manuelle".
  genererTrame: async (projetId) => {
    return postJSON(`${API_BASE_URL}/projets/${projetId}/generer_trame/`, undefined);
  },

  // Calcule le pré-dimensionnement via le vrai backend DRF : synchronise
  // d'abord les paramètres de trame sur le projet, puis génère les
  // VRAIS éléments -- soit à partir des positions réelles de l'IFC
  // importé (Phase B), soit sur une grille régulière (generer_trame)
  // pour la saisie manuelle. Remplace l'ancien pipeline à 5 éléments
  // fictifs qui ignorait complètement nb_travees_x/y et portee_x/y.
  calculateSections: async (projectData) => {
    const projetId = projectData.id || (await dqeService.createProjet(projectData)).id;

    await dqeService.patchProjet(projetId, {
      nb_niveaux: parseInt(projectData.nombreNiveaux || 1, 10),
      usage_batiment: projectData.typeUsage || 'habitation',
      numero_devis: projectData.numeroDevis || '',
      nb_travees_x: parseInt(projectData.nbTraveesX || 1, 10),
      nb_travees_y: parseInt(projectData.nbTraveesY || 1, 10),
      portee_x: parseFloat(projectData.porteeX || 4.0),
      portee_y: parseFloat(projectData.porteeY || 4.0),
      hauteur_etage: parseFloat(projectData.hauteurEtage || 3.0),
      charge_exploitation: parseFloat(projectData.chargeExploitation || 2.5),
    });

    let elements;
    if (projectData.ifcImporte) {
      const resultat = await dqeService.confirmerImportPlanIFC(projetId);
      elements = resultat.elements || [];
    } else {
      elements = await dqeService.genererTrame(projetId);
    }

    return { projetId, ...parseDRFResponse(elements) };
  },

  // Aperçu Phase A -- envoie un fichier IFC pour détection des paramètres de
  // trame (nb_travees_x/y, portee_x/y, nb_niveaux, hauteur_etage), sans créer
  // aucun ElementStructurel. Voir projets/views.py::ProjetViewSet.importer_plan.
  importerPlanIFC: async (projetId, file) => {
    if (!projetId) {
      throw new Error("Aucun projet actif -- impossible d'importer un plan IFC sans projetId.");
    }
    const formData = new FormData();
    formData.append('fichier', file);
    const response = await apiFetch(`${API_BASE_URL}/projets/${projetId}/importer_plan/`, {
      method: 'POST',
      body: formData,
    });
    const data = await response.json().catch(() => null);
    if (!response.ok) {
      const err = new Error((data && (data.erreur || data.detail)) || `Erreur ${response.status}`);
      err.status = response.status;
      err.data = data;
      throw err;
    }
    return data;
  },

  // Confirmation Phase B -- relit le fichier IFC déjà déposé et crée les
  // vrais ElementStructurel à leurs positions réelles.
  confirmerImportPlanIFC: async (projetId) => {
    if (!projetId) {
      throw new Error("Aucun projet actif -- impossible de confirmer un import sans projetId.");
    }
    return postJSON(`${API_BASE_URL}/projets/${projetId}/importer_plan/`, { confirmer: true });
  },

  // Vision IA -- envoie une image de plan (JPG/PNG) à l'endpoint Gemini
  // Vision pour lecture OCR des annotations (repères + dimensions entre
  // parenthèses, ex: "S1(170x170x40)"). Ne pré-remplit PAS nb_travees_x/y
  // (le backend ne renvoie pas ce format pour cet endpoint) -- il renvoie
  // une liste d'annotations lues à vérifier manuellement par l'ingénieur.
  // Cette fonction n'existait pas alors qu'elle était déjà appelée par
  // Step1_Parametres.jsx, ce qui provoquait un crash ("dqeService.analyserPlanImage
  // is not a function") dès qu'un utilisateur déposait une image de plan.
  analyserPlanImage: async (projetId, file) => {
    if (!projetId) {
      throw new Error("Aucun projet actif -- impossible d'analyser une image sans projetId.");
    }
    const formData = new FormData();
    formData.append('fichier', file);
    const response = await apiFetch(`${API_BASE_URL}/projets/${projetId}/analyser_plan_image/`, {
      method: 'POST',
      body: formData,
    });
    const data = await response.json().catch(() => null);
    if (!response.ok) {
      const msg = (data && (data.erreur || data.detail)) || (
        response.status === 413
          ? "L'image envoyée est trop volumineuse."
          : response.status === 429
          ? "Trop de requêtes effectuées. Veuillez patienter avant de réessayer."
          : response.status === 400
          ? "Fichier ou format d'image non supporté."
          : `Erreur ${response.status}`
      );
      const err = new Error(msg);
      err.status = response.status;
      err.data = data;
      throw err;
    }
    return data;
  },

  // Postes complémentaires (Jour 2.1)
  listerPostesComplementaires: async (projetId) => {
    if (!projetId) return [];
    const response = await apiFetch(`${API_BASE_URL}/postes-complementaires/?projet=${projetId}`);
    const data = await response.json().catch(() => null);
    if (!response.ok) {
      throw new Error((data && (data.erreur || data.detail)) || `Erreur ${response.status}`);
    }
    return Array.isArray(data) ? data : data.results || [];
  },

  ajouterPosteComplementaire: async (projetId, poste) => {
    if (!projetId) {
      throw new Error("Aucun projet actif -- impossible d'ajouter un poste.");
    }
    const payload = {
      projet: projetId,
      lot: poste.lot,
      mode: poste.mode,
    };
    if (poste.mode === 'simple') {
      payload.designation = poste.designation;
      payload.unite = poste.unite;
      payload.quantite = parseFloat(poste.quantite);
      payload.prix_unitaire = parseFloat(poste.prixUnitaire);
    } else {
      payload.type_poste = poste.typePoste;
      payload.geometrie = poste.geometrie;
    }
    return postJSON(`${API_BASE_URL}/postes-complementaires/`, payload);
  },

  supprimerPosteComplementaire: async (posteId) => {
    const response = await apiFetch(`${API_BASE_URL}/postes-complementaires/${posteId}/`, {
      method: 'DELETE',
    });
    if (!response.ok && response.status !== 204) {
      const data = await response.json().catch(() => null);
      throw new Error((data && (data.erreur || data.detail)) || `Erreur ${response.status}`);
    }
    return true;
  },

  // Ancien alias main d'œuvre pour compatibilité
  listerPostesMainDoeuvre: async (projetId) => dqeService.listerPostesComplementaires(projetId),
  ajouterPosteMainDoeuvre: async (projetId, poste) => dqeService.ajouterPosteComplementaire(projetId, { ...poste, lot: 'lot_00_generalites', mode: 'simple' }),
  supprimerPosteMainDoeuvre: async (posteId) => dqeService.supprimerPosteComplementaire(posteId),

  // Suggestion de chaînage automatique (Jour 2.2)
  recupererChainageSuggere: async (projetId) => {
    if (!projetId) return 0;
    const response = await apiFetch(`${API_BASE_URL}/projets/${projetId}/chainage_suggere/`);
    const data = await response.json().catch(() => null);
    if (!response.ok) {
      throw new Error((data && data.erreur) || `Erreur ${response.status}`);
    }
    return data.longueur_m;
  },

  // Plan de fondation (Jour 3.1)
  recupererPlanFondation: async (projetId) => {
    if (!projetId) return null;
    const response = await apiFetch(`${API_BASE_URL}/projets/${projetId}/plan_fondation/`);
    const data = await response.json().catch(() => null);
    if (!response.ok) {
      throw new Error((data && data.erreur) || `Erreur ${response.status}`);
    }
    return data;
  },

  // PDF du plan de coffrage : renvoie un Blob (fetch authentifié via apiFetch,
  // un fetch() brut n'envoie pas le jeton JWT et renvoie 401).
  recupererPlanFondationPDF: async (projetId) => {
    if (!projetId) {
      throw new Error("Aucun projet actif -- impossible de récupérer le PDF sans projetId.");
    }
    const response = await apiFetch(`${API_BASE_URL}/projets/${projetId}/plan_fondation/?export=pdf`);
    if (!response.ok) {
      const data = await response.json().catch(() => null);
      throw new Error((data && (data.erreur || data.detail)) || `Erreur ${response.status}`);
    }
    return response.blob();
  },

  telechargerPlanFondationDXF: async (projetId) => {
    if (!projetId) {
      throw new Error("Aucun projet actif -- impossible de télécharger le plan sans projetId.");
    }
    // IMPORTANT : le paramètre s'appelle "export" et non "format" -- "format" est
    // réservé par la négociation de contenu de DRF et déclenche un Http404 avant
    // même d'atteindre la vue (voir projets/views.py::plan_fondation). C'était la
    // cause du bouton de téléchargement DXF qui ne fonctionnait pas.
    const response = await apiFetch(`${API_BASE_URL}/projets/${projetId}/plan_fondation/?export=dxf`);
    if (!response.ok) {
      const data = await response.json().catch(() => null);
      throw new Error((data && data.erreur) || `Erreur ${response.status}`);
    }
    const blob = await response.blob();
    const disposition = response.headers.get('Content-Disposition') || '';
    const match = disposition.match(/filename="?([^"]+)"?/);
    const filename = match ? match[1] : `Plan_fondation_${projetId}.dxf`;
    const url = window.URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = filename;
    document.body.appendChild(a);
    a.click();
    a.remove();
    window.URL.revokeObjectURL(url);
  },

  validerPlanFondation: async (projetId) => {
    if (!projetId) return true;
    return postJSON(`${API_BASE_URL}/projets/${projetId}/valider_plan_fondation/`, undefined);
  },

  // Valide/verrouille un élément côté backend
  validerElementDRF: async (elementId, resultatValide) => {
    if (!elementId) {
      throw new Error("elementId manquant -- impossible de valider un élément sans son id numérique réel.");
    }
    return postJSON(`${API_BASE_URL}/elements/${elementId}/valider/`, {
      resultat_valide: resultatValide,
    });
  },

  // Structuration NLP par Assistant IA
  structurerProjetIA: async (descriptionText) => {
    return postJSON(`${API_BASE_URL}/assistant/structurer-projet/`, {
      description: descriptionText,
    });
  },

  // Explication d'un élément par Assistant IA
  expliquerElementIA: async (elementId) => {
    return postJSON(`${API_BASE_URL}/assistant/expliquer-element/`, {
      element_id: elementId,
    });
  },

  // Suggestion de poste complémentaire par Assistant IA -- l'ingénieur décrit
  // le poste en langage naturel, l'IA propose designation/unite/lot/confiance.
  // Cette fonction n'existait pas du tout : appel jamais câblé côté service.
  suggererPosteIA: async (descriptionText) => {
    return postJSON(`${API_BASE_URL}/assistant/suggerer-poste/`, {
      description: descriptionText,
    });
  },

  // Contrôle de cohérence structurelle -- analyse tous les éléments validés
  // d'un projet et remonte des signaux (CRITIQUE/ATTENTION/INFORMATION/...).
  // Appelée par Step3_ValidationLock.jsx mais n'existait pas encore ici.
  analyserCoherenceProjet: async (projetId) => {
    return getJSON(`${API_BASE_URL}/projets/${projetId}/analyse-coherence/`);
  },

  // Explication IA d'un signal de cohérence pour un élément donné.
  // Appelée par Step3_ValidationLock.jsx mais n'existait pas encore ici.
  expliquerCoherenceElement: async (elementId) => {
    return postJSON(`${API_BASE_URL}/elements/${elementId}/expliquer-coherence/`);
  },

  // Paramètres entreprise (logo + coordonnées) utilisés en en-tête des
  // exports DQE -- voir projets/models.py::EntrepriseParametres.
  getEntreprise: async () => {
    const response = await apiFetch(`${API_BASE_URL}/entreprise/`);
    const data = await response.json().catch(() => null);
    if (!response.ok) {
      const err = new Error((data && data.detail) || `Erreur ${response.status}`);
      err.status = response.status;
      err.data = data;
      throw err;
    }
    return data;
  },

  // `champs` : objet simple (nom, siege_social, telephone, email, site_web,
  // rccm, cc, cb, capital_social) et/ou `logoFile` (objet File, optionnel).
  updateEntreprise: async (champs, logoFile) => {
    const formData = new FormData();
    Object.entries(champs || {}).forEach(([cle, valeur]) => {
      formData.append(cle, valeur ?? '');
    });
    if (logoFile) {
      formData.append('logo', logoFile);
    }
    const response = await apiFetch(`${API_BASE_URL}/entreprise/`, {
      method: 'PATCH',
      body: formData,
    });
    const data = await response.json().catch(() => null);
    if (!response.ok) {
      const err = new Error((data && data.detail) || `Erreur ${response.status}`);
      err.status = response.status;
      err.data = data;
      throw err;
    }
    return data;
  },

  // Télécharge le DQE binaire (PDF / Excel)
  telechargerDQEFichier: async (projetId, format) => {
    if (!projetId) {
      throw new Error("Aucun projet actif -- impossible de télécharger le DQE sans projetId.");
    }
    if (format !== 'pdf' && format !== 'excel') {
      throw new Error(`Format d'export invalide : "${format}" (attendu : "pdf" ou "excel").`);
    }

    const response = await apiFetch(`${API_BASE_URL}/projets/${projetId}/generer_dqe/?export=${format}`, {
      method: 'GET',
    });

    if (!response.ok) {
      const data = await response.json().catch(() => null);
      const err = new Error((data && data.erreur) || `Erreur ${response.status}`);
      err.status = response.status;
      err.data = data;
      throw err;
    }

    const blob = await response.blob();
    const disposition = response.headers.get('Content-Disposition') || '';
    const match = disposition.match(/filename="?([^"]+)"?/);
    const filename = match ? match[1] : `DQE_projet_${projetId}.${format === 'pdf' ? 'pdf' : 'xlsx'}`;

    const url = window.URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = filename;
    document.body.appendChild(a);
    a.click();
    a.remove();
    window.URL.revokeObjectURL(url);
  },

  calculateDQE: async (projetId, sections) => {
    if (!projetId) {
      throw new Error("Aucun projetId actif -- impossible de calculer le DQE sans projet.");
    }
    const response = await apiFetch(`${API_BASE_URL}/projets/${projetId}/generer_dqe/`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
    });
    const data = await response.json();
    if (!response.ok) {
      const err = new Error(data.erreur || `Erreur ${response.status}`);
      err.data = data;
      throw err;
    }
    return parseDQEResponse(data);
  },

  // === Authentification & Comptes (sprint Comptes & Permissions) =======
  // Toutes ces routes existent réellement côté backend (projets/auth_views.py)
  // -- ce n'était pas le cas quand LoginPage/RegisterPage/ForgotPasswordPage
  // ont été créées ; elles doivent maintenant appeler ces fonctions au lieu
  // de leur ancien état "pas encore branché".

  isAuthenticated,

  // Connexion classique (JWT). Retourne {access, refresh} et les stocke.
  login: async (username, motDePasse) => {
    const response = await publicFetch(`${API_BASE_URL}/auth/token/`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ username, password: motDePasse }),
    });
    const data = await response.json().catch(() => null);
    if (!response.ok) {
      const err = new Error((data && data.detail) || "Identifiants incorrects.");
      err.status = response.status;
      err.data = data;
      throw err;
    }
    setTokens(data);
    return data;
  },

  // Déconnexion : révoque le refresh token côté serveur (liste noire),
  // puis nettoie le stockage local dans tous les cas.
  logout: async () => {
    const refresh = getRefreshToken();
    try {
      if (refresh) {
        await apiFetch(`${API_BASE_URL}/auth/logout/`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ refresh }),
        });
      }
    } finally {
      clearTokens();
    }
  },

  // Inscription d'un nouveau cabinet + premier compte Admin.
  inscription: async ({ nomEntreprise, username, email, motDePasse }) => {
    const response = await publicFetch(`${API_BASE_URL}/auth/inscription/`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        nom_entreprise: nomEntreprise,
        username,
        email,
        mot_de_passe: motDePasse,
      }),
    });
    const data = await response.json().catch(() => null);
    if (!response.ok) {
      const err = new Error("Impossible de créer le compte.");
      err.status = response.status;
      err.data = data; // erreurs par champ (nom_entreprise, username, mot_de_passe...)
      throw err;
    }
    setTokens(data);
    return data;
  },

  // Demande de réinitialisation -- ne révèle jamais si l'email existe.
  demanderReinitialisation: async (email) => {
    return postJSONPublic(`${API_BASE_URL}/auth/mot-de-passe-oublie/`, { email });
  },

  confirmerReinitialisation: async ({ uid, token, nouveauMotDePasse }) => {
    return postJSONPublic(`${API_BASE_URL}/auth/reinitialiser-mot-de-passe/`, {
      uid,
      token,
      nouveau_mot_de_passe: nouveauMotDePasse,
    });
  },

  activerCompte: async ({ uid, token, motDePasse }) => {
    return postJSONPublic(`${API_BASE_URL}/auth/activer/`, {
      uid,
      token,
      mot_de_passe: motDePasse,
    });
  },

  changerMotDePasse: async ({ ancienMotDePasse, nouveauMotDePasse }) => {
    return postJSON(`${API_BASE_URL}/auth/changer-mot-de-passe/`, {
      ancien_mot_de_passe: ancienMotDePasse,
      nouveau_mot_de_passe: nouveauMotDePasse,
    });
  },

  // Profil (rôle, entreprise) de l'utilisateur connecté.
  getMoi: async () => {
    return getJSON(`${API_BASE_URL}/auth/moi/`);
  },

  // Réservé aux comptes Admin du cabinet.
  inviterUtilisateur: async ({ email, role }) => {
    return postJSON(`${API_BASE_URL}/auth/inviter/`, { email, role });
  },

  listerMembres: async () => {
    return getJSON(`${API_BASE_URL}/auth/membres/`);
  },

  desactiverMembre: async (userId) => {
    return postJSON(`${API_BASE_URL}/auth/membres/${userId}/desactiver/`);
  },
};

function parseDRFResponse(elements) {
  if (!elements) return { poteaux: [], poutres: [], semelles: [] };
  return {
    poteaux: elements.filter((e) => e.type_element === 'poteau').map(formatElement),
    poutres: elements.filter((e) => e.type_element === 'poutre').map(formatElement),
    semelles: elements.filter((e) => e.type_element === 'semelle').map(formatElement),
  };
}

function formatElement(e) {
  const res = e.resultat_valide || e.resultat_calcul || {};
  const calculIndisponible = !e.resultat_calcul && !e.resultat_valide;
  return {
    id: e.identifiant || `EL-${e.id}`,
    elementId: e.id,
    name: e.identifiant,
    section: calculIndisponible ? 'Calcul manuel requis' : formatSection(e.type_element, res),
    armatures: calculIndisponible ? '—' : formatArmatures(e.type_element, res),
    // Champs bruts du modèle Django (ElementStructurel), sérialisés tels
    // quels par DRF (fields = "__all__") -- ils existaient déjà dans la
    // réponse API mais n'étaient jamais lus ici. Résultat : Step2_Calculs.jsx
    // (item.charge / item.effort_axial / item.portee / item.contrainteSol)
    // ne trouvait jamais ces propriétés et retombait systématiquement sur
    // ses valeurs par défaut codées en dur ("150 kN", "5.0 m", "0.20 MPa"...)
    // pour CHAQUE élément, quelle que soit sa charge réelle.
    charge: e.charge_calculee != null ? `${Math.round(e.charge_calculee * 10) / 10} kN` : null,
    portee: e.portee != null ? `${e.portee.toFixed(2)} m` : null,
    contrainteSol: e.taux_travail_sol != null ? `${e.taux_travail_sol.toFixed(2)} MPa` : null,
    hauteur: res.hauteur_cm != null ? `${res.hauteur_cm} cm` : null,
    resultat: res,
    calculIndisponible,
    erreurCalcul: e.erreur_calcul || null,
    locked: e.statut === 'valide',
    statut: e.statut,
  };
}

function formatSection(typeElement, res) {
  if (typeElement === 'poteau') {
    const cote = res.cote_cm ?? res.largeur_cm;
    return cote ? `${cote} x ${cote} cm` : 'n/d';
  }
  if (typeElement === 'poutre') {
    if (res.largeur_cm && res.hauteur_cm) return `${res.largeur_cm} x ${res.hauteur_cm} cm`;
  }
  if (typeElement === 'semelle') {
    // dimensionner_semelle() (semelle isolée carrée) renvoie "cote_cm", pas
    // "largeur_cm"/"hauteur_cm" -- seule dimensionner_semelle_affinee()
    // (grand_cote_cm/petit_cote_cm, rectangulaire) et dimensionner_semelle_filante()
    // (largeur_cm) utilisent d'autres noms. Sans ce cas, la colonne "Dimensions
    // (A x B)" affichait "n/d" pour toutes les semelles carrées, alors que
    // cote_cm était bien calculé et affiché correctement dans le tableau du
    // Plan de Fondation (StepPlanFondation.jsx, qui lit une autre source).
    if (res.grand_cote_cm && res.petit_cote_cm) return `${res.grand_cote_cm} x ${res.petit_cote_cm} cm`;
    if (res.largeur_cm && res.hauteur_cm) return `${res.largeur_cm} x ${res.hauteur_cm} cm`;
    if (res.cote_cm) return `${res.cote_cm} x ${res.cote_cm} cm`;
  }
  return 'n/d';
}

function formatArmatures(typeElement, res) {
  const barres = res.barres_proposees || res.barres_transversales;
  if (barres && barres.diametre_mm && barres.nombre_barres) {
    return `${barres.nombre_barres} HA ${barres.diametre_mm}`;
  }
  return 'n/d';
}

function parseDQEResponse(data) {
  const lignes = data.lignes || [];
  return {
    quantites: lignes.map((l) => ({
      materiau: l.designation || l.materiau,
      unite: l.unite,
      quantite: l.quantite,
      prixUnitaire: `${Number(l.prix_unitaire).toLocaleString()} FCFA`,
      total: `${Number(l.montant).toLocaleString()} FCFA`,
    })),
    montantTotalFCFA: `${Number(data.total_general).toLocaleString()} FCFA`,
    // NB : ce champ n'est PAS généré par l'assistant IA -- c'est une phrase
    // fixe décrivant le moteur de calcul. Il s'appelait "explicationIA" et
    // était affiché sous un badge "Sparkles / DKE IA" dans Step4_DQEExport.jsx,
    // ce qui laissait croire à tort qu'une IA avait produit ce texte alors
    // qu'aucun appel à /assistant/expliquer-element/ n'était jamais fait ici.
    syntheseCalcul:
      'Devis calculé par le moteur de calcul (BAEL 91) à partir des sections validées et verrouillées.',
  };
}