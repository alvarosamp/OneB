import { useId, useRef, type ReactNode } from 'react';
import { createPortal } from 'react-dom';
import { X } from 'lucide-react';
import { useFocusTrap } from '../../hooks/useFocusTrap';
import { Button } from './Button';
import { ICON } from './icon';
import styles from './Modal.module.css';

interface ModalProps {
  open: boolean;
  onClose: () => void;
  title: ReactNode;
  children: ReactNode;
  footer?: ReactNode;
  /** 'dialog' centralizado, 'sheet' pela base (mobile), 'drawer' lateral. */
  variant?: 'dialog' | 'sheet' | 'drawer';
  wide?: boolean;
  /** Sem padding no corpo e sem cabeçalho visível (ex.: command palette). */
  bare?: boolean;
  className?: string;
  /** Comportamento do Esc (padrão: fechar). */
  onEscape?: () => void;
}

export function Modal({ open, onClose, title, children, footer, variant = 'dialog', wide, bare, className, onEscape }: ModalProps) {
  const ref = useRef<HTMLDivElement>(null);
  const titleId = useId();
  useFocusTrap(ref, open, onEscape ?? onClose);
  if (!open) return null;

  const overlayCls = [styles.overlay, variant === 'sheet' ? styles.sheetOverlay : '', variant === 'drawer' ? styles.drawerOverlay : ''].join(' ');
  const dialogCls = [
    styles.dialog,
    variant === 'sheet' ? styles.sheet : '',
    variant === 'drawer' ? styles.drawer : '',
    wide ? styles.wide : '',
    bare ? styles.bare : '',
    className ?? '',
  ].join(' ');

  return createPortal(
    <div className={overlayCls} onMouseDown={(e) => e.target === e.currentTarget && onClose()}>
      <div ref={ref} role="dialog" aria-modal="true" aria-labelledby={titleId} className={dialogCls} tabIndex={-1}>
        {bare ? (
          <h2 id={titleId} className="sr-only">
            {title}
          </h2>
        ) : (
          <div className={styles.header}>
            <h2 id={titleId} className={styles.title}>
              {title}
            </h2>
            <Button variant="ghost" size="sm" iconOnly icon={<X {...ICON} />} aria-label="Fechar" onClick={onClose} />
          </div>
        )}
        <div className={styles.body}>{children}</div>
        {footer && <div className={styles.footer}>{footer}</div>}
      </div>
    </div>,
    document.body,
  );
}
