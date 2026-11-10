import { useState, type FormEvent } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { useAuth } from '../context/AuthContext';
import { ApiError } from '../api/client';

export function Cadastro() {
  const { cadastro } = useAuth();
  const navigate = useNavigate();
  const [username, setUsername] = useState('');
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [passwordConfirm, setPasswordConfirm] = useState('');
  const [acceptTerms, setAcceptTerms] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);

  async function handleSubmit(e: FormEvent) {
    e.preventDefault();
    setError(null);

    if (username.trim().length < 3) {
      setError('Usuário precisa ter pelo menos 3 caracteres.');
      return;
    }
    if (password.length < 8) {
      setError('Senha precisa ter pelo menos 8 caracteres.');
      return;
    }
    if (password !== passwordConfirm) {
      setError('As senhas não coincidem.');
      return;
    }
    if (!acceptTerms) {
      setError('Aceite os Termos de Uso e a Política de Privacidade para continuar.');
      return;
    }

    setSubmitting(true);
    try {
      await cadastro({ username, email, password, acceptTerms });
      navigate('/', { replace: true });
    } catch (err) {
      setError(err instanceof ApiError ? err.message : 'Erro ao criar conta. Tente de novo.');
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <div className="auth-body">
      <main className="auth-shell">
        <div className="auth-card">
          <div className="auth-brand">📈 Monitor NASDAQ</div>
          <h1>Criar conta</h1>
          <p className="muted">Você começa com o teste grátis do plano Pro. Sem cartão.</p>
          {error && <p className="form-error">{error}</p>}
          <form className="auth-form" onSubmit={handleSubmit}>
            <label className="field-label">
              Usuário
              <input
                type="text"
                autoComplete="username"
                minLength={3}
                required
                autoFocus
                value={username}
                onChange={(e) => setUsername(e.target.value)}
              />
            </label>
            <label className="field-label">
              E-mail
              <input
                type="email"
                autoComplete="email"
                required
                value={email}
                onChange={(e) => setEmail(e.target.value)}
              />
            </label>
            <label className="field-label">
              Senha
              <input
                type="password"
                autoComplete="new-password"
                minLength={8}
                required
                value={password}
                onChange={(e) => setPassword(e.target.value)}
              />
            </label>
            <label className="field-label">
              Confirmar senha
              <input
                type="password"
                autoComplete="new-password"
                minLength={8}
                required
                value={passwordConfirm}
                onChange={(e) => setPasswordConfirm(e.target.value)}
              />
            </label>
            <label className="terms-check">
              <input type="checkbox" checked={acceptTerms} onChange={(e) => setAcceptTerms(e.target.checked)} />
              <span>
                Li e aceito os <Link to="/termos">Termos de Uso</Link> e a{' '}
                <Link to="/privacidade">Política de Privacidade</Link>.
              </span>
            </label>
            <button type="submit" className="auth-submit" disabled={submitting}>
              {submitting ? 'Criando...' : 'Criar conta'}
            </button>
          </form>
          <p className="auth-footer-link">
            Já tem conta? <Link to="/login">Entrar</Link>
          </p>
        </div>
        <p className="disclaimer auth-disclaimer">
          Ferramenta apenas de monitoramento e informação. Não executa ordens e não constitui recomendação de
          investimento.
        </p>
      </main>
    </div>
  );
}
