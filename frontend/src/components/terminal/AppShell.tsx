import { Suspense, useEffect, useState, type ReactNode } from 'react';
import { Outlet, useLocation } from 'react-router-dom';
import { readStorage, writeStorage } from '../../lib/storage';
import { Modal, SkeletonLines } from '../ui';
import { Sidebar } from './Sidebar';
import { Topbar } from './Topbar';
import { CommandPaletteProvider } from './CommandPaletteContext';
import { MarketStatus } from './MarketStatus';
import { BottomNav } from './BottomNav';
import styles from './AppShell.module.css';

const COLLAPSE_KEY = 'oneb.sidebar.collapsed';

/** Layout único do app logado: sidebar + barra fina no topo + conteúdo. */
export function AppShell({ status, bottomNav }: { status?: ReactNode; bottomNav?: ReactNode }) {
  const [collapsed, setCollapsed] = useState(() => readStorage(COLLAPSE_KEY) === '1');
  const [drawerOpen, setDrawerOpen] = useState(false);
  const { pathname } = useLocation();

  useEffect(() => {
    writeStorage(COLLAPSE_KEY, collapsed ? '1' : '0');
  }, [collapsed]);

  useEffect(() => {
    setDrawerOpen(false);
  }, [pathname]);

  return (
    <CommandPaletteProvider>
      <a href="#conteudo" className="skip-link">
        Pular para o conteúdo
      </a>
      <div className={[styles.shell, collapsed ? styles.collapsed : ''].join(' ')}>
        <aside className={styles.sidebarSlot}>
          <Sidebar collapsed={collapsed} onToggleCollapsed={() => setCollapsed((v) => !v)} />
        </aside>
        <div className={styles.topbarSlot}>
          <Topbar onOpenMenu={() => setDrawerOpen(true)} status={status ?? <MarketStatus />} />
        </div>
        <div className={styles.main}>
          <main id="conteudo" className={styles.content} tabIndex={-1}>
            <Suspense fallback={<SkeletonLines lines={8} label="Carregando a página" />}>
              <Outlet />
            </Suspense>
          </main>
          <footer className={styles.disclaimer}>
            O OneB monitora o mercado e explica os dados coletados. Não executa ordens e não recomenda compra ou venda. Dados podem ter
            atraso.
          </footer>
        </div>
      </div>
      {bottomNav ?? <BottomNav />}
      <Modal open={drawerOpen} onClose={() => setDrawerOpen(false)} title="Menu" variant="drawer" bare>
        <Sidebar inDrawer onNavigate={() => setDrawerOpen(false)} />
      </Modal>
    </CommandPaletteProvider>
  );
}
