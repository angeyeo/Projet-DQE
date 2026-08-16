import React, { useState } from 'react';
import Sidebar from './components/Sidebar';
import TopBar from './components/TopBar';
import DashboardView from './components/DashboardView';
import Step1_Parametres from './components/Step1_Parametres';
import StepDalles from './components/StepDalles';
import Step2_Calculs from './components/Step2_Calculs';
import Step3_ValidationLock from './components/Step3_ValidationLock';
import Step4_DQEExport from './components/Step4_DQEExport';
import { dqeService } from './api/dqeService';

export default function App() {
  const [activeView, setActiveView] = useState('dashboard');
  const [isCollapsed, setIsCollapsed] = useState(false);

  // État du Projet BTP Phase 2
  const [projectData, setProjectData] = useState({
    nomProjet: '',
    planFileName: '',
    planFileSize: '',
    typeUsage: 'habitation',
    nombreNiveaux: '',
    porteeMax: '',
    chargeExploitation: '',
    norme: 'BAEL91',
  });

  // Charges permanentes composées (Module 2 Multi-couches Phase 2)
  const [couchesG, setCouchesG] = useState([]);

  // Sections calculées (Phase 2)
  const [sections, setSections] = useState({
    poteaux: [],
    poutres: [],
    semelles: [],
  });

  // Données du Devis DQE
  const [dqeData, setDqeData] = useState(null);

  // MODIFIÉ (Ange) : nécessaires pour que le verrouillage appelle
  // réellement /api/elements/{id}/valider/ au lieu de rester un simple
  // état visuel local -- voir toggleLock ci-dessous.
  const [validationError, setValidationError] = useState(null);
  const [validatingId, setValidatingId] = useState(null);

  // AJOUTÉ : postes de main d'œuvre saisis manuellement par
  // l'ingénieur (voir Step3_ValidationLock.jsx) -- distincts des
  // éléments structurels calculés automatiquement.
  const [postesMainDoeuvre, setPostesMainDoeuvre] = useState([]);
  const [mainDoeuvreError, setMainDoeuvreError] = useState(null);

  const ajouterPosteMainDoeuvre = async (poste) => {
    setMainDoeuvreError(null);
    try {
      const created = await dqeService.ajouterPosteMainDoeuvre(sections.projetId, poste);
      setPostesMainDoeuvre((prev) => [...prev, created]);
    } catch (err) {
      setMainDoeuvreError(`Impossible d'ajouter le poste : ${err.message}`);
    }
  };

  const supprimerPosteMainDoeuvre = async (posteId) => {
    setMainDoeuvreError(null);
    try {
      await dqeService.supprimerPosteMainDoeuvre(posteId);
      setPostesMainDoeuvre((prev) => prev.filter((p) => p.id !== posteId));
    } catch (err) {
      setMainDoeuvreError(`Impossible de supprimer le poste : ${err.message}`);
    }
  };

  const updateProjectData = (newFields) => {
    setProjectData((prev) => ({ ...prev, ...newFields }));
  };

  const handleCalculate = async () => {
    const totalG = couchesG.reduce((sum, c) => sum + (parseFloat(c.chargeG) || 0), 0);
    const updatedData = { ...projectData, chargePermanenteG: totalG > 0 ? totalG : 5.0 };
    const results = await dqeService.calculateSections(updatedData);
    setSections(results);
    setPostesMainDoeuvre([]); // nouveau projet -> pas de postes hérités de l'ancien
    setMainDoeuvreError(null);
    setActiveView('step2');
  };

  const handleGoToValidation = () => {
    setActiveView('step3');
  };

  const handleGenerateDQE = async () => {
    setValidationError(null);
    try {
      const dqeResults = await dqeService.calculateDQE(sections.projetId, sections);
      setDqeData(dqeResults);
      setActiveView('step4');
    } catch (err) {
      // MODIFIÉ (Ange) : avant, une erreur ici (ex. "éléments non
      // validés") n'était jamais affichée -- l'utilisateur restait
      // bloqué sur step3 sans comprendre pourquoi.
      setValidationError(`Impossible de générer le DQE : ${err.message}`);
    }
  };

  // MODIFIÉ (Ange) : toggleLock ne faisait qu'un setSections() local,
  // sans jamais appeler le backend -- donc un élément "verrouillé" à
  // l'écran restait au statut "propose" côté serveur, et
  // /generer_dqe/ refusait ensuite (400, éléments non validés), sans
  // que l'utilisateur comprenne pourquoi puisque l'UI affichait tout
  // en vert. Verrouiller un élément appelle maintenant réellement
  // /api/elements/{id}/valider/ avant de mettre à jour l'affichage.
  //
  // Note : il n'existe pas d'endpoint pour "dé-valider" côté backend.
  // Déverrouiller ici ne fait donc que ré-autoriser l'édition locale
  // (les champs redeviennent modifiables) -- il faudra re-cliquer
  // "Verrouiller" pour revalider réellement avant de générer le DQE.
  // AJOUTÉ : construit le resultat_valide numérique attendu par le
  // backend (voir projets/services/dqe_calculator.py) à partir des
  // champs saisis manuellement par l'ingénieur, pour un élément dont
  // le moteur de calcul n'a pas pu produire de résultat (503).
  // Sans ces clés numériques exactes (cote_cm / largeur_cm / hauteur_cm),
  // dqe_calculator.py renvoie silencieusement [] pour cet élément --
  // aucune ligne de béton/coffrage/acier générée dans le devis, sans
  // erreur visible. On valide donc ici AVANT tout appel API.
  const buildResultatManuel = (item, category) => {
    if (category === 'Poteau') {
      const cote = parseFloat(item.manualCoteCm);
      if (!cote || cote <= 0) {
        return { error: 'Renseignez un côté de poteau (cm) valide avant de verrouiller.' };
      }
      return { value: { cote_cm: cote, manuel: true } };
    }
    if (category === 'Poutre') {
      const largeur = parseFloat(item.manualLargeurCm);
      const hauteur = parseFloat(item.manualHauteurCm);
      if (!largeur || largeur <= 0 || !hauteur || hauteur <= 0) {
        return { error: 'Renseignez une largeur ET une hauteur (cm) valides avant de verrouiller.' };
      }
      return { value: { largeur_cm: largeur, hauteur_cm: hauteur, manuel: true } };
    }
    if (category === 'Semelle') {
      const cote = parseFloat(item.manualCoteCm);
      const hauteur = parseFloat(item.manualHauteurCm);
      if (!cote || cote <= 0 || !hauteur || hauteur <= 0) {
        return { error: 'Renseignez un côté ET une hauteur (cm) valides avant de verrouiller.' };
      }
      return { value: { cote_cm: cote, hauteur_cm: hauteur, manuel: true } };
    }
    return { error: `Saisie manuelle non prise en charge pour le type "${category}".` };
  };

  // Fige l'affichage (colonne "Section") d'un élément qui vient d'être
  // validé manuellement, pour qu'il ne reste pas affiché "Calcul manuel
  // requis" après verrouillage alors qu'une valeur réelle a été envoyée.
  const formatSectionManuelle = (item, category) => {
    if (category === 'Poteau') return `${item.manualCoteCm} x ${item.manualCoteCm} cm`;
    if (category === 'Poutre') return `${item.manualLargeurCm} x ${item.manualHauteurCm} cm`;
    if (category === 'Semelle') return `${item.manualCoteCm} x ${item.manualCoteCm} x ${item.manualHauteurCm} cm`;
    return item.section;
  };

  // CORRIGÉ : category.toLowerCase() + 's' donnait "poteaus" pour la
  // catégorie "Poteau" (pluriel français correct : "poteaux", avec un
  // x) -- une clé qui n'existe pas dans `sections`. Résultat :
  // sections["poteaus"] valait undefined, (undefined || []).find(...)
  // ne trouvait jamais l'élément, et toggleLock/updateSection
  // s'arrêtaient silencieusement (if (!item) return;) sans le moindre
  // appel réseau ni message d'erreur -- clic sur "Valider &
  // Verrouiller" sans aucun effet, pour les poteaux uniquement
  // (Poutre -> "poutres" et Semelle -> "semelles" étaient déjà corrects
  // par coïncidence).
  const categoryToKey = (category) => {
    if (category === 'Poteau') return 'poteaux';
    return category.toLowerCase() + 's';
  };

  const toggleLock = async (id, category) => {
    const key = categoryToKey(category);
    const item = (sections[key] || []).find((el) => el.id === id);
    if (!item) return;

    setValidationError(null);
    let resultatManuel = null; // objet { cote_cm, ... } si saisie manuelle requise

    if (!item.locked) {
      // Élément sans résultat backend (503 lors du /calculer/) : on
      // n'appelle l'API QUE si l'ingénieur a rempli des dimensions
      // numériques valides -- sinon on bloque tout de suite avec un
      // message clair au lieu de laisser le backend renvoyer un 400
      // "Aucun résultat de calcul disponible à valider" incompréhensible.
      if (item.calculIndisponible) {
        const manuel = buildResultatManuel(item, category);
        if (manuel.error) {
          setValidationError(`${item.name} : ${manuel.error}`);
          return;
        }
        resultatManuel = manuel.value;
      }

      setValidatingId(id);
      try {
        // CORRIGÉ : item.id est l'identifiant TEXTE ("SEM-S1"), pas
        // l'id numérique attendu par l'URL DRF (/api/elements/{id}/valider/)
        // -- d'où le 404 "SEM-S1" observé. Le vrai id numérique est
        // dans item.elementId (voir dqeService.js::formatElement).
        // Si resultatManuel est renseigné, on l'envoie explicitement ;
        // sinon (calcul automatique déjà réussi) on laisse le backend
        // utiliser resultat_calcul par défaut.
        await dqeService.validerElementDRF(item.elementId, resultatManuel || undefined);
      } catch (err) {
        setValidationError(`Impossible de valider ${item.name} : ${err.message}`);
        setValidatingId(null);
        return; // on ne verrouille PAS visuellement si le backend a refusé
      }
      setValidatingId(null);
    }

    setSections((prev) => ({
      ...prev,
      [key]: prev[key].map((el) => {
        if (el.id !== id) return el;
        const updated = { ...el, locked: !el.locked };
        if (resultatManuel) {
          // On vient de valider manuellement : on fige l'affichage sur
          // les valeurs réellement envoyées au backend.
          updated.calculIndisponible = false;
          updated.erreurCalcul = null;
          updated.resultat = resultatManuel;
          updated.section = formatSectionManuelle(el, category);
        }
        return updated;
      }),
    }));
  };

  // MODIFIÉ (Ange) : même correction pour le verrouillage groupé --
  // valide réellement chaque élément non encore verrouillé avant de
  // mettre à jour l'affichage. Si un élément échoue, aucun n'est
  // marqué verrouillé localement (tout ou rien, pour éviter un état
  // incohérent entre l'UI et le backend).
  const toggleLockAll = async (lockState) => {
    setValidationError(null);

    // categorie associée à chaque élément, pour retrouver le bon type
    // lors de la construction du resultat_valide manuel
    const parLot = [
      ...sections.poteaux.map((el) => ({ el, category: 'Poteau' })),
      ...sections.poutres.map((el) => ({ el, category: 'Poutre' })),
      ...sections.semelles.map((el) => ({ el, category: 'Semelle' })),
    ];

    if (lockState) {
      const nonValides = parLot.filter(({ el }) => !el.locked);

      // Vérification préalable de TOUTES les saisies manuelles avant
      // le moindre appel réseau -- pour éviter de valider certains
      // éléments et pas d'autres en cas d'erreur groupée (tout ou rien).
      const manuels = new Map(); // elementId -> resultat_valide
      for (const { el, category } of nonValides) {
        if (el.calculIndisponible) {
          const manuel = buildResultatManuel(el, category);
          if (manuel.error) {
            setValidationError(`${el.name} : ${manuel.error}`);
            return;
          }
          manuels.set(el.elementId, manuel.value);
        }
      }

      try {
        // CORRIGÉ : el.elementId (numérique), pas el.id (identifiant texte)
        await Promise.all(
          nonValides.map(({ el }) =>
            dqeService.validerElementDRF(el.elementId, manuels.get(el.elementId))
          )
        );
      } catch (err) {
        setValidationError(`Erreur lors de la validation groupée : ${err.message}`);
        return;
      }

      // CORRIGÉ : ces deux setSections() reconstruisaient l'objet
      // sections avec SEULEMENT {poteaux, poutres, semelles}, sans
      // spreader ...prev -- ce qui effaçait sections.projetId (stocké
      // au même niveau, voir calculateSections() dans dqeService.js)
      // à chaque clic sur "Verrouiller Toutes les Sections". Résultat:
      // handleGenerateDQE recevait ensuite un projetId undefined et
      // échouait avec "Aucun projet actif", même après une validation
      // par ailleurs réussie.
      setSections((prev) => ({
        ...prev,
        poteaux: prev.poteaux.map((el) =>
          manuels.has(el.elementId)
            ? { ...el, locked: true, calculIndisponible: false, erreurCalcul: null, resultat: manuels.get(el.elementId), section: formatSectionManuelle(el, 'Poteau') }
            : { ...el, locked: true }
        ),
        poutres: prev.poutres.map((el) =>
          manuels.has(el.elementId)
            ? { ...el, locked: true, calculIndisponible: false, erreurCalcul: null, resultat: manuels.get(el.elementId), section: formatSectionManuelle(el, 'Poutre') }
            : { ...el, locked: true }
        ),
        semelles: prev.semelles.map((el) =>
          manuels.has(el.elementId)
            ? { ...el, locked: true, calculIndisponible: false, erreurCalcul: null, resultat: manuels.get(el.elementId), section: formatSectionManuelle(el, 'Semelle') }
            : { ...el, locked: true }
        ),
      }));
      return;
    }

    setSections((prev) => ({
      ...prev,
      poteaux: prev.poteaux.map((item) => ({ ...item, locked: lockState })),
      poutres: prev.poutres.map((item) => ({ ...item, locked: lockState })),
      semelles: prev.semelles.map((item) => ({ ...item, locked: lockState })),
    }));
  };


  const updateSection = (id, category, field, value) => {
    const key = categoryToKey(category);
    setSections((prev) => ({
      ...prev,
      [key]: prev[key].map((item) =>
        item.id === id ? { ...item, [field]: value } : item
      ),
    }));
  };

  const allElements = [
    ...(sections.poteaux || []),
    ...(sections.poutres || []),
    ...(sections.semelles || []),
  ];
  const lockedCount = allElements.filter((e) => e.locked).length;

  return (
    <div className="app-layout">
      <Sidebar
        activeView={activeView}
        setActiveView={setActiveView}
        isCollapsed={isCollapsed}
        setIsCollapsed={setIsCollapsed}
        lockedCount={lockedCount}
        totalCount={allElements.length}
      />

      <div className="main-wrapper">
        <TopBar
          projectName={projectData.nomProjet || 'Nouveau Projet BTP'}
          onNewCalculation={() => setActiveView('step1')}
          lockedCount={lockedCount}
          totalCount={allElements.length}
        />

        <main className="content-body">
          {activeView === 'dashboard' && (
            <DashboardView
              projectData={projectData}
              sections={sections}
              lockedCount={lockedCount}
              totalCount={allElements.length}
              onNavigate={setActiveView}
            />
          )}

          {activeView === 'step1' && (
            <Step1_Parametres
              projectData={projectData}
              updateProjectData={updateProjectData}
              couchesG={couchesG}
              setCouchesG={setCouchesG}
              onNext={() => setActiveView('stepDalles')}
            />
          )}

          {activeView === 'stepDalles' && (
            <StepDalles
              projectData={projectData}
              onNext={handleCalculate}
            />
          )}

          {activeView === 'step2' && (
            <Step2_Calculs
              sections={sections}
              projectData={projectData}
              onBack={() => setActiveView('stepDalles')}
              onNext={handleGoToValidation}
            />
          )}

          {activeView === 'step3' && (
            <Step3_ValidationLock
              sections={sections}
              toggleLock={toggleLock}
              toggleLockAll={toggleLockAll}
              updateSection={updateSection}
              validationError={validationError}
              validatingId={validatingId}
              postesMainDoeuvre={postesMainDoeuvre}
              onAddPosteMainDoeuvre={ajouterPosteMainDoeuvre}
              onRemovePosteMainDoeuvre={supprimerPosteMainDoeuvre}
              mainDoeuvreError={mainDoeuvreError}
              onBack={() => setActiveView('step2')}
              onNext={handleGenerateDQE}
            />
          )}

          {activeView === 'step4' && (
            <Step4_DQEExport
              dqeData={dqeData || {}}
              projectData={projectData}
              projetId={sections.projetId}
              onBack={() => setActiveView('step3')}
              onReset={() => {
                setPostesMainDoeuvre([]);
                setMainDoeuvreError(null);
                setActiveView('step1');
              }}
            />
          )}
        </main>
      </div>
    </div>
  );
}