import React, { useState, useEffect } from 'react';
import Sidebar from './components/Sidebar';
import TopBar from './components/TopBar';
import DashboardView from './components/DashboardView';
import Step1_Parametres from './components/Step1_Parametres';
import Step2_Calculs from './components/Step2_Calculs';
import Step3_ValidationLock from './components/Step3_ValidationLock';
import Step4_DQEExport from './components/Step4_DQEExport';
import { dqeService } from './api/dqeService';

export default function App() {
  const [activeView, setActiveView] = useState('dashboard');
  const [isCollapsed, setIsCollapsed] = useState(false);

  // État du Projet BTP
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

  // Calcul automatique au chargement initial pour alimenter les KPIs
  useEffect(() => {
    handleCalculateInitial();
  }, []);

  const handleCalculateInitial = async () => {
    const results = await dqeService.calculateSections(projectData);
    setSections(results);
  };

  const updateProjectData = (newFields) => {
    setProjectData((prev) => ({ ...prev, ...newFields }));
  };

  const handleCalculate = async () => {
    const results = await dqeService.calculateSections(projectData);
    setSections(results);
    setActiveView('step2');
  };

  const handleGoToValidation = () => {
    setActiveView('step3');
  };

  const handleGenerateDQE = async () => {
    const dqeResults = await dqeService.calculateDQE(sections, projectData);
    setDqeData(dqeResults);
    setActiveView('step4');
  };

  const toggleLock = (id, category) => {
    const key = category.toLowerCase() + 's';
    setSections((prev) => ({
      ...prev,
      [key]: prev[key].map((item) =>
        item.id === id ? { ...item, locked: !item.locked } : item
      ),
    }));
  };

  const toggleLockAll = (lockState) => {
    setSections((prev) => ({
      poteaux: prev.poteaux.map((item) => ({ ...item, locked: lockState })),
      poutres: prev.poutres.map((item) => ({ ...item, locked: lockState })),
      semelles: prev.semelles.map((item) => ({ ...item, locked: lockState })),
    }));
  };

  const updateSection = (id, category, field, value) => {
    const key = category.toLowerCase() + 's';
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
      {/* Sidebar Core 2.0 */}
      <Sidebar
        activeView={activeView}
        setActiveView={setActiveView}
        isCollapsed={isCollapsed}
        setIsCollapsed={setIsCollapsed}
        lockedCount={lockedCount}
        totalCount={allElements.length}
      />

      {/* Workspace Principal */}
      <div className="main-wrapper">
        <TopBar
          projectName={projectData.nomProjet}
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
              onNext={handleCalculate}
            />
          )}

          {activeView === 'step2' && (
            <Step2_Calculs
              sections={sections}
              projectData={projectData}
              onBack={() => setActiveView('step1')}
              onNext={handleGoToValidation}
            />
          )}

          {activeView === 'step3' && (
            <Step3_ValidationLock
              sections={sections}
              toggleLock={toggleLock}
              toggleLockAll={toggleLockAll}
              updateSection={updateSection}
              onBack={() => setActiveView('step2')}
              onNext={handleGenerateDQE}
            />
          )}

          {activeView === 'step4' && (
            <Step4_DQEExport
              dqeData={dqeData || {}}
              projectData={projectData}
              onBack={() => setActiveView('step3')}
              onReset={() => setActiveView('step1')}
            />
          )}
        </main>
      </div>
    </div>
  );
}
