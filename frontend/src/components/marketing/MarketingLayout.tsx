import { useState, type ReactNode } from 'react';
import { Menu, X } from 'lucide-react';
import { NavLink } from 'react-router-dom';
import { navLinks } from '../../content/onebMarketing';
import '../../styles/marketing.css';

export function MarketingLayout({ children }: { children: ReactNode }) {
  const [open, setOpen] = useState(false);

  return (
    <div className="oneb-site">
      <header className="oneb-header">
        <NavLink to="/" className="oneb-logo" onClick={() => setOpen(false)}>
          <span className="oneb-logo-mark" aria-hidden="true">
            <i />
            <i />
            <i />
            <i />
          </span>
          <span>
            OneB
            <small>Escola de Investimentos</small>
          </span>
        </NavLink>
        <button
          type="button"
          className="oneb-menu-btn"
          aria-label={open ? 'Fechar menu' : 'Abrir menu'}
          aria-expanded={open}
          onClick={() => setOpen((value) => !value)}
        >
          {open ? <X size={20} /> : <Menu size={20} />}
        </button>
        <nav className={open ? 'open' : ''} aria-label="Navegação principal">
          {navLinks.map((link) => (
            <NavLink key={link.href} to={link.href} onClick={() => setOpen(false)}>
              {link.label}
            </NavLink>
          ))}
        </nav>
        <div className="oneb-header-actions">
          <NavLink to="/login" className="oneb-login">
            Entrar
          </NavLink>
          <NavLink to="/cadastro" className="oneb-primary">
            Criar conta
          </NavLink>
        </div>
      </header>
      {children}
      <footer className="oneb-footer">
        <div>
          <div className="oneb-logo footer-logo">
            <span className="oneb-logo-mark" aria-hidden="true">
              <i />
              <i />
              <i />
              <i />
            </span>
            <span>
              OneB
              <small>Escola de Investimentos</small>
            </span>
          </div>
          <p>Escola de investimentos com terminal de apoio à decisão para estudar, praticar e revisar risco.</p>
        </div>
        <div>
          <strong>Navegação</strong>
          {navLinks.map((link) => (
            <NavLink key={link.href} to={link.href}>
              {link.label}
            </NavLink>
          ))}
        </div>
        <div>
          <strong>Institucional</strong>
          <a href="#termos">Termos</a>
          <a href="#privacidade">Privacidade</a>
          <a href="#risco">Aviso de risco</a>
        </div>
        <p className="oneb-risk">
          Ferramenta educacional e de monitoramento. Não executa ordens e não constitui recomendação de investimento.
          Operações no mercado financeiro envolvem riscos.
        </p>
      </footer>
    </div>
  );
}
