// Service API Frontend pour le Projet DQE
// Aligné sur l'API Django REST Framework réelle d'Ange Yeo (voir api/urls.py, projets/models.py)
//
// Endpoints DRF utilisés :
// - POST /api/projets/
// - POST /api/elements/
// - POST /api/elements/{id}/calculer/
// - POST /api/elements/{id}/valider/
// - GET|POST /api/projets/{id}/generer_dqe/
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
    };
    return postJSON(`${API_BASE_URL}/projets/`, payload);
  },

  // Crée les ElementStructurel du projet à partir des paramètres saisis,
  // puis déclenche leur calcul.
  createAndCalculateElements: async (projetId, projectData) => {
    const portee = parseFloat(projectData.porteeMax || 6.0);
    const chargeExploitation = parseFloat(projectData.chargeExploitation || 2.5);
    const nbNiveaux = parseInt(projectData.nombreNiveaux || 1, 10);

    const G = 5.0; // charge permanente forfaitaire (kN/m²)
    const qELU = 1.35 * G + 1.5 * chargeExploitation;
    const surfaceInfluence = (portee / 2) * (portee / 2);
    const chargeCalculeePoteau = surfaceInfluence * qELU * nbNiveaux; // kN

    const elementsACreer = [
      { type_element: 'poteau', identifiant: 'POT-C1', charge_calculee: chargeCalculeePoteau, hauteur_poteau: 3.0 },
      { type_element: 'poteau', identifiant: 'POT-P1', charge_calculee: chargeCalculeePoteau * 0.6, hauteur_poteau: 3.0 },
      { type_element: 'poutre', identifiant: 'POU-PRINC', portee, charge_lineaire: qELU },
      { type_element: 'poutre', identifiant: 'POU-SEC', portee: portee * 0.75, charge_lineaire: qELU * 0.8 },
      { type_element: 'semelle', identifiant: 'SEM-S1', charge_calculee: chargeCalculeePoteau, taux_travail_sol: 2.0 },
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
    try {
      const projet = await dqeService.createProjet(projectData);
      const elements = await dqeService.createAndCalculateElements(projet.id, projectData);
      return { projetId: projet.id, ...parseDRFResponse(elements) };
    } catch (e) {
      console.warn('API indisponible ou en erreur, mode simulateur local :', e.message);
      return { projetId: null, ...simulateSectionsLocal(projectData) };
    }
  },

  // Valide/verrouille un élément côté backend
  validerElementDRF: async (elementId, resultatValide) => {
    if (!elementId) return null;
    return postJSON(`${API_BASE_URL}/elements/${elementId}/valider/`, {
      resultat_valide: resultatValide,
    });
  },

  // Structuration NLP par Assistant IA
  structurerProjetIA: async (descriptionText) => {
    try {
      return await postJSON(`${API_BASE_URL}/assistant/structurer-projet/`, {
        description: descriptionText,
      });
    } catch (e) {
      console.warn('Assistant IA indisponible :', e.message);
      return { validation_humaine_requise: true, message: 'Structure analysée (mode local).' };
    }
  },

  // Explication d'un élément par Assistant IA
  expliquerElementIA: async (elementId) => {
    try {
      return await postJSON(`${API_BASE_URL}/assistant/expliquer-element/`, {
        element_id: elementId,
      });
    } catch (e) {
      console.warn('Assistant IA indisponible :', e.message);
      return {
        validation_humaine_requise: true,
        explication: 'Section dimensionnée conformément aux règles BAEL 91 (mode local).',
      };
    }
  },

  // Génère le DQE via l'API DRF avec le vrai projetId
  calculateDQE: async (projetId, sections) => {
    if (!projetId) {
      return simulateDQELocal(sections);
    }
    try {
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
    } catch (e) {
      console.warn('Génération DQE via API impossible, fallback local :', e.message);
      return simulateDQELocal(sections);
    }
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

function simulateSectionsLocal(projectData) {
  const { porteeMax = 6.0, chargeExploitation = 2.5, nombreNiveaux = 3 } = projectData;
  const G = 5.0;
  const Q = parseFloat(chargeExploitation || 2.5);
  const qELU = 1.35 * G + 1.5 * Q;

  const surfaceInfluence = (porteeMax / 2) * (porteeMax / 2);
  const Nsd = surfaceInfluence * qELU * parseInt(nombreNiveaux || 3, 10);

  const sectionPoteauHeight = Math.max(20, Math.ceil(Math.sqrt((Nsd * 1000) / (0.85 * 14.2)) / 5) * 5);
  const hauteurPoutre = Math.ceil((porteeMax * 100) / 10 / 5) * 5;
  const largeurPoutre = Math.max(20, Math.ceil(hauteurPoutre / 2 / 5) * 5);

  const sigmaSol = 0.2;
  const surfaceSemelle = Nsd / (sigmaSol * 1000);
  const coteSemelle = Math.ceil(Math.sqrt(surfaceSemelle) * 10) / 10;

  return {
    poteaux: [
      { id: 'POT-C1', elementId: null, name: 'Poteau Central C1', charge: `${Nsd.toFixed(1)} kN`, section: `20 x ${sectionPoteauHeight} cm`, armatures: '4 HA 14', locked: false, statut: 'propose' },
      { id: 'POT-P1', elementId: null, name: 'Poteau Périphérique P1', charge: `${(Nsd * 0.6).toFixed(1)} kN`, section: `20 x ${Math.max(20, sectionPoteauHeight - 5)} cm`, armatures: '4 HA 12', locked: false, statut: 'propose' },
    ],
    poutres: [
      { id: 'POU-PRINC', elementId: null, name: 'Poutre Principale PP1', portee: `${porteeMax} m`, section: `${largeurPoutre} x ${hauteurPoutre} cm`, armatures: '3 HA 16 filantes', locked: false, statut: 'propose' },
      { id: 'POU-SEC', elementId: null, name: 'Poutre Secondaire PS1', portee: `${(porteeMax * 0.75).toFixed(1)} m`, section: `15 x ${Math.max(20, hauteurPoutre - 10)} cm`, armatures: '3 HA 12 filantes', locked: false, statut: 'propose' },
    ],
    semelles: [
      { id: 'SEM-S1', elementId: null, name: 'Semelle S1 (Poteau C1)', contrainteSol: `${sigmaSol} MPa`, section: `${coteSemelle.toFixed(2)} x ${coteSemelle.toFixed(2)} m`, hauteur: '40 cm', locked: false, statut: 'propose' },
    ],
  };
}

function simulateDQELocal(sections) {
  const nbPoteaux = (sections?.poteaux || []).length || 12;
  const volumeBetonPoteaux = nbPoteaux * 0.2 * 0.3 * 3.0;
  const volumeBetonPoutres = 8 * 0.2 * 0.4 * 6.0;
  const volumeBetonSemelles = nbPoteaux * 1.2 * 1.2 * 0.4;

  const totalBeton = (volumeBetonPoteaux + volumeBetonPoutres + volumeBetonSemelles).toFixed(2);
  const poidsAcier = (totalBeton * 90).toFixed(0);
  const sacsCiment = Math.ceil(totalBeton * 7);

  const prixBetonM3 = 65000;
  const prixAcierKg = 750;
  const prixCimentSac = 4800;

  const costBeton = totalBeton * prixBetonM3;
  const costAcier = poidsAcier * prixAcierKg;
  const costTotal = costBeton + costAcier;

  return {
    quantites: [
      { materiau: 'Béton Armé dosé à 350 kg/m³', unite: 'm³', quantite: totalBeton, prixUnitaire: `${prixBetonM3.toLocaleString()} FCFA`, total: `${costBeton.toLocaleString()} FCFA` },
      { materiau: 'Acier Haute Adhérence (FeE500)', unite: 'kg', quantite: poidsAcier, prixUnitaire: `${prixAcierKg.toLocaleString()} FCFA`, total: `${costAcier.toLocaleString()} FCFA` },
      { materiau: 'Ciment Portland CPJ 45 (Est. Sacs)', unite: 'sacs (50kg)', quantite: sacsCiment, prixUnitaire: `${prixCimentSac.toLocaleString()} FCFA`, total: `${(sacsCiment * prixCimentSac).toLocaleString()} FCFA` },
    ],
    montantTotalFCFA: `${costTotal.toLocaleString()} FCFA`,
    explicationIA:
      "Devis estimé localement (API indisponible) sur la base d'un ratio d'armatures de 90 kg/m³. Validation humaine obligatoire avant commande.",
  };
}
