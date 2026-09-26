import { useEffect, useId, useRef, useState, type ReactElement, type ReactNode } from 'react';
import styles from './Tooltip.module.css';

interface TooltipProps {
  content: ReactNode;
  children: ReactElement;
  placement?: 'top' | 'bottom';
}

/** Dica curta em hover e foco. O conteúdo é descrição, nunca a única fonte da informação. */
export function Tooltip({ content, children, placement = 'top' }: TooltipProps) {
  const [open, setOpen] = useState(false);
  const id = useId();
  return (
    <span
      className={styles.wrap}
      onMouseEnter={() => setOpen(true)}
      onMouseLeave={() => setOpen(false)}
      onFocus={() => setOpen(true)}
      onBlur={() => setOpen(false)}
      onKeyDown={(e) => e.key === 'Escape' && setOpen(false)}
      aria-describedby={open ? id : undefined}
    >
      {children}
      {open && (
        <span role="tooltip" id={id} className={[styles.tip, placement === 'bottom' ? styles.bottom : ''].join(' ')}>
          {content}
        </span>
      )}
    </span>
  );
}

interface PopoverProps {
  trigger: ReactNode;
  triggerLabel?: string;
  title?: ReactNode;
  children: ReactNode;
  footer?: ReactNode;
  placement?: 'top' | 'bottom';
  triggerClassName?: string;
}

/** Popover aberto por clique (ex.: "Entenda"). Fecha no Esc e ao clicar fora. */
export function Popover({ trigger, triggerLabel, title, children, footer, placement = 'bottom', triggerClassName }: PopoverProps) {
  const [open, setOpen] = useState(false);
  const ref = useRef<HTMLSpanElement>(null);
  const id = useId();

  useEffect(() => {
    if (!open) return;
    function onDown(e: MouseEvent) {
      if (ref.current && !ref.current.contains(e.target as Node)) setOpen(false);
    }
    document.addEventListener('mousedown', onDown);
    return () => document.removeEventListener('mousedown', onDown);
  }, [open]);

  return (
    <span className={styles.wrap} ref={ref} onKeyDown={(e) => e.key === 'Escape' && setOpen(false)}>
      <button
        type="button"
        className={triggerClassName ?? styles.trigger}
        aria-expanded={open}
        aria-controls={id}
        aria-label={triggerLabel}
        onClick={() => setOpen((v) => !v)}
      >
        {trigger}
      </button>
      {open && (
        <span id={id} role="dialog" aria-label={typeof title === 'string' ? title : triggerLabel} className={[styles.tip, styles.popover, placement === 'bottom' ? styles.bottom : ''].join(' ')}>
          {title && <span className={styles.popoverTitle}>{title}</span>}
          <span className={styles.popoverBody}>{children}</span>
          {footer && <span className={styles.popoverFooter}>{footer}</span>}
        </span>
      )}
    </span>
  );
}
