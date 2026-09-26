import { useState, type FormEvent } from 'react';
import { useSearchParams } from 'react-router-dom';
import { useApi } from '../../hooks/useApi';
import { ConceptLink } from '../../components/terminal/ConceptLink';
import { DataAge } from '../../components/terminal/DataAge';
import { AsyncContent, Button, EmptyState, Input, Section, SkeletonLines, Table } from '../../components/ui';
import { MACRO_LABEL, REGIME_LABEL } from '../../lib/marketRead';
import { formatNumber, formatSigned } from '../../lib/format';
import { ptBR } from '../../lib/text';
import { normalizeSymbol, SYMBOL_RE } from '../../lib/watchlist';
import type { RegimeReport } from '../../types';
import { crossAssetColumns } from './crossAsset';
import styles from './Analise.module.css';

const FACTOR_LABEL: Record<string, string> = { trend: 'Tendência', momentum: 'Momentum', forca_da_tendencia: 'Força da tendência', estrutura: 'Estrutura' };
const QUICK = ['NASDAQ', 'SP500', 'GOLD', 'QQQ', 'NVDA'];

/** Análise › Regime: regime local do ativo (determinístico) + contexto macro. */
export function Regime() {
  const [params, setParams] = useSearchParams();
  const symbol = normalizeSymbol(params.get('symbol') ?? 'NASDAQ');
  const [input, setInput] = useState('');
  const report = useApi<RegimeReport>(`/api/regime/${encodeURIComponent(symbol)}`);

  function go(s: string) {
    const p = new URLSearchParams(params);
    p.set('symbol', s);
    setParams(p, { replace: true });
  }

  function submit(e: FormEvent) {
    e.preventDefault();
    const s = normalizeSymbol(input);
    if (SYMBOL_RE.test(s)) {
      go(s);
      setInput('');
    }
  }

  return (
    <div className={styles.stack}>
      <div className={styles.toolbar}>
        <form onSubmit={submit} className={styles.inline}>
          <Input label="Ativo ou instrumento" value={input} onChange={(e) => setInput(e.target.value.toUpperCase())} placeholder="NASDAQ, GOLD, AAPL" className={styles.w220} />
          <Button type="submit">Ver regime</Button>
        </form>
        <div className={styles.inline}>
          {QUICK.map((q) => (
            <Button key={q} size="sm" variant={q === symbol ? 'secondary' : 'ghost'} aria-pressed={q === symbol} onClick={() => go(q)}>
              {q}
            </Button>
          ))}
        </div>
      </div>
      <p className={styles.note}>
        Regime calculado por regras fixas no gráfico diário (EMA 20/50, RSI, ADX e máximas/mínimas de 20 candles). <ConceptLink concept="regime" />
      </p>

      <AsyncContent
        state={report}
        loading={<SkeletonLines lines={8} />}
        empty={<EmptyState title={`Sem histórico suficiente para ${symbol}`} description={report.error ?? 'O regime precisa de pelo menos 55 candles diários.'} />}
        errorTitle="Não foi possível calcular o regime"
      >
        {(r) => (
          <>
            <Section title={`Regime de ${r.symbol}`} meta={report.lastUpdated ? <DataAge at={report.lastUpdated} /> : null}>
              {r.local_regime ? (
                <div className={styles.regime}>
                  <div className={styles.regimeHead}>
                    <span className={styles.regimeLabel}>{REGIME_LABEL[r.local_regime.label] ?? r.local_regime.label}</span>
                    <span className="num muted">score {formatSigned(r.local_regime.score, 1)} (de −100 a 100)</span>
                    <span className="muted">Contexto macro: {MACRO_LABEL[r.macro_context] ?? r.macro_context}</span>
                  </div>
                  <Table
                    caption="Fatores do regime"
                    columns={[
                      { key: 'f', header: 'Fator', render: (f) => FACTOR_LABEL[f.name] ?? ptBR(f.name) },
                      { key: 'i', header: 'Impacto', align: 'right', render: (f) => (f.impact === null ? <span className="muted">multiplicador</span> : <span className={f.impact > 0 ? 'num up' : f.impact < 0 ? 'num down' : 'num'}>{formatSigned(f.impact, 1)}</span>) },
                      { key: 'e', header: 'Evidência', wrap: true, render: (f) => ptBR(f.evidence) },
                    ]}
                    rows={r.local_regime.factors}
                    rowKey={(f) => f.name}
                    dense
                  />
                </div>
              ) : (
                <EmptyState title="Sem regime local" description="Histórico insuficiente para este ativo; o contexto macro abaixo continua válido." />
              )}
            </Section>
            <Section title="Contexto cross-asset" meta="correlação dos retornos diários nos últimos 30 dias">
              {r.cross_asset_relevance.length ? (
                <Table caption="Relevância cross-asset" columns={crossAssetColumns()} rows={r.cross_asset_relevance} rowKey={(c) => c.key} initialSort={{ key: 'corr', dir: 'desc' }} dense />
              ) : (
                <p className="muted">Sem histórico suficiente para correlações.</p>
              )}
              <p className={styles.note}>
                “Confirma” quando o instrumento se moveu hoje na direção que a correlação sugere; “diverge” quando se moveu ao contrário. Correlação de {formatNumber(0.5, 1)} ou mais é considerada alta.
              </p>
            </Section>
          </>
        )}
      </AsyncContent>
    </div>
  );
}
