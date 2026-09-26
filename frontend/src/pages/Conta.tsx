import { useAuth } from '../context/AuthContext';
import { useTheme } from '../context/ThemeContext';
import { Button, Section } from '../components/ui';
import styles from './Conta.module.css';

/** Dados da conta (somente leitura: a API não expõe edição de perfil). */
export function Conta() {
  const { user, logout } = useAuth();
  const { theme, toggleTheme } = useTheme();
  if (!user) return null;
  return (
    <div className={styles.grid}>
      <Section title="Conta">
        <dl className={styles.list}>
          <dt>Usuário</dt>
          <dd>{user.username}</dd>
          <dt>Tipo de acesso</dt>
          <dd>{user.is_admin ? 'Administrador' : 'Conta pessoal'}</dd>
        </dl>
      </Section>
      <Section title="Aparência">
        <div className={styles.row}>
          <span>Tema {theme === 'dark' ? 'escuro' : 'claro'}</span>
          <Button size="sm" onClick={toggleTheme}>
            {theme === 'dark' ? 'Usar tema claro' : 'Usar tema escuro'}
          </Button>
        </div>
      </Section>
      <Section title="Sessão">
        <div className={styles.row}>
          <span className="muted">Encerra a sessão neste navegador.</span>
          <Button size="sm" variant="danger" onClick={logout}>
            Sair
          </Button>
        </div>
      </Section>
    </div>
  );
}
