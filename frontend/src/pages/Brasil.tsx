import { TabbedPage } from '../components/terminal/TabbedPage';
import { Comecar } from './brasil/Comecar';
import { Simulador } from './brasil/Simulador';
import { Produtos } from './brasil/Produtos';
import { Bolsa } from './brasil/Bolsa';
import { Eventos } from './brasil/Eventos';
import { AulasBrasil } from './brasil/AulasBrasil';

export type BrasilTab = 'comecar' | 'simulador' | 'produtos' | 'bolsa' | 'eventos' | 'aulas';

/** Brasil › Investir: educação e simulação para quem quer começar a investir. Não é corretora. */
export function Brasil() {
  return (
    <TabbedPage<BrasilTab>
      title="Investir no Brasil"
      description="Todo mundo pode investir. Aqui você entende as opções, simula o seu caso e vê por que cada parte faz sentido. Não somos corretora e não vendemos produto."
      fallback="comecar"
      tabs={[
        { value: 'comecar', label: 'Começar', render: () => <Comecar /> },
        { value: 'simulador', label: 'Simulador', render: () => <Simulador /> },
        { value: 'produtos', label: 'Onde investir', render: () => <Produtos /> },
        { value: 'bolsa', label: 'Bolsa (B3)', render: () => <Bolsa /> },
        { value: 'eventos', label: 'Eventos', render: () => <Eventos /> },
        { value: 'aulas', label: 'Aulas', render: () => <AulasBrasil /> },
      ]}
    />
  );
}
