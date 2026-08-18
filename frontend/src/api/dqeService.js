// Service API Frontend pour le Projet DQE
// Aligné sur l'API Django REST Framework réelle d'Ange Yeo (voir api/urls.py, projets/models.py)
//
// MODIFIÉ (revue) : les fallbacks silencieux vers des données 100%
// inventées (simulateSectionsLocal, simulateDQELocal) ont été
// supprimés. Ils masquaient toute erreur réelle du backend (élément
// non validé, moteur indisponible, id mal formé...) derrière un faux
// résultat plausible -- exactement le genre de chose qui casse une
// démo sans prévenir personne. Les erreurs remontent maintenant
// réellement (throw) pour que l'interface puisse les afficher.
//
// Exception assumée : le calcul PAR ÉLÉMENT (createAndCalculateElements)
// continue à capturer une erreur 503 individuelle et à la transformer
// en "Calcul manuel requis" affiché à l'écran -- ce n'est pas un
// masquage silencieux, c'est un état réel et visible (erreur_calcul
// stocké et affiché), pas une valeur inventée à sa place.
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
  //
  // Note : si le calcul d'UN élément échoue (503, moteur indisponible
  // pour ce cas), c'est capturé et affiché comme "Calcul manuel
  // requis" -- un vrai état, pas une valeur inventée. Si la CRÉATION
  // d'un élément échoue (400, mauvais champ), en revanche, l'erreur
  // remonte normalement : créer un élément avec des données invalides
  // n'est jamais un cas à masquer.
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
      // CORRIGÉ : taux_travail_sol=2.0 était envoyé en dur ici, alors
      // que la formule backend (dimensionnement_semelles.py) attend
      // cette valeur en kN/m² (défaut réaliste : 180 kN/m², cf.
      // CONTRAINTE_SOL_DEFAUT). 2.0 ressemblait à une saisie en kg/cm²
      // mal convertie -- elle sous-estimait la portance du sol d'un
      // facteur ~90, produisant des semelles ~90x trop grandes (ex:
      // 6,87 m de côté au lieu de 72,5 cm pour une charge de 94,5 kN).
      // En omettant le champ, le backend applique son propre défaut
      // réaliste (voir hypothese_sol dans la réponse).
      { type_element: 'semelle', identifiant: 'SEM-S1', charge_calculee: chargeCalculeePoteau },
    ];

    const elements = [];
    for (const base of elementsACreer) {
      // Création : n'importe quelle erreur ici (400, réseau, backend
      // hors ligne) doit remonter telle quelle -- pas de fallback.
      const created = await postJSON(`${API_BASE_URL}/elements/`, { projet: projetId, ...base });

      try {
        const calcule = await postJSON(`${API_BASE_URL}/elements/${created.id}/calculer/`, undefined);
        elements.push(calcule);
      } catch (calcErr) {
        // Cas légitime : le moteur n'a pas de formule pour ce cas
        // précis (503). État réel affiché à l'écran, pas une donnée
        // inventée à la place.
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

  // Calcule le pré-dimensionnement via le vrai backend DRF.
  // MODIFIÉ : ne bascule plus vers un simulateur local en cas d'échec
  // -- toute erreur (backend hors ligne, projet mal formé...) remonte
  // à l'appelant, qui doit l'afficher clairement à l'utilisateur.
  calculateSections: async (projectData) => {
    const projet = await dqeService.createProjet(projectData);
    const elements = await dqeService.createAndCalculateElements(projet.id, projectData);
    return { projetId: projet.id, ...parseDRFResponse(elements) };
  },

  // AJOUTÉ : postes de main d'œuvre -- le backend les gère déjà
  // entièrement (modèle PosteMainDoeuvre, CRUD complet, intégration
  // dans dqe_calculator.py ET dans les exports PDF/Excel, voir
  // "Sous-total Main d'œuvre") mais aucune interface ne les créait
  // jamais côté frontend. Contrairement aux éléments structurels, ce
  // sont des postes saisis manuellement par l'ingénieur (main d'œuvre,
  // terrassement, etc.), jamais calculés automatiquement.
  listerPostesMainDoeuvre: async (projetId) => {
    if (!projetId) return [];
    const response = await fetch(`${API_BASE_URL}/postes-main-doeuvre/?projet=${projetId}`);
    const data = await response.json().catch(() => null);
    if (!response.ok) {
      const err = new Error((data && (data.erreur || data.detail)) || `Erreur ${response.status}`);
      err.status = response.status;
      throw err;
    }
    return Array.isArray(data) ? data : data.results || [];
  },

  ajouterPosteMainDoeuvre: async (projetId, poste) => {
    if (!projetId) {
      throw new Error("Aucun projet actif -- impossible d'ajouter un poste de main d'œuvre.");
    }
    return postJSON(`${API_BASE_URL}/postes-main-doeuvre/`, {
      projet: projetId,
      designation: poste.designation,
      unite: poste.unite,
      quantite: parseFloat(poste.quantite),
      prix_unitaire: parseFloat(poste.prixUnitaire),
    });
  },

  supprimerPosteMainDoeuvre: async (posteId) => {
    const response = await fetch(`${API_BASE_URL}/postes-main-doeuvre/${posteId}/`, {
      method: 'DELETE',
    });
    if (!response.ok && response.status !== 204) {
      const data = await response.json().catch(() => null);
      const err = new Error((data && (data.erreur || data.detail)) || `Erreur ${response.status}`);
      err.status = response.status;
      throw err;
    }
    return true;
  },

  // Valide/verrouille un élément côté backend
  validerElementDRF: async (elementId, resultatValide) => {
    if (!elementId) {
      throw new Error(
        "elementId manquant -- impossible de valider un élément sans son id numérique réel."
      );
    }
    return postJSON(`${API_BASE_URL}/elements/${elementId}/valider/`, {
      resultat_valide: resultatValide,
    });
  },

  // Structuration NLP par Assistant IA.
  // MODIFIÉ : ne renvoie plus un message générique "(mode local)" en
  // cas d'échec -- l'IA est une couche d'interface optionnelle, mais
  // faire semblant qu'elle a répondu quand ce n'est pas le cas reste
  // trompeur. L'erreur remonte, à l'UI de dire "assistant indisponible".
  structurerProjetIA: async (descriptionText) => {
    return postJSON(`${API_BASE_URL}/assistant/structurer-projet/`, {
      description: descriptionText,
    });
  },

  // Explication d'un élément par Assistant IA -- même principe.
  expliquerElementIA: async (elementId) => {
    return postJSON(`${API_BASE_URL}/assistant/expliquer-element/`, {
      element_id: elementId,
    });
  },

  // AJOUTÉ : télécharge le DQE au format PDF ou Excel via le vrai
  // endpoint backend (?export=pdf|excel, voir projets/views.py +
  // projets/services/dqe_exporters.py) -- jusqu'ici Step4_DQEExport.jsx
  // n'appelait rien du tout (juste un alert() factice), alors que le
  // backend générait déjà correctement ces fichiers.
  //
  // Différence importante avec les autres appels de ce service : la
  // réponse ici n'est PAS du JSON mais un fichier binaire (le
  // Content-Type est application/pdf ou .xlsx), donc on ne peut pas
  // réutiliser postJSON -- il faut lire la réponse comme un Blob et
  // déclencher le téléchargement navigateur nous-mêmes.
  telechargerDQEFichier: async (projetId, format) => {
    if (!projetId) {
      throw new Error(
        "Aucun projet actif -- impossible de télécharger le DQE sans projetId."
      );
    }
    if (format !== 'pdf' && format !== 'excel') {
      throw new Error(`Format d'export invalide : "${format}" (attendu : "pdf" ou "excel").`);
    }

    const response = await fetch(`${API_BASE_URL}/projets/${projetId}/generer_dqe/?export=${format}`, {
      method: 'GET',
    });

    if (!response.ok) {
      // En cas d'erreur, le backend répond en JSON (ex: "éléments non
      // validés") et non en binaire -- on le lit comme tel pour un
      // message clair plutôt qu'un blob illisible.
      const data = await response.json().catch(() => null);
      const err = new Error((data && data.erreur) || `Erreur ${response.status}`);
      err.status = response.status;
      err.data = data;
      throw err;
    }

    const blob = await response.blob();

    // Récupère le nom de fichier proposé par le backend
    // (Content-Disposition: attachment; filename="DQE_xxx.pdf")
    // plutôt que d'en inventer un côté frontend, pour rester cohérent
    // avec ce que le backend a réellement nommé.
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

    return { filename };
  },

  // Génère le DQE via l'API DRF avec le vrai projetId.
  // MODIFIÉ : plus de fallback vers simulateDQELocal. Un projetId
  // manquant ou une erreur backend (ex. éléments non validés) sont
  // désormais de vraies erreurs visibles, pas un faux devis silencieux.
  calculateDQE: async (projetId, sections) => {
    if (!projetId) {
      throw new Error(
        "Aucun projet actif -- calculateSections() doit réussir avant calculateDQE()."
      );
    }
    const response = await fetch(`${API_BASE_URL}/projets/${projetId}/generer_dqe/`, {
      method: 'GET',
    });
    const data = await response.json().catch(() => null);
    if (!response.ok) {
      const err = new Error((data && data.erreur) || `Erreur ${response.status}`);
      err.status = response.status;
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
    elementId: e.id, // id numérique réel -- c'est LUI qu'il faut utiliser pour tout appel API
    name: e.identifiant,
    section: calculIndisponible ? 'Calcul manuel requis' : formatSection(e.type_element, res),
    armatures: calculIndisponible ? '—' : formatArmatures(e.type_element, res),
    // AJOUTÉ : Step2_Calculs.jsx affiche ces 4 champs (colonnes "Effort
    // Axial", "Portée L", "Contrainte du Sol", "Hauteur h") mais ils
    // n'étaient jamais renseignés ici -- les colonnes s'affichaient
    // vides silencieusement, sans erreur visible.
    charge: e.charge_calculee != null ? `${e.charge_calculee} kN` : 'n/d',
    portee: e.portee != null ? `${e.portee} m` : 'n/d',
    contrainteSol: e.taux_travail_sol != null ? `${e.taux_travail_sol} kN/m²` : 'Défaut (180 kN/m²)',
    hauteur: res.hauteur_cm != null ? `${res.hauteur_cm} cm` : 'n/d',
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
    // Semelle isolée carrée (dimensionner_semelle) -> cote_cm + hauteur_cm
    if (res.cote_cm && res.hauteur_cm) return `${res.cote_cm} x ${res.cote_cm} x ${res.hauteur_cm} cm`;
    // Semelle filante (dimensionner_semelle_filante) -> largeur_cm + hauteur_cm
    if (res.largeur_cm && res.hauteur_cm) return `${res.largeur_cm} x ${res.hauteur_cm} cm`;
    // Semelle rectangulaire affinée (dimensionner_semelle_affinee) -> grand/petit_cote_cm
    if (res.grand_cote_cm && res.petit_cote_cm && res.hauteur_cm) {
      return `${res.grand_cote_cm} x ${res.petit_cote_cm} x ${res.hauteur_cm} cm`;
    }
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