import { TabbedPage } from '../components/terminal/TabbedPage';
import { VisaoGeral } from './analise/VisaoGeral';
import { Regime } from './analise/Regime';
import { Tecnica } from './analise/Tecnica';
import { Macro } from './analise/Macro';
import { Tendencia } from './analise/Tendencia';
import { Ativo } from './analise/Ativo';
import { Horarios } from './analise/Horarios';
import { Confianca } from './analise/Confianca';
import { Conta } from './analise/Conta';
import { Sinal } from './analise/Sinal';

type AnaliseTab = 'visao-geral' | 'ativo' | 'conta' | 'sinal' | 'horarios' | 'confianca' | 'tendencia' | 'regime' | 'tecnica' | 'macro';

/** Análise: Visão geral, Ativo (risco e custo medidos), Quanto operar (lote pela conta), Horários (mapa de calor), Tendência, Regime, Técnica e Macro. */
export function Analise() {
  return (
    <TabbedPage<AnaliseTab>
      title="Análise"
      fallback="visao-geral"
      tabs={[
        { value: 'visao-geral', label: 'Visão geral', render: () => <VisaoGeral /> },
        { value: 'ativo', label: 'Ativo', render: () => <Ativo /> },
        { value: 'conta', label: 'Quanto operar', render: () => <Conta /> },
        { value: 'sinal', label: 'Avaliar sinal', render: () => <Sinal /> },
        { value: 'horarios', label: 'Horários', render: () => <Horarios /> },
        { value: 'confianca', label: 'Por que confiar', render: () => <Confianca /> },
        { value: 'tendencia', label: 'Tendência', render: () => <Tendencia /> },
        { value: 'regime', label: 'Regime', render: () => <Regime /> },
        { value: 'tecnica', label: 'Técnica', render: () => <Tecnica /> },
        { value: 'macro', label: 'Macro', render: () => <Macro /> },
      ]}
    />
  );
}
