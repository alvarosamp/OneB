import { Component, type ErrorInfo, type ReactNode } from 'react';
import { CenteredMessage } from './AuthLayout';
import { Button } from './ui';
import { buttonClass } from './ui/buttonClass';

interface Props {
  children: ReactNode;
}

interface State {
  failed: boolean;
}

/** Mantém uma falha de renderização isolada do resto do app. */
export class AppErrorBoundary extends Component<Props, State> {
  state: State = { failed: false };

  static getDerivedStateFromError(): State {
    return { failed: true };
  }

  componentDidCatch(error: Error, info: ErrorInfo) {
    // Diagnóstico disponível no console sem expor detalhes ao usuário.
    console.error('Erro ao renderizar a aplicação OneB.', error, info);
  }

  render() {
    if (this.state.failed) {
      return (
        <CenteredMessage role="alert" title="Não foi possível abrir esta tela" description="Atualize a página. Se o problema continuar, volte para o Hoje.">
          <a className={buttonClass({})} href="/ferramenta">
            Ir para o Hoje
          </a>
          <Button variant="primary" onClick={() => window.location.reload()}>
            Atualizar página
          </Button>
        </CenteredMessage>
      );
    }
    return this.props.children;
  }
}
