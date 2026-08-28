import { Link } from 'react-router-dom';

export function NaoEncontrado() {
  return (
    <main className="app-error-state">
      <p className="eyebrow">Página não encontrada</p>
      <h1>Este endereço não existe.</h1>
      <p className="muted">Use o início para voltar ao seu ambiente OneB.</p>
      <Link className="btn-secondary" to="/inicio">Ir para o início</Link>
    </main>
  );
}
