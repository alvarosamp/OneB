import { Component, type ErrorInfo, type ReactNode } from 'react';

interface Props {
  children: ReactNode;
}

interface State {
  failed: boolean;
}

/** Keeps an unexpected rendering failure isolated from the rest of the application. */
export class AppErrorBoundary extends Component<Props, State> {
  state: State = { failed: false };

  static getDerivedStateFromError(): State {
    return { failed: true };
  }

  componentDidCatch(error: Error, info: ErrorInfo) {
    // Keep diagnostic information available in development without exposing it to users.
    console.error('Erro ao renderizar a aplicação OneB.', error, info);
  }

  render() {
    if (this.state.failed) {
      return (
        <main className="app-error-state" role="alert">
          <p className="eyebrow">Erro inesperado</p>
          <h1>Não foi possível abrir esta tela.</h1>
          <p className="muted">Se o problema persistir, atualize a página ou volte ao início.</p>
          <div className="app-error-actions">
            <a className="btn-secondary" href="/inicio">Ir para o início</a>
            <button type="button" onClick={() => window.location.reload()}>Atualizar página</button>
          </div>
        </main>
      );
    }

    return this.props.children;
  }
}
