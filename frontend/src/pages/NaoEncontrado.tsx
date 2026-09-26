import { Link } from 'react-router-dom';
import { CenteredMessage } from '../components/AuthLayout';
import { buttonClass } from '../components/ui/buttonClass';

export function NaoEncontrado() {
  return (
    <CenteredMessage title="Página não encontrada" description="Este endereço não existe ou mudou de lugar. Use a busca (Ctrl+K) ou volte para o Hoje.">
      <Link className={buttonClass({ variant: 'primary' })} to="/ferramenta">
        Ir para o Hoje
      </Link>
    </CenteredMessage>
  );
}
