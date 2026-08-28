import { useEffect, useState, type FormEvent } from 'react';
import { api, ApiError } from '../api/client';
import type { User } from '../types';
import { useToast } from '../context/ToastContext';

export function Usuarios() {
  const toast = useToast();
  const [users, setUsers] = useState<User[]>([]);
  const [loading, setLoading] = useState(true);
  const [username, setUsername] = useState('');
  const [password, setPassword] = useState('');
  const [isAdmin, setIsAdmin] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);

  async function load() {
    setLoading(true);
    try {
      setUsers(await api.get<User[]>('/api/auth/usuarios'));
    } catch {
      toast('Erro ao carregar usuários', 'error');
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    load();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  async function handleSubmit(e: FormEvent) {
    e.preventDefault();
    setError(null);
    setSubmitting(true);
    try {
      await api.post('/api/auth/usuarios', { username, password, is_admin: isAdmin });
      toast(`Usuário ${username} criado`, 'success');
      setUsername('');
      setPassword('');
      setIsAdmin(false);
      load();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : 'Erro ao criar usuário');
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <div className="container">
      <div className="page-header">
        <div>
          <p className="eyebrow">Administração</p>
          <h1>Usuários</h1>
          <p className="muted">Contas com acesso à plataforma e permissões de administrador.</p>
        </div>
      </div>

      <section className="panel">
        <h2>Contas cadastradas</h2>
        <div className="table-scroll compact-scroll">
          <table className="table dense-table">
            <thead>
              <tr>
                <th>Usuário</th>
                <th>Admin</th>
                <th>Criado em</th>
              </tr>
            </thead>
            <tbody>
              {loading ? (
                <tr>
                  <td colSpan={3} className="muted">
                    Carregando...
                  </td>
                </tr>
              ) : (
                users.map((u) => (
                  <tr key={u.id}>
                    <td>{u.username}</td>
                    <td>
                      <span className={`status-pill ${u.is_admin ? 'good' : ''}`}>{u.is_admin ? 'Admin' : 'Usuário'}</span>
                    </td>
                    <td className="muted">{new Date(u.created_at).toLocaleString('pt-BR')}</td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>
      </section>

      <section className="panel">
        <h2>Criar novo usuário</h2>
        {error && <p className="form-error">{error}</p>}
        <form onSubmit={handleSubmit}>
          <label className="field-label">
            Usuário
            <input type="text" minLength={3} required value={username} onChange={(e) => setUsername(e.target.value)} />
          </label>
          <label className="field-label">
            Senha
            <input
              type="password"
              minLength={8}
              required
              value={password}
              onChange={(e) => setPassword(e.target.value)}
            />
          </label>
          <label className="field-label" style={{ flexDirection: 'row', alignItems: 'center', gap: '0.4rem' }}>
            <input
              type="checkbox"
              checked={isAdmin}
              onChange={(e) => setIsAdmin(e.target.checked)}
              style={{ minHeight: 'auto', width: 'auto' }}
            />
            Administrador
          </label>
          <button type="submit" disabled={submitting}>
            Criar usuário
          </button>
        </form>
      </section>
    </div>
  );
}
