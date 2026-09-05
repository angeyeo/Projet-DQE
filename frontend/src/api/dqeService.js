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

const API_BASE_URL = (import.meta.env.VITE_API_URL || '/api').replace(/\/$/, '');

async function postJSON(url, body) {
  const response = await fetch(url, {
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
    const response = await fetch(`${API_BASE_URL}/projets/${projetId}/`, {
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
    const response = await fetch(`${API_BASE_URL}/projets/${projetId}/importer_plan/`, {
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

  // Postes complémentaires (Jour 2.1)
  listerPostesComplementaires: async (projetId) => {
    if (!projetId) return [];
    const response = await fetch(`${API_BASE_URL}/postes-complementaires/?projet=${projetId}`);
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
    const response = await fetch(`${API_BASE_URL}/postes-complementaires/${posteId}/`, {
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
    const response = await fetch(`${API_BASE_URL}/projets/${projetId}/chainage_suggere/`);
    const data = await response.json().catch(() => null);
    if (!response.ok) {
      throw new Error((data && data.erreur) || `Erreur ${response.status}`);
    }
    return data.longueur_m;
  },

  // Plan de fondation (Jour 3.1)
  recupererPlanFondation: async (projetId) => {
    if (!projetId) return null;
    const response = await fetch(`${API_BASE_URL}/projets/${projetId}/plan_fondation/`);
    const data = await response.json().catch(() => null);
    if (!response.ok) {
      throw new Error((data && data.erreur) || `Erreur ${response.status}`);
    }
    return data;
  },

  telechargerPlanFondationDXF: async (projetId) => {
    if (!projetId) {
      throw new Error("Aucun projet actif -- impossible de télécharger le plan sans projetId.");
    }
    // IMPORTANT : le paramètre s'appelle "export" et non "format" -- "format" est
    // réservé par la négociation de contenu de DRF et déclenche un Http404 avant
    // même d'atteindre la vue (voir projets/views.py::plan_fondation). C'était la
    // cause du bouton de téléchargement DXF qui ne fonctionnait pas.
    const response = await fetch(`${API_BASE_URL}/projets/${projetId}/plan_fondation/?export=dxf`);
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

  // Paramètres entreprise (logo + coordonnées) utilisés en en-tête des
  // exports DQE -- voir projets/models.py::EntrepriseParametres.
  getEntreprise: async () => {
    const response = await fetch(`${API_BASE_URL}/entreprise/`);
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
    const response = await fetch(`${API_BASE_URL}/entreprise/`, {
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

    const response = await fetch(`${API_BASE_URL}/projets/${projetId}/generer_dqe/?export=${format}`, {
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
    const response = await fetch(`${API_BASE_URL}/projets/${projetId}/generer_dqe/`, {
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
  if (typeElement === 'poutre' || typeElement === 'semelle') {
    if (res.largeur_cm && res.hauteur_cm) return `${res.largeur_cm} x ${res.hauteur_cm} cm`;
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
    explicationIA:
      'Devis calculé par le moteur de calcul (BAEL 91) à partir des sections validées et verrouillées.',
  };
}