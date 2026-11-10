import { useState } from 'react';
import { NavLink, useNavigate } from 'react-router-dom';
import { useAuth } from '../context/AuthContext';
import { fetchBlob } from '../api/client';
import { useToast } from '../context/ToastContext';

export function Navbar() {
  const { user, logout } = useAuth();
  const navigate = useNavigate();
  const toast = useToast();
  const [menuOpen, setMenuOpen] = useState(false);
  const [downloading, setDownloading] = useState(false);

  if (!user) return null;

  function handleLogout() {
    logout();
    navigate('/login');
  }

  async function handleDownloadPdf() {
    setDownloading(true);
    try {
      const blob = await fetchBlob('/api/reports/pdf');
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = `monitor-nasdaq-${new Date().toISOString().slice(0, 10)}.pdf`;
      a.click();
      URL.revokeObjectURL(url);
    } catch {
      toast('Erro ao gerar o relatório PDF', 'error');
    } finally {
      setDownloading(false);
    }
  }

  return (
    <header className="topbar">
      <NavLink to="/" className="brand">
        📈 Monitor NASDAQ
      </NavLink>
      <input
        type="checkbox"
        id="nav-toggle"
        className="nav-toggle-input"
        checked={menuOpen}
        onChange={(e) => setMenuOpen(e.target.checked)}
      />
      <label htmlFor="nav-toggle" className="nav-toggle-label" aria-label="Abrir menu">
        ☰
      </label>
      <nav>
        <NavLink to="/" end>
          Dashboard
        </NavLink>
        <NavLink to="/watchlist">Watchlist &amp; Regras</NavLink>
        <NavLink to="/analise-matinal">Analise Matinal</NavLink>
        <NavLink to="/mercado">Mercado</NavLink>
        <NavLink to="/analise">Análise</NavLink>
        <NavLink to="/pesquisa">Pesquisa</NavLink>
        <NavLink to="/alertas">Alertas</NavLink>
        <NavLink to="/posicoes">Posições</NavLink>
        <NavLink to="/perfil">Perfil</NavLink>
        <NavLink to="/copiloto">Copiloto</NavLink>
        <NavLink to="/assistente">Assistente IA</NavLink>
        <NavLink to="/como-usar">Como usar</NavLink>
        <NavLink to="/planos">Planos</NavLink>
        <NavLink to="/conta">Conta</NavLink>
        {user.is_admin && <NavLink to="/usuarios">Usuários</NavLink>}
        <button type="button" className="nav-link" onClick={handleDownloadPdf} disabled={downloading}>
          {downloading ? 'Gerando...' : 'Baixar PDF'}
        </button>
        <span className="nav-user">
          {user.username} <span className="plan-badge">{user.plan === 'pro' ? (user.on_trial ? 'Teste' : 'Pro') : 'Free'}</span>
          <button type="button" className="link-btn" onClick={handleLogout}>
            Sair
          </button>
        </span>
      </nav>
    </header>
  );
}
