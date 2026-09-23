import React, { useState, useEffect } from 'react';
import LandingPage from './components/LandingPage';
import LoginPage from './components/LoginPage';
import RegisterPage from './components/RegisterPage';
import ForgotPasswordPage from './components/ForgotPasswordPage';
import ActivateAccountPage from './components/ActivateAccountPage';
import ResetPasswordConfirmPage from './components/ResetPasswordConfirmPage';
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
import TeamManagementView from './components/TeamManagementView';
import { dqeService } from './api/dqeService';

// Liens à usage unique envoyés par le backend (voir auth_views.py) :
// /activer-compte?uid=...&token=... et
// /reinitialiser-mot-de-passe?uid=...&token=... -- pas de routeur dans
// cette app, donc on les détecte une fois au chargement.
const DEEP_LINK_PATHS = {
  '/activer-compte': 'activer-compte',
  '/reinitialiser-mot-de-passe': 'reinitialiser-mot-de-passe',
};

export default function App() {
  // Persistence de la vue active au rafraîchissement (F5). Une vraie
  // authentification existe maintenant (JWT) : un visiteur non connecté
  // ne doit jamais retomber directement sur le tableau de bord, même si
  // c'était la dernière vue enregistrée avant expiration de sa session.
  const [activeView, setActiveView] = useState(() => {
    const vueLien = DEEP_LINK_PATHS[window.location.pathname];
    if (vueLien) return vueLien;
    if (!dqeService.isAuthenticated()) return 'landing';
    return localStorage.getItem('dqe_active_view') || 'dashboard';
  });

  // uid/token du lien d'activation ou de réinitialisation, lus une seule
  // fois (ces vues sont éphémères, jamais rechargées depuis le stockage).
  const [deepLinkParams] = useState(() => {
    const params = new URLSearchParams(window.location.search);
    return { uid: params.get('uid'), token: params.get('token') };
  });

  useEffect(() => {
    // Ne pas persister les vues éphémères liées à un lien à usage unique :
    // recharger la page plus tard ne doit pas y retomber.
    if (activeView === 'activer-compte' || activeView === 'reinitialiser-mot-de-passe') return;
    localStorage.setItem('dqe_active_view', activeView);
  }, [activeView]);

  // Session expirée / refresh token révoqué (déclenché par dqeService's
  // apiFetch) -- renvoie proprement à la landing plutôt que de laisser
  // l'utilisateur face à des appels API qui échouent en boucle.
  useEffect(() => {
    const onAuthExpired = () => setActiveView('landing');
    window.addEventListener('dqe:auth-expired', onAuthExpired);
    return () => window.removeEventListener('dqe:auth-expired', onAuthExpired);
  }, []);

  const handleLogout = async () => {
    await dqeService.logout();
    setActiveView('landing');
  };

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

  // Entreprise réelle (dqeService.getEntreprise) -- affichée dans la Sidebar
  // à la place d'un nom de personne codé en dur. Pas de donnée inventée :
  // si l'entreprise n'est pas encore configurée, entreprise reste null et
  // la Sidebar l'indique honnêtement.
  const [entreprise, setEntreprise] = useState(null);
  const [entrepriseLoading, setEntrepriseLoading] = useState(true);

  useEffect(() => {
    let annule = false;
    dqeService.getEntreprise()
      .then((data) => { if (!annule) setEntreprise(data || null); })
      .catch(() => { if (!annule) setEntreprise(null); })
      .finally(() => { if (!annule) setEntrepriseLoading(false); });
    return () => { annule = true; };
  }, []);

  // Profil de l'utilisateur connecté (rôle, entreprise) -- nécessaire pour
  // savoir s'il faut afficher "Équipe" dans la Sidebar (réservé Admin).
  // Pas de donnée inventée : reste null tant que l'appel n'a pas répondu
  // ou si l'utilisateur n'est pas authentifié.
  const [moiProfil, setMoiProfil] = useState(null);

  useEffect(() => {
    let annule = false;
    if (!dqeService.isAuthenticated()) return undefined;
    dqeService.getMoi()
      .then((data) => { if (!annule) setMoiProfil(data || null); })
      .catch(() => { if (!annule) setMoiProfil(null); });
    return () => { annule = true; };
  }, [activeView === 'landing' || activeView === 'login']);


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
    if (!item) return false;

    setValidationError(null);
    let resultatManuel = null;

    if (!item.locked) {
      if (item.calculIndisponible) {
        const manuel = buildResultatManuel(item, category);
        if (manuel.error) {
          setValidationError(`${item.name} : ${manuel.error}`);
          return false;
        }
        resultatManuel = manuel.value;
      }

      setValidatingId(id);
      try {
        await dqeService.validerElementDRF(item.elementId, resultatManuel || undefined);
      } catch (err) {
        setValidationError(`Impossible de valider ${item.name} : ${err.message}`);
        setValidatingId(null);
        return false;
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
    return true;
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
            return false;
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
        return false;
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
      return true;
    }

    setSections((prev) => ({
      ...prev,
      poteaux: prev.poteaux.map((item) => ({ ...item, locked: lockState })),
      poutres: prev.poutres.map((item) => ({ ...item, locked: lockState })),
      semelles: prev.semelles.map((item) => ({ ...item, locked: lockState })),
    }));
    return true;
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

  if (activeView === 'landing') {
    return (
      <LandingPage
        // "Commencer un projet" suppose désormais un vrai compte (les
        // projets sont rattachés à une entreprise) -- vers l'inscription
        // si non connecté, direct au tableau de bord sinon.
        onGetStarted={() => setActiveView(dqeService.isAuthenticated() ? 'dashboard' : 'register')}
        onLogin={() => setActiveView('login')}
      />
    );
  }

  if (activeView === 'login') {
    return (
      <LoginPage
        onEnterApp={() => setActiveView('dashboard')}
        onBackToLanding={() => setActiveView('landing')}
        onGoToRegister={() => setActiveView('register')}
        onGoToForgotPassword={() => setActiveView('forgot-password')}
      />
    );
  }

  if (activeView === 'register') {
    return (
      <RegisterPage
        onEnterApp={() => setActiveView('dashboard')}
        onBackToLanding={() => setActiveView('landing')}
        onGoToLogin={() => setActiveView('login')}
      />
    );
  }

  if (activeView === 'forgot-password') {
    return (
      <ForgotPasswordPage
        onBackToLanding={() => setActiveView('landing')}
        onGoToLogin={() => setActiveView('login')}
      />
    );
  }

  if (activeView === 'activer-compte') {
    return (
      <ActivateAccountPage
        uid={deepLinkParams.uid}
        token={deepLinkParams.token}
        onGoToLogin={() => setActiveView('login')}
      />
    );
  }

  if (activeView === 'reinitialiser-mot-de-passe') {
    return (
      <ResetPasswordConfirmPage
        uid={deepLinkParams.uid}
        token={deepLinkParams.token}
        onGoToLogin={() => setActiveView('login')}
      />
    );
  }

  return (
    <div className="app-layout">
      <Sidebar
        activeView={activeView}
        setActiveView={setActiveView}
        isCollapsed={isCollapsed}
        setIsCollapsed={setIsCollapsed}
        lockedCount={lockedCount}
        totalCount={allElements.length}
        entreprise={entreprise}
        entrepriseLoading={entrepriseLoading}
        onLogout={handleLogout}
        moiProfil={moiProfil}
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
              projetId={sections?.projetId || projectData?.id}
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

          {activeView === 'equipe' && (
            <TeamManagementView moiProfil={moiProfil} />
          )}
        </main>
      </div>
    </div>
  );
}