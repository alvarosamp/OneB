import { useState, type FormEvent } from 'react';
import { Link, useLocation, useNavigate } from 'react-router-dom';
import { useAuth } from '../context/AuthContext';
import { ApiError } from '../api/client';

export function Login() {
  const { login } = useAuth();
  const navigate = useNavigate();
  const location = useLocation();
  const [username, setUsername] = useState('');
  const [password, setPassword] = useState('');
  const [error, setError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);

  async function handleSubmit(e: FormEvent) {
    e.preventDefault();
    setError(null);
    setSubmitting(true);
    try {
      await login(username, password);
      const from = (location.state as { from?: string } | null)?.from ?? '/';
      navigate(from, { replace: true });
    } catch (err) {
      setError(err instanceof ApiError ? err.message : 'Erro ao entrar. Tente de novo.');
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <div className="auth-body">
      <main className="auth-shell">
        <div className="auth-card">
          <div className="auth-brand">📈 Monitor NASDAQ</div>
          <h1>Entrar</h1>
          {error && <p className="form-error">{error}</p>}
          <form className="auth-form" onSubmit={handleSubmit}>
            <label className="field-label">
              Usuário ou e-mail
              <input
                type="text"
                autoComplete="username"
                required
                autoFocus
                value={username}
                onChange={(e) => setUsername(e.target.value)}
              />
            </label>
            <label className="field-label">
              Senha
              <input
                type="password"
                autoComplete="current-password"
                required
                value={password}
                onChange={(e) => setPassword(e.target.value)}
              />
            </label>
            <button type="submit" className="auth-submit" disabled={submitting}>
              {submitting ? 'Entrando...' : 'Entrar'}
            </button>
          </form>
          <p className="auth-footer-link">
            Novo por aqui? <Link to="/cadastro">Criar conta</Link>
          </p>
        </div>
        <p className="disclaimer auth-disclaimer">
          Ferramenta apenas de monitoramento e sugestão. Não executa ordens e não constitui
          recomendação de investimento.
        </p>
      </main>
    </div>
  );
}
