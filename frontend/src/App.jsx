import React, { useCallback, useEffect, useState } from 'react';
import LandingPage from './components/LandingPage';
import LoginPage from './components/LoginPage';
import RegisterPage from './components/RegisterPage';
import ForgotPasswordPage from './components/ForgotPasswordPage';
import ActivateAccountPage from './components/ActivateAccountPage';
import ResetPasswordConfirmPage from './components/ResetPasswordConfirmPage';
import Sidebar from './components/Sidebar';
import TopBar from './components/TopBar';
import Step1_Parametres from './components/Step1_Parametres';
import StepDalles from './components/StepDalles';
import Step2_Calculs from './components/Step2_Calculs';
import Step3_ValidationLock from './components/Step3_ValidationLock';
import StepPlanFondation from './components/StepPlanFondation';
import Step4_DQEExport from './components/Step4_DQEExport';
import SettingsEntreprise from './components/settingsentreprise';
import TeamManagementView from './components/TeamManagementView';
import MesProjetsView from './components/MesProjetsView';
import CabinetDashboard from './components/dashboards/CabinetDashboard';
import ProjetDashboard from './components/dashboards/ProjetDashboard';
import StaffDashboard from './components/dashboards/StaffDashboard';
import Alerte from './components/ui/Alerte';
import AucunProjet from './components/ui/AucunProjet';
import { dqeService, projetVersFormulaire } from './api/dqeService';
import useProjetCourant from './hooks/useProjetCourant';

// Liens à usage unique envoyés par le backend (activation, réinitialisation).
const DEEP_LINK_PATHS = {
  '/activer-compte': 'activer-compte',
  '/reinitialiser-mot-de-passe': 'reinitialiser-mot-de-passe',
};
const VUES_PUBLIQUES = ['landing', 'login', 'register', 'forgot-password', 'activer-compte', 'reinitialiser-mot-de-passe'];
// Vues qui n'ont de sens qu'avec un projet ouvert.
const VUES_PROJET = ['step2', 'stepDalles', 'step3', 'step3bis', 'step4', 'analyse'];

const FORMULAIRE_VIDE = {
  id: null,
  nomProjet: '',
  numeroDevis: '',
  typeUsage: '',
  nombreNiveaux: '',
  nbTraveesX: '',
  nbTraveesY: '',
  porteeX: '',
  porteeY: '',
  hauteurEtage: '',
  chargeExploitation: '',
  contrainteSol: '',
  chargePermanente: '',
  couchesPermanentes: [],
  methodeSemelles: 'ELU',
  // Défaut validé par le technicien BTP : le forfait G ne couvre pas poutres et poteaux.
  inclurePoidsPropre: true,
  ifcImporte: false,
};

const lireVue = () => {
  try { return localStorage.getItem('dqe_active_view'); } catch { return null; }
};

const estMobile = () => typeof window !== 'undefined' && window.innerWidth <= 768;

export default function App() {
  const [activeView, setActiveView] = useState(() => {
    const vueLien = DEEP_LINK_PATHS[window.location.pathname];
    if (vueLien) return vueLien;
    if (!dqeService.isAuthenticated()) return 'landing';
    return lireVue() || 'dashboard';
  });
  const [deepLinkParams] = useState(() => {
    const params = new URLSearchParams(window.location.search);
    return { uid: params.get('uid'), token: params.get('token') };
  });
  const [isCollapsed, setIsCollapsed] = useState(estMobile);

  const authentifie = !VUES_PUBLIQUES.includes(activeView);
  const courant = useProjetCourant(authentifie);

  useEffect(() => {
    if (activeView === 'activer-compte' || activeView === 'reinitialiser-mot-de-passe') return;
    try { localStorage.setItem('dqe_active_view', activeView); } catch { /* non persisté */ }
  }, [activeView]);

  useEffect(() => {
    const onAuthExpired = () => setActiveView('login');
    window.addEventListener('dqe:auth-expired', onAuthExpired);
    return () => window.removeEventListener('dqe:auth-expired', onAuthExpired);
  }, []);

  // Navigation : sur mobile, la sidebar se replie après un choix.
  const naviguer = useCallback((vue) => {
    setActiveView(vue);
    if (estMobile()) setIsCollapsed(true);
  }, []);

  // --- Compte connecté ----------------------------------------------------
  const [moi, setMoi] = useState(null);
  const [entreprise, setEntreprise] = useState(null);
  const [entrepriseLoading, setEntrepriseLoading] = useState(true);
  const [erreurCompte, setErreurCompte] = useState(null);

  useEffect(() => {
    if (!authentifie) return undefined;
    let annule = false;
    setEntrepriseLoading(true);
    Promise.allSettled([dqeService.getMe(), dqeService.getEntreprise()]).then(([me, ent]) => {
      if (annule) return;
      setMoi(me.status === 'fulfilled' ? me.value : null);
      setEntreprise(ent.status === 'fulfilled' ? ent.value : null);
      setErreurCompte(
        ent.status === 'rejected' && ent.reason?.status === 403
          ? "Votre compte n'est rattaché à aucun cabinet : les projets ne sont pas accessibles. Contactez l'administrateur de votre cabinet."
          : null,
      );
      setEntrepriseLoading(false);
    });
    return () => { annule = true; };
  }, [authentifie]);

  const handleLogout = async () => {
    await dqeService.logout();
    courant.fermer();
    setMoi(null);
    setActiveView('landing');
  };

  // --- Formulaire du projet (miroir éditable des données serveur) ----------
  const [formulaire, setFormulaire] = useState(FORMULAIRE_VIDE);
  useEffect(() => {
    if (courant.projet) setFormulaire(projetVersFormulaire(courant.projet));
  }, [courant.projet]);
  const updateProjectData = (champs) => setFormulaire((prev) => ({ ...prev, ...champs }));

  const ouvrirProjet = (id, vue = 'step3') => {
    courant.ouvrir(id);
    naviguer(vue);
  };

  const nouveauProjet = () => {
    courant.fermer();
    setFormulaire(FORMULAIRE_VIDE);
    setCalcul({ erreur: null, champs: [], hypotheses: [], avertissements: [] });
    naviguer('step1');
  };

  // --- Étape 1 -> 2 : enregistrement + génération des éléments -------------
  const [calcul, setCalcul] = useState({ enCours: false, erreur: null, champs: [], hypotheses: [], avertissements: [] });

  const handleCalculate = async () => {
    setCalcul({ enCours: true, erreur: null, champs: [], hypotheses: [], avertissements: [] });
    try {
      const res = await dqeService.enregistrerEtGenerer(formulaire);
      await courant.ouvrir(res.projetId);
      setCalcul({ enCours: false, erreur: null, champs: [], hypotheses: res.hypotheses, avertissements: res.avertissements });
      naviguer('step2');
    } catch (err) {
      if (err.projetId && err.projetId !== courant.projetId) await courant.ouvrir(err.projetId);
      setCalcul({
        enCours: false,
        erreur: err.message,
        champs: err.data?.champs_manquants || [],
        hypotheses: [],
        avertissements: [],
      });
    }
  };

  // Crée le projet côté serveur si besoin (import IFC / Vision avant calcul).
  const assurerProjet = async () => {
    if (formulaire.id) return formulaire.id;
    // Le serveur exige un nom : on le demande avant de créer le projet
    // (jamais de nom inventé à la place de l'utilisateur).
    if (!formulaire.nomProjet?.trim()) {
      document.getElementById('champ-s1-1')?.focus();
      throw new Error('saisissez d’abord le nom du projet (champ « Nom du projet » plus bas), puis déposez à nouveau le fichier.');
    }
    const projet = await dqeService.createProjet(formulaire);
    await courant.ouvrir(projet.id);
    return projet.id;
  };

  // --- Verrouillage (toujours côté serveur, puis relecture du projet) ------
  const [validation, setValidation] = useState({ erreur: null, enCoursId: null });

  const basculerVerrou = async (item, resultatManuel) => {
    setValidation({ erreur: null, enCoursId: item.elementId });
    try {
      if (item.locked) await dqeService.deverrouillerElement(item.elementId);
      else await dqeService.validerElement(item.elementId, resultatManuel);
      await courant.recharger();
      setValidation({ erreur: null, enCoursId: null });
      return true;
    } catch (err) {
      setValidation({ erreur: `${item.name} : ${err.message}`, enCoursId: null });
      return false;
    }
  };

  const basculerTout = async (verrouiller, manuels) => {
    const tous = Object.values(courant.sections).flat();
    const cibles = tous.filter((el) => el.locked !== verrouiller);
    setValidation({ erreur: null, enCoursId: 'tous' });
    const echecs = [];
    for (const el of cibles) {
      try {
        if (verrouiller) {
          if (el.calculIndisponible && !manuels[el.elementId]) {
            echecs.push(`${el.name} : saisie manuelle requise (aucun résultat de calcul).`);
            continue;
          }
          await dqeService.validerElement(el.elementId, manuels[el.elementId]);
        } else {
          await dqeService.deverrouillerElement(el.elementId);
        }
      } catch (err) {
        echecs.push(`${el.name} : ${err.message}`);
      }
    }
    await courant.recharger();
    setValidation({ erreur: echecs.length ? echecs.join(' · ') : null, enCoursId: null });
    return echecs.length === 0;
  };

  // --- Postes complémentaires ----------------------------------------------
  const [erreurPoste, setErreurPoste] = useState(null);
  const ajouterPoste = async (poste) => {
    setErreurPoste(null);
    try {
      await dqeService.ajouterPosteComplementaire(courant.projetId, poste);
      await courant.recharger();
      return true;
    } catch (err) {
      setErreurPoste(`Impossible d'ajouter le poste : ${err.message}`);
      return false;
    }
  };
  const supprimerPoste = async (posteId) => {
    setErreurPoste(null);
    try {
      await dqeService.supprimerPosteComplementaire(posteId);
      await courant.recharger();
    } catch (err) {
      setErreurPoste(`Impossible de supprimer le poste : ${err.message}`);
    }
  };

  const tousElements = Object.values(courant.sections).flat();
  const lockedCount = tousElements.filter((e) => e.locked).length;

  // --- Vues publiques -------------------------------------------------------
  if (activeView === 'landing') {
    return (
      <LandingPage
        onGetStarted={() => setActiveView(dqeService.isAuthenticated() ? 'dashboard' : 'register')}
        onLogin={() => setActiveView('login')}
      />
    );
  }
  if (activeView === 'login') {
    return (
      <LoginPage
        onEnterApp={() => setActiveView(lireVue() && !VUES_PUBLIQUES.includes(lireVue()) ? lireVue() : 'dashboard')}
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
    return <ForgotPasswordPage onBackToLanding={() => setActiveView('landing')} onGoToLogin={() => setActiveView('login')} />;
  }
  if (activeView === 'activer-compte') {
    return <ActivateAccountPage uid={deepLinkParams.uid} token={deepLinkParams.token} onGoToLogin={() => setActiveView('login')} />;
  }
  if (activeView === 'reinitialiser-mot-de-passe') {
    return <ResetPasswordConfirmPage uid={deepLinkParams.uid} token={deepLinkParams.token} onGoToLogin={() => setActiveView('login')} />;
  }

  // --- Application ----------------------------------------------------------
  const vueProjetSansProjet = VUES_PROJET.includes(activeView) && !courant.projetId;

  const contenu = () => {
    if (vueProjetSansProjet) {
      return <AucunProjet onOuvrir={() => naviguer('projets')} onNouveau={nouveauProjet} />;
    }
    if (VUES_PROJET.includes(activeView) && courant.chargement && !courant.projet) {
      return <div className="glass-panel etat-chargement" role="status">Chargement du projet…</div>;
    }
    switch (activeView) {
      case 'dashboard':
        return <CabinetDashboard onOuvrirProjet={ouvrirProjet} onNouveau={nouveauProjet} onNaviguer={naviguer} />;
      case 'projets':
        return (
          <MesProjetsView
            projetCourantId={courant.projetId}
            onOuvrir={ouvrirProjet}
            onNouveau={nouveauProjet}
            onProjetSupprime={(id) => { if (id === courant.projetId) courant.fermer(); }}
          />
        );
      case 'analyse':
        return <ProjetDashboard projetId={courant.projetId} onNaviguer={naviguer} />;
      case 'staff':
        return moi?.is_staff ? <StaffDashboard /> : <Alerte type="erreur">Accès réservé à l'équipe interne.</Alerte>;
      case 'step1':
        return (
          <Step1_Parametres
            projectData={formulaire}
            updateProjectData={updateProjectData}
            assurerProjet={assurerProjet}
            onNext={handleCalculate}
            calcul={calcul}
            alertes={(courant.projet?.alertes_plausibilite || []).filter((a) => !a.element)}
          />
        );
      case 'step2':
        return (
          <Step2_Calculs
            sections={courant.sections}
            projet={courant.projet}
            hypotheses={calcul.hypotheses.length ? calcul.hypotheses : courant.projet?.hypotheses_calcul?.hypotheses || []}
            alertes={courant.projet?.alertes_plausibilite || []}
            avertissements={calcul.avertissements}
            onBack={() => naviguer('step1')}
            onNext={() => naviguer('stepDalles')}
          />
        );
      case 'stepDalles':
        return (
          <StepDalles
            projetId={courant.projetId}
            dalles={courant.sections.dalles}
            onChange={courant.recharger}
            onBack={() => naviguer('step2')}
            onNext={() => naviguer('step3')}
          />
        );
      case 'step3':
        return (
          <Step3_ValidationLock
            sections={courant.sections}
            projetId={courant.projetId}
            postes={courant.postes}
            onBasculerVerrou={basculerVerrou}
            onBasculerTout={basculerTout}
            validation={validation}
            onAjouterPoste={ajouterPoste}
            onSupprimerPoste={supprimerPoste}
            erreurPoste={erreurPoste}
            onBack={() => naviguer('stepDalles')}
            onNext={() => naviguer('step3bis')}
          />
        );
      case 'step3bis':
        return (
          <StepPlanFondation
            projetId={courant.projetId}
            peutValider={moi?.role === 'admin' || moi?.role === 'ingenieur'}
            onBack={() => naviguer('step3')}
            onNext={() => naviguer('step4')}
          />
        );
      case 'step4':
        return (
          <Step4_DQEExport
            projetId={courant.projetId}
            nomProjet={courant.projet?.nom}
            onBack={() => naviguer('step3bis')}
            onCorriger={() => naviguer('step3')}
            onAnalyse={() => naviguer('analyse')}
          />
        );
      case 'settingsEntreprise':
        return <SettingsEntreprise estAdmin={moi?.role === 'admin'} />;
      case 'equipe':
        return <TeamManagementView moiProfil={moi ? { role: moi.role } : null} />;
      default:
        return <CabinetDashboard onOuvrirProjet={ouvrirProjet} onNouveau={nouveauProjet} onNaviguer={naviguer} />;
    }
  };

  return (
    <div className="app-layout">
      <Sidebar
        activeView={activeView}
        setActiveView={naviguer}
        isCollapsed={isCollapsed}
        setIsCollapsed={setIsCollapsed}
        lockedCount={lockedCount}
        totalCount={tousElements.length}
        entreprise={entreprise}
        entrepriseLoading={entrepriseLoading}
        onLogout={handleLogout}
        moi={moi}
        projetOuvert={!!courant.projetId}
      />

      <div className="main-wrapper">
        <TopBar
          projectName={courant.projet?.nom || (courant.projetId ? 'Chargement…' : 'Aucun projet ouvert')}
          onNewCalculation={nouveauProjet}
          onMesProjets={() => naviguer('projets')}
          lockedCount={lockedCount}
          totalCount={tousElements.length}
        />

        <main className="content-body" id="contenu-principal">
          {erreurCompte && <Alerte type="erreur">{erreurCompte}</Alerte>}
          {courant.erreur && (
            <Alerte type="erreur" action={{ libelle: 'Mes projets', onClick: () => naviguer('projets') }}>
              {courant.erreur}
            </Alerte>
          )}
          {contenu()}
        </main>
      </div>
    </div>
  );
}