import {
  BarChart3,
  Bell,
  BookOpen,
  BriefcaseBusiness,
  CircleHelp,
  Eye,
  LayoutDashboard,
  Newspaper,
  Radar,
  Settings,
  MessagesSquare,
  type LucideIcon,
} from 'lucide-react';

export interface NavItem {
  to: string;
  label: string;
  icon: LucideIcon;
  /** Palavras extras para a busca (command palette). */
  keywords?: string[];
  /** Caminhos antigos/relacionados que também marcam este item como ativo. */
  match?: string[];
}

export interface NavGroup {
  label?: string;
  items: NavItem[];
}

export const PRIMARY_NAV: NavGroup[] = [
  {
    items: [{ to: '/ferramenta', label: 'Hoje', icon: LayoutDashboard, keywords: ['dashboard', 'início', 'resumo'] }],
  },
  {
    label: 'Mercado',
    items: [
      { to: '/mercado', label: 'Mercado', icon: Newspaper, keywords: ['notícias', 'calendário', 'câmbio', 'juros', 'earnings'] },
      { to: '/analise', label: 'Análise', icon: BarChart3, keywords: ['regime', 'técnica', 'macro', 'resumo diário', 'análise matinal'] },
      { to: '/radar', label: 'Radar', icon: Radar, keywords: ['atenção', 'ranking', 'score'] },
    ],
  },
  {
    label: 'Operação',
    items: [
      { to: '/watchlist', label: 'Watchlist', icon: Eye, keywords: ['regras', 'monitorar'] },
      { to: '/alertas', label: 'Alertas', icon: Bell, keywords: ['sinais', 'disparos'] },
      { to: '/carteira', label: 'Carteira', icon: BriefcaseBusiness, keywords: ['posições', 'operações', 'transações', 'desempenho', 'P&L'] },
    ],
  },
  {
    items: [
      { to: '/assistente', label: 'Assistente', icon: MessagesSquare, keywords: ['perguntar', 'explicar', 'analisar ativo', 'revisar setup'] },
      { to: '/academia', label: 'Academia', icon: BookOpen, keywords: ['aulas', 'trilhas', 'lives', 'curso'], match: ['/aulas'] },
    ],
  },
];

export const SECONDARY_NAV: NavItem[] = [
  { to: '/configuracoes', label: 'Configurações', icon: Settings, keywords: ['perfil', 'conta', 'workspace', 'canais', 'usuários', 'sistema'] },
  { to: '/ajuda', label: 'Ajuda', icon: CircleHelp, keywords: ['como usar', 'manual'] },
];

export const ALL_NAV_ITEMS: NavItem[] = [...PRIMARY_NAV.flatMap((g) => g.items), ...SECONDARY_NAV];

export function isNavItemActive(item: NavItem, pathname: string): boolean {
  const paths = [item.to, ...(item.match ?? [])];
  return paths.some((p) => pathname === p || pathname.startsWith(`${p}/`));
}
