import { useState, type FormEvent } from 'react';
import { api, ApiError } from '../api/client';
import { useApi } from '../hooks/useApi';
import { useToast } from '../context/ToastContext';
import { AsyncContent, Badge, Button, Input, Section, SkeletonLines, Table, type Column } from '../components/ui';
import { formatDateTime } from '../lib/format';
import type { User } from '../types';
import styles from './Configuracoes.module.css';

/** Configurações › Usuários (só administradores). */
export function Usuarios() {
  const toast = useToast();
  const users = useApi<User[]>('/api/auth/usuarios');
  const [form, setForm] = useState({ username: '', password: '', is_admin: false });
  const [error, setError] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);

  async function submit(e: FormEvent) {
    e.preventDefault();
    if (form.username.trim().length < 3) return setError('O usuário precisa de pelo menos 3 caracteres.');
    if (form.password.length < 8) return setError('A senha precisa de pelo menos 8 caracteres.');
    setError(null);
    setSaving(true);
    try {
      await api.post('/api/auth/usuarios', form);
      toast(`Usuário ${form.username} criado`, 'success');
      setForm({ username: '', password: '', is_admin: false });
      users.retry();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : 'Não foi possível criar o usuário');
    } finally {
      setSaving(false);
    }
  }

  const columns: Column<User>[] = [
    { key: 'u', header: 'Usuário', sortValue: (u) => u.username, render: (u) => <strong>{u.username}</strong> },
    { key: 'a', header: 'Acesso', render: (u) => (u.is_admin ? <Badge tone="info">administrador</Badge> : <Badge>usuário</Badge>) },
    { key: 'c', header: 'Criado em', sortValue: (u) => u.created_at, render: (u) => <span className="num muted">{formatDateTime(u.created_at)}</span> },
  ];

  return (
    <div className={styles.stack}>
      <Section title="Contas">
        <AsyncContent state={users} loading={<SkeletonLines lines={4} />} empty={<p className="muted">Nenhuma conta.</p>} errorTitle="Não foi possível carregar os usuários">
          {(list) => <Table caption="Contas" columns={columns} rows={list} rowKey={(u) => u.id} initialSort={{ key: 'u', dir: 'asc' }} dense />}
        </AsyncContent>
      </Section>
      <Section title="Criar usuário" divided>
        <form className={styles.form} onSubmit={submit}>
          <Input label="Usuário" value={form.username} onChange={(e) => setForm((f) => ({ ...f, username: e.target.value }))} autoComplete="off" className={styles.w260} />
          <Input
            label="Senha (mín. 8 caracteres)"
            type="password"
            value={form.password}
            onChange={(e) => setForm((f) => ({ ...f, password: e.target.value }))}
            autoComplete="new-password"
            className={styles.w260}
          />
          <label className={styles.check}>
            <input type="checkbox" checked={form.is_admin} onChange={(e) => setForm((f) => ({ ...f, is_admin: e.target.checked }))} />
            Administrador
          </label>
          <Button type="submit" variant="primary" loading={saving}>
            Criar usuário
          </Button>
        </form>
        {error && <p className={styles.error}>{error}</p>}
      </Section>
    </div>
  );
}
