import { useState } from 'react';
import { Link, useLocation, useNavigate } from 'react-router-dom';
import { Bell, BellPlus, LayoutDashboard, MessagesSquare, Newspaper, Plus, Search, Eye, MessageCircleQuestion } from 'lucide-react';
import { Modal, ICON, ICON_LG } from '../ui';
import { useCommandPalette } from './CommandPaletteContext';
import styles from './BottomNav.module.css';

const ITEMS = [
  { to: '/ferramenta', label: 'Hoje', icon: LayoutDashboard },
  { to: '/mercado', label: 'Mercado', icon: Newspaper },
  null,
  { to: '/alertas', label: 'Alertas', icon: Bell },
  { to: '/assistente', label: 'Assistente', icon: MessagesSquare },
] as const;

/** Navegação inferior no mobile (<768px), com ações rápidas no [+]. */
export function BottomNav() {
  const { pathname } = useLocation();
  const navigate = useNavigate();
  const palette = useCommandPalette();
  const [open, setOpen] = useState(false);

  function go(to: string) {
    setOpen(false);
    navigate(to);
  }

  return (
    <>
      <nav className={styles.nav} aria-label="Navegação rápida">
        {ITEMS.map((item) => {
          if (!item) {
            return (
              <button key="plus" type="button" className={styles.plus} aria-label="Ações rápidas" aria-haspopup="dialog" aria-expanded={open} onClick={() => setOpen(true)}>
                <Plus {...ICON_LG} aria-hidden="true" />
              </button>
            );
          }
          const Icon = item.icon;
          const active = pathname === item.to || pathname.startsWith(`${item.to}/`);
          return (
            <Link key={item.to} to={item.to} className={[styles.item, active ? styles.active : ''].join(' ')} aria-current={active ? 'page' : undefined}>
              <Icon {...ICON_LG} aria-hidden="true" />
              {item.label}
            </Link>
          );
        })}
      </nav>
      <Modal open={open} onClose={() => setOpen(false)} title="Ações rápidas" variant="sheet">
        <ul className={styles.sheetList}>
          <li>
            <button
              type="button"
              className={styles.sheetItem}
              onClick={() => {
                setOpen(false);
                palette.open();
              }}
            >
              <Search {...ICON} aria-hidden="true" />
              Buscar ativo
            </button>
          </li>
          <li>
            <button type="button" className={styles.sheetItem} onClick={() => go('/watchlist?regra=')}>
              <BellPlus {...ICON} aria-hidden="true" />
              Criar alerta
            </button>
          </li>
          <li>
            <button type="button" className={styles.sheetItem} onClick={() => go('/watchlist?adicionar=')}>
              <Eye {...ICON} aria-hidden="true" />
              Adicionar à watchlist
            </button>
          </li>
          <li>
            <button type="button" className={styles.sheetItem} onClick={() => go('/assistente?modo=perguntar')}>
              <MessageCircleQuestion {...ICON} aria-hidden="true" />
              Perguntar
            </button>
          </li>
        </ul>
      </Modal>
    </>
  );
}
