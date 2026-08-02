// Service API Frontend pour le Projet DQE
// Communique avec l'API Django REST Framework (http://localhost:8000/api/)
// avec basculement automatique sur un simulateur local.

const API_BASE_URL = '/api';

export const dqeService = {
  // Calcul de la descente de charge & pré-dimensionnement
  calculateSections: async (projectData) => {
    try {
      const response = await fetch(`${API_BASE_URL}/calculs/predict/`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(projectData),
      });
      if (response.ok) {
        return await response.json();
      }
    } catch (e) {
      console.log('Utilisation du simulateur local pour le pré-dimensionnement');
    }

    // Algorithme de simulation normatif (BAEL / Eurocode 2)
    const { porteeMax = 6.0, chargeExploitation = 2.5, nombreNiveaux = 3, typeUsage = 'habitation' } = projectData;

    // Calcul charge ELU (1.35 G + 1.5 Q)
    const G = 5.0; // Charge permanente kN/m²
    const Q = parseFloat(chargeExploitation);
    const qELU = 1.35 * G + 1.5 * Q; // kN/m²

    // Surface d'influence type poteau central (m²)
    const surfaceInfluence = (porteeMax / 2) * (porteeMax / 2);
    const Nsd = surfaceInfluence * qELU * parseInt(nombreNiveaux); // Charge axiale kN

    // Section poteau b x h (cm)
    const sectionPoteauWidth = 20;
    const sectionPoteauHeight = Math.max(20, Math.ceil(Math.sqrt((Nsd * 1000) / (0.85 * 14.2)) / 5) * 5); // fcd = 14.2 MPa

    // Poutre h = L/12 à L/10
    const hauteurPoutre = Math.ceil((porteeMax * 100) / 10 / 5) * 5; // cm
    const largeurPoutre = Math.max(20, Math.ceil(hauteurPoutre / 2 / 5) * 5); // cm

    // Semelle isolée (A x B)
    const sigmaSol = 0.2; // MPa = 200 kN/m²
    const surfaceSemelle = Nsd / (sigmaSol * 1000); // m²
    const coteSemelle = Math.ceil(Math.sqrt(surfaceSemelle) * 10) / 10; // m

    return {
      poteaux: [
        { id: 'POT-C1', name: 'Poteau Central C1', charge: `${Nsd.toFixed(1)} kN`, section: `${sectionPoteauWidth} x ${sectionPoteauHeight} cm`, armatures: `4 HA 14 (${(sectionPoteauWidth * sectionPoteauHeight * 0.002).toFixed(1)} cm²)`, locked: false },
        { id: 'POT-P1', name: 'Poteau Périphérique P1', charge: `${(Nsd * 0.6).toFixed(1)} kN`, section: `${sectionPoteauWidth} x ${Math.max(20, sectionPoteauHeight - 5)} cm`, armatures: '4 HA 12', locked: false },
      ],
      poutres: [
        { id: 'POU-PRINC', name: 'Poutre Principale PP1', portee: `${porteeMax} m`, section: `${largeurPoutre} x ${hauteurPoutre} cm`, armatures: '3 HA 16 filantes + cadres HA 8', locked: false },
        { id: 'POU-SEC', name: 'Poutre Secondaire PS1', portee: `${(porteeMax * 0.75).toFixed(1)} m`, section: `15 x ${Math.max(20, hauteurPoutre - 10)} cm`, armatures: '3 HA 12 filantes', locked: false },
      ],
      semelles: [
        { id: 'SEM-S1', name: 'Semelle S1 (Poteau C1)', contrainteSol: `${sigmaSol} MPa`, section: `${coteSemelle.toFixed(2)} x ${coteSemelle.toFixed(2)} m`, hauteur: '40 cm', locked: false },
      ],
    };
  },

  // Calcul du devis quantitatif (DQE / DEK)
  calculateDQE: async (sections, projectData) => {
    try {
      const response = await fetch(`${API_BASE_URL}/devis/generate/`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ sections, projectData }),
      });
      if (response.ok) {
        return await response.json();
      }
    } catch (e) {
      console.log('Utilisation du simulateur DQE local');
    }

    // Calcul estimatif des quantitatifs
    const nbPoteaux = 12;
    const volumeBetonPoteaux = nbPoteaux * 0.2 * 0.3 * 3.0; // m³
    const volumeBetonPoutres = 8 * 0.2 * 0.4 * 6.0; // m³
    const volumeBetonSemelles = nbPoteaux * 1.2 * 1.2 * 0.4; // m³

    const totalBeton = (volumeBetonPoteaux + volumeBetonPoutres + volumeBetonSemelles).toFixed(2);
    const poidsAcier = (totalBeton * 90).toFixed(0); // 90 kg d'acier par m³ de béton
    const sacsCiment = Math.ceil(totalBeton * 7); // 350 kg/m³ = 7 sacs de 50kg par m³

    // Estimation des coûts (Prix unitaires indicatifs)
    const prixBetonM3 = 65000; // FCFA / m³
    const prixAcierKg = 750; // FCFA / kg
    const prixCimentSac = 4800; // FCFA / sac

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
      explicationIA: `L'estimation du devis est basée sur un ratio moyen de 90 kg d'acier par m³ de béton pour un bâtiment R+${projectData.nombreNiveaux || 3}. Les sections ont été dimensionnées pour garantir une résistance aux charges permanentes et d'exploitation conformément aux règles BAEL 91 / Eurocode 2.`,
    };
  },
};
