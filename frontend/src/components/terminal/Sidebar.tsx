import { NavLink, useLocation } from 'react-router-dom';
import { PanelLeftClose, PanelLeftOpen } from 'lucide-react';
import { PRIMARY_NAV, SECONDARY_NAV, isNavItemActive, type NavItem } from '../../content/navigation';
import { ICON } from '../ui';
import styles from './Sidebar.module.css';

interface SidebarProps {
  collapsed?: boolean;
  onToggleCollapsed?: () => void;
  onNavigate?: () => void;
  /** Sem botão de recolher e sem marca (uso dentro do drawer mobile). */
  inDrawer?: boolean;
}

export function BrandMark() {
  return (
    <span className={styles.mark} aria-hidden="true">
      <i />
      <i />
      <i />
    </span>
  );
}

export function Sidebar({ collapsed = false, onToggleCollapsed, onNavigate, inDrawer }: SidebarProps) {
  const { pathname } = useLocation();

  function renderItem(item: NavItem) {
    const Icon = item.icon;
    const active = isNavItemActive(item, pathname);
    return (
      <NavLink
        key={item.to}
        to={item.to}
        className={[styles.link, active ? styles.active : ''].join(' ')}
        aria-current={active ? 'page' : undefined}
        title={collapsed ? item.label : undefined}
        onClick={onNavigate}
      >
        <Icon {...ICON} aria-hidden="true" />
        <span className={styles.label}>{item.label}</span>
      </NavLink>
    );
  }

  return (
    <div className={[styles.sidebar, collapsed ? styles.collapsed : ''].join(' ')}>
      {!inDrawer && (
        <NavLink to="/ferramenta" className={styles.brand} aria-label="OneB, ir para Hoje">
          <BrandMark />
          <span className={styles.brandName}>OneB</span>
        </NavLink>
      )}
      <nav className={styles.nav} aria-label="Navegação principal">
        {PRIMARY_NAV.map((group, i) => (
          <div className={styles.group} key={group.label ?? `g${i}`}>
            {group.label && <span className={styles.groupLabel}>{group.label}</span>}
            {group.items.map(renderItem)}
          </div>
        ))}
      </nav>
      <div className={styles.footer}>
        {SECONDARY_NAV.map(renderItem)}
        {onToggleCollapsed && !inDrawer && (
          <button
            type="button"
            className={styles.collapseButton}
            onClick={onToggleCollapsed}
            aria-label={collapsed ? 'Expandir menu' : 'Recolher menu'}
            aria-expanded={!collapsed}
            title={collapsed ? 'Expandir menu' : undefined}
          >
            {collapsed ? <PanelLeftOpen {...ICON} aria-hidden="true" /> : <PanelLeftClose {...ICON} aria-hidden="true" />}
            <span className={styles.label}>Recolher menu</span>
          </button>
        )}
      </div>
    </div>
  );
}
