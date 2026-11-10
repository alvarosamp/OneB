import { createContext, useCallback, useContext, useRef, useState, type ReactNode } from 'react';
import { Button } from './ui/Button';
import { Modal } from './ui/Modal';

type ConfirmFn = (message: string) => Promise<boolean>;

const ConfirmContext = createContext<ConfirmFn | null>(null);

/** Confirmação de ações destrutivas, com foco preso e Esc para cancelar. */
export function ConfirmProvider({ children }: { children: ReactNode }) {
  const [message, setMessage] = useState<string | null>(null);
  const resolverRef = useRef<((result: boolean) => void) | null>(null);

  const confirm = useCallback<ConfirmFn>((msg) => {
    return new Promise((resolve) => {
      resolverRef.current = resolve;
      setMessage(msg);
    });
  }, []);

  function close(result: boolean) {
    setMessage(null);
    resolverRef.current?.(result);
    resolverRef.current = null;
  }

  return (
    <ConfirmContext.Provider value={confirm}>
      {children}
      <Modal
        open={message !== null}
        onClose={() => close(false)}
        title="Confirmar"
        footer={
          <>
            <Button onClick={() => close(false)}>Cancelar</Button>
            <Button variant="danger" data-autofocus onClick={() => close(true)}>
              Confirmar
            </Button>
          </>
        }
      >
        <p>{message}</p>
      </Modal>
    </ConfirmContext.Provider>
  );
}

export function useConfirm(): ConfirmFn {
  const ctx = useContext(ConfirmContext);
  if (!ctx) throw new Error('useConfirm precisa estar dentro de <ConfirmProvider>');
  return ctx;
}
