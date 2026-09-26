import { useEffect, useRef, useState, type KeyboardEvent, type ReactNode } from 'react';
import { NavLink, useNavigate } from 'react-router-dom';
import { ChevronDown, FileDown, LogOut, Menu, Moon, Search, Settings, Sun } from 'lucide-react';
import { useAuth } from '../../context/AuthContext';
import { useTheme } from '../../context/ThemeContext';
import { useToast } from '../../context/ToastContext';
import { fetchBlob } from '../../api/client';
import { Button, ICON } from '../ui';
import { BrandMark } from './Sidebar';
import { useCommandPalette } from './CommandPaletteContext';
import styles from './Topbar.module.css';

const isMac = typeof navigator !== 'undefined' && /Mac|iPhone|iPad/.test(navigator.platform);

export function Topbar({ onOpenMenu, status }: { onOpenMenu: () => void; status?: ReactNode }) {
  const { user, logout } = useAuth();
  const { theme, toggleTheme } = useTheme();
  const palette = useCommandPalette();
  const toast = useToast();
  const navigate = useNavigate();
  const [menuOpen, setMenuOpen] = useState(false);
  const [downloading, setDownloading] = useState(false);
  const menuRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!menuOpen) return;
    const first = menuRef.current?.querySelector<HTMLElement>('[role="menuitem"]');
    first?.focus();
    function onDown(e: MouseEvent) {
      if (menuRef.current && !menuRef.current.contains(e.target as Node)) setMenuOpen(false);
    }
    document.addEventListener('mousedown', onDown);
    return () => document.removeEventListener('mousedown', onDown);
  }, [menuOpen]);

  function onMenuKey(e: KeyboardEvent) {
    if (e.key === 'Escape') {
      setMenuOpen(false);
      menuRef.current?.querySelector<HTMLElement>('button[aria-haspopup]')?.focus();
      return;
    }
    if (e.key !== 'ArrowDown' && e.key !== 'ArrowUp') return;
    e.preventDefault();
    const items = Array.from(menuRef.current?.querySelectorAll<HTMLElement>('[role="menuitem"]') ?? []);
    const i = items.indexOf(document.activeElement as HTMLElement);
    const next = e.key === 'ArrowDown' ? (i + 1) % items.length : (i - 1 + items.length) % items.length;
    items[next]?.focus();
  }

  async function downloadPdf() {
    setDownloading(true);
    try {
      const blob = await fetchBlob('/api/reports/pdf');
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = `oneb-relatorio-${new Date().toISOString().slice(0, 10)}.pdf`;
      a.click();
      URL.revokeObjectURL(url);
      toast('Relatório baixado', 'success');
    } catch (err) {
      toast(err instanceof Error ? `Não foi possível baixar o relatório: ${err.message}` : 'Não foi possível baixar o relatório', 'error');
    } finally {
      setDownloading(false);
      setMenuOpen(false);
    }
  }

  function handleLogout() {
    logout();
    navigate('/login');
  }

  if (!user) return null;

  return (
    <header className={styles.topbar}>
      <Button variant="ghost" iconOnly className={styles.menuButton} icon={<Menu {...ICON} />} aria-label="Abrir menu" onClick={onOpenMenu} />
      <NavLink to="/ferramenta" className={styles.mobileBrand} aria-label="OneB, ir para Hoje">
        <BrandMark />
        OneB
      </NavLink>

      <button type="button" className={styles.search} onClick={palette.open} aria-label="Buscar ativo ou página" aria-keyshortcuts={isMac ? 'Meta+K' : 'Control+K'}>
        <Search {...ICON} aria-hidden="true" />
        <span className={styles.searchText}>Buscar ativo ou página</span>
        <kbd className={styles.kbd}>{isMac ? '⌘K' : 'Ctrl K'}</kbd>
      </button>

      <div className={styles.spacer} />

      <div className={styles.actions}>
        {status}
        <Button
          variant="ghost"
          iconOnly
          icon={theme === 'dark' ? <Sun {...ICON} /> : <Moon {...ICON} />}
          aria-label={theme === 'dark' ? 'Usar tema claro' : 'Usar tema escuro'}
          title={theme === 'dark' ? 'Usar tema claro' : 'Usar tema escuro'}
          onClick={toggleTheme}
        />
        <div className={styles.userMenu} ref={menuRef} onKeyDown={onMenuKey}>
          <button type="button" className={styles.userTrigger} aria-haspopup="menu" aria-expanded={menuOpen} onClick={() => setMenuOpen((v) => !v)}>
            <span className={styles.avatar} aria-hidden="true">
              {user.username.slice(0, 1).toUpperCase()}
            </span>
            <span className={styles.userName}>{user.username}</span>
            <ChevronDown {...ICON} className={styles.caret} aria-hidden="true" />
            <span className="sr-only">Menu da conta</span>
          </button>
          {menuOpen && (
            <div className={styles.menu} role="menu" aria-label="Conta">
              <div className={styles.menuHeader}>
                <strong>{user.username}</strong>
                {user.is_admin ? 'Administrador' : 'Conta pessoal'}
              </div>
              <NavLink to="/configuracoes" role="menuitem" className={styles.menuItem} onClick={() => setMenuOpen(false)}>
                <Settings {...ICON} aria-hidden="true" />
                Configurações
              </NavLink>
              <button type="button" role="menuitem" className={styles.menuItem} onClick={downloadPdf} disabled={downloading}>
                <FileDown {...ICON} aria-hidden="true" />
                {downloading ? 'Gerando relatório…' : 'Baixar relatório em PDF'}
              </button>
              <button type="button" role="menuitem" className={styles.menuItem} onClick={handleLogout}>
                <LogOut {...ICON} aria-hidden="true" />
                Sair
              </button>
            </div>
          )}
        </div>
      </div>
    </header>
  );
}
