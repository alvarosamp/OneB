import { useId } from 'react';
import { useSearchParams } from 'react-router-dom';
import { PageHeader, TabPanel, Tabs } from '../components/ui';
import { MarketView } from '../components/assistant/MarketView';
import { AssetAnalysis, SetupReview } from '../components/assistant/AssetAnalysis';
import { AskQuestion } from '../components/assistant/AskQuestion';
import { AlertExplain } from '../components/assistant/AlertExplain';
import styles from './Assistente.module.css';

const MODES = [
  { value: 'mercado', label: 'Visão do mercado' },
  { value: 'ativo', label: 'Analisar ativo' },
  { value: 'setup', label: 'Revisar setup' },
  { value: 'perguntar', label: 'Perguntar' },
  { value: 'alerta', label: 'Explicar alerta' },
] as const;
type Mode = (typeof MODES)[number]['value'];

/**
 * Assistente único (antes: Mesa IA, Copiloto e Assistente IA).
 * Parâmetros: ?modo=, ?symbol= (ativo/setup), ?alerta= (id), ?q= (pergunta).
 */
export function Assistente() {
  const [params, setParams] = useSearchParams();
  const idBase = useId();
  const raw = params.get('modo');
  const mode: Mode = MODES.some((m) => m.value === raw) ? (raw as Mode) : 'mercado';
  const symbol = params.get('symbol') ?? undefined;
  const alertId = params.get('alerta') ? Number(params.get('alerta')) : null;
  const q = params.get('q') ?? undefined;

  function go(next: Mode, extra: Record<string, string> = {}) {
    const p = new URLSearchParams({ modo: next, ...extra });
    setParams(p, { replace: next === mode });
  }

  return (
    <div className={styles.page}>
      <PageHeader title="Assistente" description="Explica o mercado e os seus ativos a partir dos dados coletados pelo OneB. Não recomenda compra ou venda." />
      <Tabs items={[...MODES]} value={mode} onChange={(m) => go(m)} label="Modo do Assistente" variant="segmented" idBase={idBase} />
      <TabPanel idBase={idBase} value={mode}>
        {mode === 'mercado' && <MarketView onAnalyze={(s) => go('ativo', { symbol: s })} />}
        {mode === 'ativo' && <AssetAnalysis key={symbol ?? ''} initialSymbol={symbol} />}
        {mode === 'setup' && <SetupReview initialSymbol={symbol} />}
        {mode === 'perguntar' && <AskQuestion key={q ?? ''} initialQuestion={q} />}
        {mode === 'alerta' && <AlertExplain alertId={alertId} onSelect={(id) => go('alerta', { alerta: String(id) })} onAsk={(question) => go('perguntar', { q: question })} />}
      </TabPanel>
    </div>
  );
}
