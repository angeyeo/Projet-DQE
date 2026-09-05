import React, { useState, useEffect } from 'react';
import Sidebar from './components/Sidebar';
import TopBar from './components/TopBar';
import DashboardView from './components/DashboardView';
import Step1_Parametres from './components/Step1_Parametres';
import StepDalles from './components/StepDalles';
import Step2_Calculs from './components/Step2_Calculs';
import Step3_ValidationLock from './components/Step3_ValidationLock';
import StepPlanFondation from './components/StepPlanFondation';
import Step4_DQEExport from './components/Step4_DQEExport';
import SettingsEntreprise from './components/settingsentreprise';
import { dqeService } from './api/dqeService';

export default function App() {
  // Persistence de la vue active au rafraîchissement (F5)
  const [activeView, setActiveView] = useState(() => {
    return localStorage.getItem('dqe_active_view') || 'dashboard';
  });

  useEffect(() => {
    localStorage.setItem('dqe_active_view', activeView);
  }, [activeView]);

  const [isCollapsed, setIsCollapsed] = useState(false);

  // État du Projet BTP
  const [projectData, setProjectData] = useState({
    nomProjet: '',
    numeroDevis: '',
    planFileName: '',
    planFileSize: '',
    typeUsage: 'habitation',
    nombreNiveaux: '',
    nbTraveesX: '',
    nbTraveesY: '',
    porteeX: '',
    porteeY: '',
    hauteurEtage: '',
    chargeExploitation: '',
    norme: 'BAEL91',
  });

  // Charges permanentes composées
  const [couchesG, setCouchesG] = useState([]);

  // Sections calculées
  const [sections, setSections] = useState({
    poteaux: [],
    poutres: [],
    semelles: [],
  });

  // Données du Devis DQE
  const [dqeData, setDqeData] = useState(null);

  // Verrouillage et validation
  const [validationError, setValidationError] = useState(null);
  const [validatingId, setValidatingId] = useState(null);

  // Postes de main d'œuvre saisis manuellement
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
    try {
      const totalG = couchesG.reduce((sum, c) => sum + (parseFloat(c.chargeG) || 0), 0);
      const updatedData = { ...projectData, chargePermanenteG: totalG > 0 ? totalG : 5.0 };
      const results = await dqeService.calculateSections(updatedData);
      setSections(results);
      setPostesMainDoeuvre([]);
      setMainDoeuvreError(null);
      setActiveView('step2');
    } catch (err) {
      console.error("Erreur lors du calcul :", err);
      // Ancien comportement : on avançait quand même vers step2 malgré l'échec.
      // Problème : sections.projetId n'est alors jamais renseigné (sections
      // garde sa valeur initiale {poteaux:[], poutres:[], semelles:[]}), ce qui
      // fait échouer silencieusement StepPlanFondation plus loin dans le
      // parcours (chargerPlanFondation() ne se déclenche jamais sans projetId,
      // et le téléchargement DXF échoue aussi) -- sans qu'aucun message n'aide
      // à comprendre pourquoi. On informe maintenant l'utilisateur et on reste
      // sur l'étape courante plutôt que d'avancer vers un état cassé.
      alert(
        "Impossible de lancer le calcul : " + (err.message || "erreur inconnue") +
        "\n\nVous êtes maintenu sur cette étape -- corrigez le problème (ou réessayez) avant de continuer."
      );
    }
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
      setValidationError(`Impossible de générer le DQE : ${err.message}`);
    }
  };

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

  const formatSectionManuelle = (item, category) => {
    if (category === 'Poteau') return `${item.manualCoteCm} x ${item.manualCoteCm} cm`;
    if (category === 'Poutre') return `${item.manualLargeurCm} x ${item.manualHauteurCm} cm`;
    if (category === 'Semelle') return `${item.manualCoteCm} x ${item.manualCoteCm} x ${item.manualHauteurCm} cm`;
    return item.section;
  };

  const categoryToKey = (category) => {
    if (category === 'Poteau') return 'poteaux';
    return category.toLowerCase() + 's';
  };

  const toggleLock = async (id, category) => {
    const key = categoryToKey(category);
    const item = (sections[key] || []).find((el) => el.id === id);
    if (!item) return;

    setValidationError(null);
    let resultatManuel = null;

    if (!item.locked) {
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
        await dqeService.validerElementDRF(item.elementId, resultatManuel || undefined);
      } catch (err) {
        setValidationError(`Impossible de valider ${item.name} : ${err.message}`);
        setValidatingId(null);
        return;
      }
      setValidatingId(null);
    }

    setSections((prev) => ({
      ...prev,
      [key]: prev[key].map((el) => {
        if (el.id !== id) return el;
        const updated = { ...el, locked: !el.locked };
        if (resultatManuel) {
          updated.calculIndisponible = false;
          updated.erreurCalcul = null;
          updated.resultat = resultatManuel;
          updated.section = formatSectionManuelle(el, category);
        }
        return updated;
      }),
    }));
  };

  const toggleLockAll = async (lockState) => {
    setValidationError(null);

    const parLot = [
      ...sections.poteaux.map((el) => ({ el, category: 'Poteau' })),
      ...sections.poutres.map((el) => ({ el, category: 'Poutre' })),
      ...sections.semelles.map((el) => ({ el, category: 'Semelle' })),
    ];

    if (lockState) {
      const nonValides = parLot.filter(({ el }) => !el.locked);

      const manuels = new Map();
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
        await Promise.all(
          nonValides.map(({ el }) =>
            dqeService.validerElementDRF(el.elementId, manuels.get(el.elementId))
          )
        );
      } catch (err) {
        setValidationError(`Erreur lors de la validation groupée : ${err.message}`);
        return;
      }

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
              onNext={() => setActiveView('step3bis')}
            />
          )}

          {activeView === 'step3bis' && (
            <StepPlanFondation
              projetId={sections.projetId}
              sections={sections}
              onBack={() => setActiveView('step3')}
              onNext={handleGenerateDQE}
            />
          )}

          {activeView === 'step4' && (
            <Step4_DQEExport
              dqeData={dqeData || {}}
              projectData={projectData}
              projetId={sections.projetId}
              onBack={() => setActiveView('step3bis')}
              onReset={() => {
                setPostesMainDoeuvre([]);
                setMainDoeuvreError(null);
                setActiveView('step1');
              }}
            />
          )}

          {activeView === 'settingsEntreprise' && (
            <SettingsEntreprise />
          )}
        </main>
      </div>
    </div>
  );
}