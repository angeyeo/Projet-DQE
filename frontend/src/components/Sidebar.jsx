import React from 'react';
import { LayoutDashboard, FileUp, Calculator, Lock, FileSpreadsheet, ChevronLeft, ChevronRight, Building2, ShieldCheck } from 'lucide-react';

export default function Sidebar({ activeView, setActiveView, isCollapsed, setIsCollapsed, lockedCount, totalCount }) {
  const menuItems = [
    { id: 'dashboard', label: 'Tableau de Bord', icon: LayoutDashboard },
    { id: 'step1', label: '1. Plans & Saisie', icon: FileUp, badge: 'Étape 1' },
    { id: 'step2', label: '2. Calculs Structurels', icon: Calculator, badge: 'Étape 2' },
    { id: 'step3', label: '3. Validation & Verrou', icon: Lock, badge: lockedCount > 0 ? `${lockedCount}/${totalCount}` : 'Étape 3' },
    { id: 'step4', label: '4. Devis DQE & IA', icon: FileSpreadsheet, badge: 'Étape 4' },
  ];

  return (
    <aside className={`sidebar ${isCollapsed ? 'collapsed' : ''}`}>
      <div>
        {/* Brand Header */}
        <div className="sidebar-header">
          <div className="brand-wrapper">
            <div className="brand-icon-box">
              <Building2 size={26} />
            </div>
            {!isCollapsed && (
              <div className="brand-text">
                <h1>Projet DQE</h1>
                <p>Core 2.0 BTP Suite</p>
              </div>
            )}
          </div>

          <button className="collapse-btn" onClick={() => setIsCollapsed(!isCollapsed)}>
            {isCollapsed ? <ChevronRight size={20} /> : <ChevronLeft size={20} />}
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
                <Icon size={25} style={{ flexShrink: 0 }} />
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
      </div>

      {/* User Footer Profile */}
      <div className="sidebar-footer">
        <div className="user-profile-card">
          <div className="user-avatar">YA</div>
          {!isCollapsed && (
            <div className="user-details">
              <div className="name">Yves Arthur Ané</div>
              <div className="role">Dev Frontend / BTP</div>
            </div>
          )}
        </div>
      </div>
    </aside>
  );
}
