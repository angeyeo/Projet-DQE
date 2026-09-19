import React from 'react';
import { LayoutDashboard, FileUp, Calculator, Lock, FileSpreadsheet, ChevronLeft, ChevronRight, Compass, Settings, Building2 } from 'lucide-react';

export default function Sidebar({
  activeView,
  setActiveView,
  isCollapsed,
  setIsCollapsed,
  lockedCount,
  totalCount,
  entreprise,
  entrepriseLoading,
}) {
  const menuItems = [
    { id: 'dashboard', label: 'Tableau de Bord', icon: LayoutDashboard },
    { id: 'step1', label: 'Plans & Saisie', icon: FileUp },
    { id: 'step2', label: 'Calculs Structurels', icon: Calculator },
    { id: 'step3', label: 'Validation & Verrou', icon: Lock, badge: lockedCount > 0 ? `${lockedCount}/${totalCount}` : null },
    { id: 'step4', label: 'Devis DQE & IA', icon: FileSpreadsheet },
  ];

  const menuItemsBas = [
    { id: 'settingsEntreprise', label: 'Paramètres Entreprise', icon: Settings },
  ];

  // Initiales tirées du vrai nom d'entreprise (dqeService.getEntreprise) --
  // jamais une donnée inventée. Tant que rien n'est configuré, on l'indique
  // honnêtement plutôt que d'afficher un faux nom.
  const initiales = entreprise?.nom
    ? entreprise.nom
        .split(/\s+/)
        .filter(Boolean)
        .slice(0, 2)
        .map((w) => w[0].toUpperCase())
        .join('')
    : null;

  return (
    <aside className={`sidebar ${isCollapsed ? 'collapsed' : ''}`}>
      <div>
        {/* Brand Header */}
        <div className="sidebar-header">
          <div className="brand-wrapper">
            <div className="brand-icon-box">
              <Compass size={22} />
            </div>
            {!isCollapsed && (
              <div className="brand-text">
                <h1>BTP Innovation Ivoire</h1>
                <p>Suite de calcul DQE / BTP</p>
              </div>
            )}
          </div>

          <button className="collapse-btn" onClick={() => setIsCollapsed(!isCollapsed)}>
            {isCollapsed ? <ChevronRight size={18} /> : <ChevronLeft size={18} />}
          </button>
        </div>

        {/* Navigation Section */}
        {!isCollapsed && <div className="nav-section-title">Navigation principale</div>}
        <ul className="nav-menu">
          {menuItems.map((item) => {
            const Icon = item.icon;
            const isActive = activeView === item.id;
            return (
              <li
                key={item.id}
                className={`nav-item ${isActive ? 'active' : ''}`}
                onClick={() => setActiveView(item.id)}
              >
                <Icon size={19} style={{ flexShrink: 0 }} />
                {!isCollapsed && (
                  <>
                    <span>{item.label}</span>
                    {item.badge && <span className="nav-badge">{item.badge}</span>}
                  </>
                )}
              </li>
            );
          })}
        </ul>

        {!isCollapsed && <div className="nav-section-title">Configuration</div>}
        <ul className="nav-menu">
          {menuItemsBas.map((item) => {
            const Icon = item.icon;
            const isActive = activeView === item.id;
            return (
              <li
                key={item.id}
                className={`nav-item ${isActive ? 'active' : ''}`}
                onClick={() => setActiveView(item.id)}
              >
                <Icon size={19} style={{ flexShrink: 0 }} />
                {!isCollapsed && <span>{item.label}</span>}
              </li>
            );
          })}
        </ul>
      </div>

      {/* Carte entreprise -- reflète la vraie config (Paramètres Entreprise),
          jamais un nom de personne. Trois états honnêtes : chargement,
          entreprise configurée, entreprise non configurée. */}
      <div className="sidebar-footer">
        <div className="account-card" onClick={() => setActiveView('settingsEntreprise')}>
          <div className="account-avatar">
            {entreprise?.logo ? (
              <img src={entreprise.logo} alt="" />
            ) : initiales ? (
              initiales
            ) : (
              <Building2 size={16} />
            )}
          </div>
          {!isCollapsed && (
            <div className="account-details">
              <div className="name">
                {entrepriseLoading ? 'Chargement…' : entreprise?.nom || 'Entreprise non configurée'}
              </div>
              <div className="role">
                {entrepriseLoading ? '' : entreprise?.nom ? 'Compte entreprise' : 'Configurer maintenant'}
              </div>
            </div>
          )}
        </div>
      </div>
    </aside>
  );
}