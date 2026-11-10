import { TabbedPage } from '../components/terminal/TabbedPage';
import { VisaoGeral } from './analise/VisaoGeral';
import { Regime } from './analise/Regime';
import { Tecnica } from './analise/Tecnica';
import { Macro } from './analise/Macro';

type AnaliseTab = 'visao-geral' | 'regime' | 'tecnica' | 'macro';

/** Análise: Visão geral (resumo diário + matinal + semanal), Regime, Técnica e Macro. */
export function Analise() {
  return (
    <TabbedPage<AnaliseTab>
      title="Análise"
      fallback="visao-geral"
      tabs={[
        { value: 'visao-geral', label: 'Visão geral', render: () => <VisaoGeral /> },
        { value: 'regime', label: 'Regime', render: () => <Regime /> },
        { value: 'tecnica', label: 'Técnica', render: () => <Tecnica /> },
        { value: 'macro', label: 'Macro', render: () => <Macro /> },
      ]}
    />
  );
}
