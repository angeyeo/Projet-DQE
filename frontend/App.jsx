import React, { useState, useEffect } from 'react';
import Header from './Header';
import Stepper from './Stepper';
import Step1_Parametres from './Step1_Parametres';
import Step2_Calculs from './Step2_Calculs';
import Step3_ValidationLock from './Step3_ValidationLock';
import Step4_DQEExport from './Step4_DQEExport';
import { dqeService } from './dqeService';

export default function App() {
  const [currentStep, setCurrentStep] = useState(1);
  const [completedSteps, setCompletedSteps] = useState([]);

  // État du Projet
  const [projectData, setProjectData] = useState({
    nomProjet: 'Résidence des Palmes R+3',
    planFileName: 'Plan_Coffrage_Niveau1.PLN',
    planFileSize: '4.2 MB',
    typeUsage: 'habitation',
    nombreNiveaux: 3,
    porteeMax: 6.0,
    chargeExploitation: 2.5,
    norme: 'BAEL91',
  });

  // Sections calculées
  const [sections, setSections] = useState({
    poteaux: [],
    poutres: [],
    semelles: [],
  });

  // Données du Devis DQE
  const [dqeData, setDqeData] = useState(null);

  // Mettre à jour les paramètres
  const updateProjectData = (newFields) => {
    setProjectData((prev) => ({ ...prev, ...newFields }));
  };

  // Lancer le calcul à l'étape 2
  const handleCalculate = async () => {
    const results = await dqeService.calculateSections(projectData);
    setSections(results);
    if (!completedSteps.includes(1)) {
      setCompletedSteps((prev) => [...prev, 1]);
    }
    setCurrentStep(2);
  };

  // Passer à l'étape 3 (Validation & Verrouillage)
  const handleGoToValidation = () => {
    if (!completedSteps.includes(2)) {
      setCompletedSteps((prev) => [...prev, 2]);
    }
    setCurrentStep(3);
  };

  // Passer à l'étape 4 (Génération DQE)
  const handleGenerateDQE = async () => {
    const dqeResults = await dqeService.calculateDQE(sections, projectData);
    setDqeData(dqeResults);
    if (!completedSteps.includes(3)) {
      setCompletedSteps((prev) => [...prev, 3]);
    }
    setCurrentStep(4);
  };

  // Basculer le verrou d'un élément
  const toggleLock = (id, category) => {
    const key = category.toLowerCase() + 's'; // poteaux, poutres, semelles
    setSections((prev) => ({
      ...prev,
      [key]: prev[key].map((item) =>
        item.id === id ? { ...item, locked: !item.locked } : item
      ),
    }));
  };

  // Verrouiller ou déverrouiller TOUTES les sections
  const toggleLockAll = (lockState) => {
    setSections((prev) => ({
      poteaux: prev.poteaux.map((item) => ({ ...item, locked: lockState })),
      poutres: prev.poutres.map((item) => ({ ...item, locked: lockState })),
      semelles: prev.semelles.map((item) => ({ ...item, locked: lockState })),
    }));
  };

  // Modifier une section non verrouillée
  const updateSection = (id, category, field, value) => {
    const key = category.toLowerCase() + 's';
    setSections((prev) => ({
      ...prev,
      [key]: prev[key].map((item) =>
        item.id === id ? { ...item, [field]: value } : item
      ),
    }));
  };

  // Calcul du nombre de sections verrouillées
  const allElements = [
    ...(sections.poteaux || []),
    ...(sections.poutres || []),
    ...(sections.semelles || []),
  ];
  const lockedCount = allElements.filter((e) => e.locked).length;

  return (
    <div className="app-container">
      <Header
        projectName={projectData.nomProjet}
        lockedCount={lockedCount}
        totalCount={allElements.length}
      />

      <Stepper
        currentStep={currentStep}
        setStep={setCurrentStep}
        completedSteps={completedSteps}
      />

      <main>
        {currentStep === 1 && (
          <Step1_Parametres
            projectData={projectData}
            updateProjectData={updateProjectData}
            onNext={handleCalculate}
          />
        )}

        {currentStep === 2 && (
          <Step2_Calculs
            sections={sections}
            projectData={projectData}
            onBack={() => setCurrentStep(1)}
            onNext={handleGoToValidation}
          />
        )}

        {currentStep === 3 && (
          <Step3_ValidationLock
            sections={sections}
            toggleLock={toggleLock}
            toggleLockAll={toggleLockAll}
            updateSection={updateSection}
            onBack={() => setCurrentStep(2)}
            onNext={handleGenerateDQE}
          />
        )}

        {currentStep === 4 && (
          <Step4_DQEExport
            dqeData={dqeData}
            projectData={projectData}
            onBack={() => setCurrentStep(3)}
            onReset={() => {
              setCurrentStep(1);
              setCompletedSteps([]);
            }}
          />
        )}
      </main>
    </div>
  );
}
