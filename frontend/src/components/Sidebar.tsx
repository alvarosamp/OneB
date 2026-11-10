import {
  Activity,
  BarChart3,
  Bell,
  BookOpen,
  Bot,
  Brain,
  BriefcaseBusiness,
  ClipboardList,
  Gauge,
  LayoutDashboard,
  LineChart,
  Newspaper,
  Radar,
  ShieldCheck,
  Sparkles,
  TrendingUp,
  Users,
} from 'lucide-react';
import { NavLink } from 'react-router-dom';
import { useAuth } from '../context/AuthContext';

const GROUPS = [
  {
    label: 'Visao geral',
    items: [
      { to: '/ferramenta', label: 'Dashboard', icon: LayoutDashboard },
      { to: '/resumo-diario', label: 'Resumo Diario', icon: Newspaper },
      { to: '/analise-matinal', label: 'Analise Matinal', icon: Activity },
    ],
  },
  {
    label: 'Mercado',
    items: [
      { to: '/mercado', label: 'Mercado', icon: LineChart },
      { to: '/regime', label: 'Regime', icon: Gauge },
      { to: '/inteligencia', label: 'Inteligencia', icon: Brain },
      { to: '/mesa-tecnica', label: 'Mesa Tecnica', icon: BarChart3 },
    ],
  },
  {
    label: 'IA',
    items: [
      { to: '/mesa-ia', label: 'Mesa IA', icon: Sparkles },
      { to: '/copiloto', label: 'Copiloto', icon: Bot },
      { to: '/assistente', label: 'Assistente IA', icon: Radar },
    ],
  },
  {
    label: 'Operacao',
    items: [
      { to: '/watchlist', label: 'Watchlist & Regras', icon: ClipboardList },
      { to: '/alertas', label: 'Alertas', icon: Bell },
      { to: '/posicoes', label: 'Posicoes', icon: BriefcaseBusiness },
    ],
  },
  {
    label: 'Sistema',
    items: [
      { to: '/operacoes', label: 'Operacoes', icon: ShieldCheck },
      { to: '/como-usar', label: 'Como usar', icon: BookOpen },
    ],
  },
];

export function Sidebar() {
  const { user } = useAuth();

  return (
    <aside className="sidebar terminal-sidebar">
      <div className="terminal-sidebar-brand">
        <span className="brand-mark" aria-hidden="true">
          <i />
          <i />
          <i />
        </span>
        <div>
          <strong>OneB</strong>
          <small>Terminal</small>
        </div>
      </div>

      <nav className="sidebar-nav terminal-sidebar-nav">
        {GROUPS.map((group) => (
          <div className="sidebar-group" key={group.label}>
            <p className="sidebar-group-label">{group.label}</p>
            {group.items.map((item) => {
              const Icon = item.icon;
              return (
                <NavLink key={item.to} to={item.to} className="sidebar-link terminal-sidebar-link">
                  <Icon size={17} />
                  <span>{item.label}</span>
                </NavLink>
              );
            })}
          </div>
        ))}

        {user?.is_admin && (
          <div className="sidebar-group">
            <p className="sidebar-group-label">Admin</p>
            <NavLink to="/usuarios" className="sidebar-link terminal-sidebar-link">
              <Users size={17} />
              <span>Usuarios</span>
            </NavLink>
          </div>
        )}
      </nav>

      <div className="terminal-sidebar-footer">
        <TrendingUp size={16} />
        <span>Estudo, dados, risco e metodo em um fluxo.</span>
      </div>
    </aside>
  );
}
