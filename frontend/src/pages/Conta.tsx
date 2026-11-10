import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { api, ApiError } from '../api/client';
import { useConfirm } from '../components/ConfirmModal';
import { useAuth } from '../context/AuthContext';
import { useToast } from '../context/ToastContext';

export function Conta() {
  const { user, refreshUser, logout } = useAuth();
  const toast = useToast();
  const confirm = useConfirm();
  const navigate = useNavigate();
  const [code, setCode] = useState<string | null>(null);

  if (!user) return null;

  async function generateCode() {
    try {
      const res = await api.post<{ code: string }>('/api/auth/telegram/link-code');
      setCode(res.code);
    } catch (err) {
      toast(err instanceof ApiError ? err.message : 'Erro ao gerar o código', 'error');
    }
  }

  async function unlink() {
    await api.delete('/api/auth/telegram');
    setCode(null);
    await refreshUser();
    toast('Telegram desvinculado', 'success');
  }

  async function deleteAccount() {
    const ok = await confirm(
      'Excluir sua conta apaga watchlist, regras, posições e alertas. Não dá para desfazer. Continuar?',
    );
    if (!ok) return;
    try {
      await api.delete('/api/auth/me');
      logout();
      navigate('/', { replace: true });
    } catch (err) {
      toast(err instanceof ApiError ? err.message : 'Erro ao excluir a conta', 'error');
    }
  }

  return (
    <div className="container">
      <div className="page-header">
        <div>
          <p className="eyebrow">Conta</p>
          <h1>{user.username}</h1>
          <p className="muted">{user.email ?? 'Sem e-mail cadastrado'}</p>
        </div>
      </div>

      <section className="panel" style={{ marginBottom: '1rem' }}>
        <h2>Telegram</h2>
        {user.plan !== 'pro' ? (
          <p className="muted">Alertas e resumos no Telegram fazem parte do plano Pro.</p>
        ) : user.telegram_linked ? (
          <>
            <p>Chat vinculado. Os alertas das suas regras chegam por lá.</p>
            <button type="button" className="btn-secondary" onClick={unlink}>
              Desvincular
            </button>
          </>
        ) : (
          <>
            <p className="muted">
              Gere um código e envie ao bot do Telegram o comando <code>/vincular CODIGO</code>.
            </p>
            {code ? (
              <p>
                Código: <strong className="link-code">{code}</strong>
                <span className="muted"> · uso único. Depois de enviar ao bot, recarregue esta página.</span>
              </p>
            ) : (
              <button type="button" onClick={generateCode}>
                Gerar código
              </button>
            )}
          </>
        )}
      </section>

      <section className="panel">
        <h2>Privacidade</h2>
        <p className="muted">
          Você pode apagar sua conta e todos os seus dados a qualquer momento. Se tiver uma assinatura ativa,
          cancele-a antes em Planos.
        </p>
        <button type="button" className="btn-danger" onClick={deleteAccount}>
          Excluir minha conta
        </button>
      </section>
    </div>
  );
}
