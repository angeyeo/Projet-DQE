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

  const updateProjectData = (newFields) => {
    setProjectData((prev) => ({ ...prev, ...newFields }));
  };

  const handleCalculate = async () => {
    const totalG = couchesG.reduce((sum, c) => sum + (parseFloat(c.chargeG) || 0), 0);
    const updatedData = { ...projectData, chargePermanenteG: totalG > 0 ? totalG : 5.0 };
    const results = await dqeService.calculateSections(updatedData);
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
