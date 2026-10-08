import React from 'react';
import {
  LayoutDashboard, FolderKanban, FileUp, Calculator, Grid3x3, Lock, Layers, FileSpreadsheet,
  BarChart3, ChevronLeft, ChevronRight, Compass, Settings, Building2, LogOut, Users, Activity,
} from 'lucide-react';

// Navigation en trois groupes : le CABINET (toujours accessible), le
// PROJET OUVERT (étapes, grisées tant qu'aucun projet n'est ouvert) et la
// CONFIGURATION. Chaque entrée est un vrai <button> : navigation clavier
// (Tab / Entrée / Espace) et focus visible natifs.
export default function Sidebar({
  activeView,
  setActiveView,
  isCollapsed,
  setIsCollapsed,
  lockedCount,
  totalCount,
  entreprise,
  entrepriseLoading,
  onLogout,
  moi,
  projetOuvert,
}) {
  const cabinet = [
    { id: 'dashboard', label: 'Tableau de bord', icon: LayoutDashboard },
    { id: 'projets', label: 'Mes projets', icon: FolderKanban },
  ];

  const projet = [
    { id: 'step1', label: 'Paramètres', icon: FileUp, toujours: true },
    { id: 'step2', label: 'Calculs structurels', icon: Calculator },
    { id: 'stepDalles', label: 'Dalles', icon: Grid3x3 },
    { id: 'step3', label: 'Validation', icon: Lock, badge: totalCount > 0 ? `${lockedCount}/${totalCount}` : null },
    { id: 'step3bis', label: 'Plan de fondation', icon: Layers },
    { id: 'step4', label: 'DQE & exports', icon: FileSpreadsheet },
    { id: 'analyse', label: 'Analyse du projet', icon: BarChart3 },
  ];

  const configuration = [
    { id: 'settingsEntreprise', label: 'Paramètres cabinet', icon: Settings },
    ...(moi?.role === 'admin' ? [{ id: 'equipe', label: 'Équipe', icon: Users }] : []),
    ...(moi?.is_staff ? [{ id: 'staff', label: 'Pilotage produit', icon: Activity }] : []),
  ];

  const initiales = entreprise?.nom
    ? entreprise.nom.split(/\s+/).filter(Boolean).slice(0, 2).map((w) => w[0].toUpperCase()).join('')
    : null;

  const groupe = (titre, items) => (
    <nav aria-label={titre}>
      {!isCollapsed && <div className="nav-section-title">{titre}</div>}
      <ul className="nav-menu">
        {items.map((item) => {
          const Icon = item.icon;
          const actif = activeView === item.id;
          const desactive = items === projet && !projetOuvert && !item.toujours;
          return (
            <li key={item.id}>
              <button
                type="button"
                className={`nav-item ${actif ? 'active' : ''} ${desactive ? 'nav-item-inactif' : ''}`}
                onClick={() => setActiveView(item.id)}
                aria-current={actif ? 'page' : undefined}
                title={desactive ? `${item.label} — ouvrez d'abord un projet` : item.label}
              >
                <Icon size={19} style={{ flexShrink: 0 }} aria-hidden="true" />
                {!isCollapsed && (
                  <>
                    <span>{item.label}</span>
                    {item.badge && <span className="nav-badge">{item.badge}</span>}
                  </>
                )}
              </button>
            </li>
          );
        })}
      </ul>
    </nav>
  );

  return (
    <aside className={`sidebar ${isCollapsed ? 'collapsed' : ''}`}>
      <div>
        <div className="sidebar-header">
          <div className="brand-wrapper">
            <div className="brand-icon-box"><Compass size={22} aria-hidden="true" /></div>
            {!isCollapsed && (
              <div className="brand-text">
                <h1>BTP Innovation Ivoire</h1>
                <p>Suite de calcul DQE / BTP</p>
              </div>
            )}
          </div>
          <button
            type="button"
            className="collapse-btn"
            onClick={() => setIsCollapsed(!isCollapsed)}
            aria-label={isCollapsed ? 'Déplier le menu' : 'Replier le menu'}
            aria-expanded={!isCollapsed}
          >
            {isCollapsed ? <ChevronRight size={18} /> : <ChevronLeft size={18} />}
          </button>
        </div>

        {groupe('Cabinet', cabinet)}
        {groupe(projetOuvert ? 'Projet ouvert' : 'Projet (aucun ouvert)', projet)}
        {groupe('Configuration', configuration)}
      </div>

      <div className="sidebar-footer">
        <button type="button" className="account-card" onClick={() => setActiveView('settingsEntreprise')}>
          <div className="account-avatar">
            {entreprise?.logo ? <img src={entreprise.logo} alt="" /> : initiales || <Building2 size={16} />}
          </div>
          {!isCollapsed && (
            <div className="account-details">
              <div className="name">
                {entrepriseLoading ? 'Chargement…' : entreprise?.nom || 'Cabinet non configuré'}
              </div>
              <div className="role">
                {entrepriseLoading ? '' : moi?.username ? `${moi.username}${moi.role ? ` · ${moi.role}` : ''}` : ''}
              </div>
            </div>
          )}
        </button>

        <button type="button" className="nav-item nav-item-deconnexion" onClick={onLogout}>
          <LogOut size={19} style={{ flexShrink: 0 }} aria-hidden="true" />
          {!isCollapsed && <span>Déconnexion</span>}
        </button>
      </div>
    </aside>
  );
}