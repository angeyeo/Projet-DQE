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

const API_BASE_URL = '/api';

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

  // Crée les ElementStructurel du projet à partir des paramètres saisis,
  // puis déclenche leur calcul.
  createAndCalculateElements: async (projetId, projectData) => {
    const porteeX = parseFloat(projectData.porteeX || projectData.porteeMax || 6.0);
    const porteeY = parseFloat(projectData.porteeY || projectData.porteeMax || 6.0);
    const portee = Math.max(porteeX, porteeY);
    const chargeExploitation = parseFloat(projectData.chargeExploitation || 2.5);
    const nbNiveaux = parseInt(projectData.nombreNiveaux || 1, 10);
    const hauteurPoteau = parseFloat(projectData.hauteurEtage || 3.0);

    const G = 5.0; // charge permanente forfaitaire (kN/m²)
    const qELU = 1.35 * G + 1.5 * chargeExploitation;
    const surfaceInfluence = (porteeX / 2) * (porteeY / 2);
    const chargeCalculeePoteau = surfaceInfluence * qELU * nbNiveaux; // kN

    const elementsACreer = [
      { type_element: 'poteau', identifiant: 'POT-C1', charge_calculee: chargeCalculeePoteau, hauteur_poteau: hauteurPoteau },
      { type_element: 'poteau', identifiant: 'POT-P1', charge_calculee: chargeCalculeePoteau * 0.6, hauteur_poteau: hauteurPoteau },
      { type_element: 'poutre', identifiant: 'POU-PRINC', portee, charge_lineaire: qELU },
      { type_element: 'poutre', identifiant: 'POU-SEC', portee: portee * 0.75, charge_lineaire: qELU * 0.8 },
      { type_element: 'semelle', identifiant: 'SEM-S1', charge_calculee: chargeCalculeePoteau },
    ];

    const elements = [];
    for (const base of elementsACreer) {
      const created = await postJSON(`${API_BASE_URL}/elements/`, { projet: projetId, ...base });

      try {
        const calcule = await postJSON(`${API_BASE_URL}/elements/${created.id}/calculer/`, undefined);
        elements.push(calcule);
      } catch (calcErr) {
        console.warn(`Calcul indisponible pour ${created.identifiant} :`, calcErr.message);
        elements.push({
          ...created,
          resultat_calcul: null,
          erreur_calcul: (calcErr.data && (calcErr.data.detail || calcErr.data.erreur)) || calcErr.message,
        });
      }
    }
    return elements;
  },

  // Calcule le pré-dimensionnement via le vrai backend DRF
  calculateSections: async (projectData) => {
    const projet = await dqeService.createProjet(projectData);
    const elements = await dqeService.createAndCalculateElements(projet.id, projectData);
    return { projetId: projet.id, ...parseDRFResponse(elements) };
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
    const response = await fetch(`${API_BASE_URL}/projets/${projetId}/plan_fondation/?format=dxf`);
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