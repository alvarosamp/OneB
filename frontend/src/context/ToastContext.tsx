import { createContext, useCallback, useContext, useRef, useState, type ReactNode } from 'react';
import { AlertTriangle, CheckCircle2, Info, X } from 'lucide-react';
import styles from './Toast.module.css';

type ToastType = 'info' | 'success' | 'error';

interface ToastItem {
  id: number;
  message: string;
  type: ToastType;
}

interface ToastContextValue {
  toast: (message: string, type?: ToastType) => void;
}

const ToastContext = createContext<ToastContextValue | null>(null);

const ICONS = { info: Info, success: CheckCircle2, error: AlertTriangle };

/**
 * Confirmações curtas. O texto repete o verbo da ação ("Alerta criado").
 * Erros ficam mais tempo e podem ser fechados.
 */
export function ToastProvider({ children }: { children: ReactNode }) {
  const [items, setItems] = useState<ToastItem[]>([]);
  const counter = useRef(0);

  const dismiss = useCallback((id: number) => setItems((prev) => prev.filter((t) => t.id !== id)), []);

  const toast = useCallback(
    (message: string, type: ToastType = 'info') => {
      const id = counter.current++;
      setItems((prev) => [...prev.slice(-3), { id, message, type }]);
      setTimeout(() => dismiss(id), type === 'error' ? 7000 : 4000);
    },
    [dismiss],
  );

  return (
    <ToastContext.Provider value={{ toast }}>
      {children}
      <div className={styles.region} role="status" aria-live="polite">
        {items.map((item) => {
          const Icon = ICONS[item.type];
          return (
            <div key={item.id} className={[styles.toast, styles[item.type]].join(' ')} role={item.type === 'error' ? 'alert' : undefined}>
              <Icon size={16} strokeWidth={1.75} aria-hidden="true" />
              <span>{item.message}</span>
              <button type="button" className={styles.close} aria-label="Fechar aviso" onClick={() => dismiss(item.id)}>
                <X size={14} strokeWidth={1.75} aria-hidden="true" />
              </button>
            </div>
          );
        })}
      </div>
    </ToastContext.Provider>
  );
}

export function useToast(): ToastContextValue['toast'] {
  const ctx = useContext(ToastContext);
  if (!ctx) throw new Error('useToast precisa estar dentro de <ToastProvider>');
  return ctx.toast;
}
