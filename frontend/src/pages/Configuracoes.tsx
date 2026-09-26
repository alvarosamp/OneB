import type { ReactNode } from 'react';
import { TabbedPage } from '../components/terminal/TabbedPage';
import { useAuth } from '../context/AuthContext';
import { Saas } from './Saas';
import { Operacoes } from './Operacoes';
import { Usuarios } from './Usuarios';
import { Conta } from './Conta';

type ConfigTab = 'conta' | 'workspace' | 'usuarios' | 'sistema';

export function Configuracoes() {
  const { user } = useAuth();
  const isAdmin = !!user?.is_admin;
  const tabs: { value: ConfigTab; label: string; render: () => ReactNode }[] = [
    { value: 'conta', label: 'Conta', render: () => <Conta /> },
    { value: 'workspace', label: 'Workspace e canais', render: () => <Saas /> },
  ];
  if (isAdmin) {
    tabs.push({ value: 'usuarios', label: 'Usuários', render: () => <Usuarios /> });
    tabs.push({ value: 'sistema', label: 'Sistema', render: () => <Operacoes /> });
  }
  return <TabbedPage<ConfigTab> title="Configurações" fallback="conta" tabs={tabs} />;
}
