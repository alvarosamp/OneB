import { useState, type FormEvent } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { useAuth } from '../context/AuthContext';
import { ApiError } from '../api/client';
import { AuthLayout } from '../components/AuthLayout';
import styles from '../components/AuthLayout.module.css';
import { Button, Input } from '../components/ui';

export function Cadastro() {
  const { cadastro } = useAuth();
  const navigate = useNavigate();
  const [username, setUsername] = useState('');
  const [password, setPassword] = useState('');
  const [passwordConfirm, setPasswordConfirm] = useState('');
  const [error, setError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);

  async function handleSubmit(e: FormEvent) {
    e.preventDefault();
    setError(null);
    if (username.trim().length < 3) return setError('O usuário precisa ter pelo menos 3 caracteres.');
    if (password.length < 8) return setError('A senha precisa ter pelo menos 8 caracteres.');
    if (password !== passwordConfirm) return setError('As senhas não coincidem.');
    setSubmitting(true);
    try {
      await cadastro(username, password);
      navigate('/ferramenta', { replace: true });
    } catch (err) {
      setError(err instanceof ApiError ? err.message : 'Não foi possível criar a conta. Tente de novo.');
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <AuthLayout
      title="Criar conta"
      description="Escolha um usuário e uma senha para acessar o terminal e a Academia."
      footer={
        <>
          Já tem conta? <Link to="/login">Entrar</Link>
        </>
      }
    >
      {error && (
        <p className={styles.error} role="alert">
          {error}
        </p>
      )}
      <form className={styles.form} onSubmit={handleSubmit}>
        <Input label="Usuário" autoComplete="username" minLength={3} required autoFocus value={username} onChange={(e) => setUsername(e.target.value)} />
        <Input label="Senha" hint="Mínimo de 8 caracteres." type="password" autoComplete="new-password" minLength={8} required value={password} onChange={(e) => setPassword(e.target.value)} />
        <Input label="Confirmar senha" type="password" autoComplete="new-password" minLength={8} required value={passwordConfirm} onChange={(e) => setPasswordConfirm(e.target.value)} />
        <Button type="submit" variant="primary" size="lg" block loading={submitting}>
          Criar conta
        </Button>
      </form>
    </AuthLayout>
  );
}
