import { useState } from 'react';
import { ArrowUpRight, FileDown, RotateCw } from 'lucide-react';
import { api, fetchBlob } from '../../api/client';
import { useApi } from '../../hooks/useApi';
import { useAction } from '../../hooks/useAction';
import { useToast } from '../../context/ToastContext';
import { DataAge } from '../../components/terminal/DataAge';
import { AsyncContent, Badge, Button, ChangeText, EmptyState, ICON, ICON_SM, Section, SkeletonLines, Table, type Column } from '../../components/ui';
import { formatDateTime, formatNumber, formatPrice, isNum } from '../../lib/format';
import { ptBR } from '../../lib/text';
import type { DailyMarketAsset, DailyMarketSummary, DataQualityOverview, MorningReport, SignalQuality, SymbolLevels, WeeklyBrief } from '../../types';
import styles from './Analise.module.css';

/** Análise › Visão geral: resumo diário, análise matinal, resumo semanal e confiabilidade dos dados. */
export function VisaoGeral() {
  return (
    <div className={styles.stack}>
      <DailySummary />
      <MorningReportBlock />
      <WeeklyBriefBlock />
      <Reliability />
    </div>
  );
}

function assetColumns(): Column<DailyMarketAsset>[] {
  return [
    { key: 'ativo', header: 'Ativo', sortValue: (a) => a.symbol, render: (a) => <strong>{a.symbol}</strong> },
    { key: 'preco', header: 'Preço', align: 'right', render: (a) => <span className="num">{formatPrice(a.price, a.symbol)}</span> },
    { key: 'dia', header: 'Dia', align: 'right', sortValue: (a) => a.change_pct, render: (a) => <ChangeText value={a.change_pct} /> },
    { key: 'tendencia', header: 'Tendência', render: (a) => ptBR(a.trend) },
    { key: 'rsi', header: 'RSI', align: 'right', sortValue: (a) => a.rsi, render: (a) => <span className="num">{formatNumber(a.rsi, 1)}</span> },
    { key: 'atr', header: 'ATR', align: 'right', render: (a) => <span className="num">{isNum(a.atr_pct) ? `${formatNumber(a.atr_pct, 2)}%` : '—'}</span> },
    { key: 'vol', header: 'Volume rel.', align: 'right', render: (a) => <span className="num">{isNum(a.volume_ratio) ? `${formatNumber(a.volume_ratio, 2)}x` : '—'}</span> },
    { key: 'score', header: 'Score técnico', align: 'right', sortValue: (a) => a.score, render: (a) => <span className="num">{a.score}</span> },
    { key: 'notas', header: 'Notas', wrap: true, render: (a) => <span className="muted">{a.notes.slice(0, 2).map((n) => ptBR(n)).join(' ')}</span> },
  ];
}

function DailySummary() {
  const s = useApi<DailyMarketSummary>('/api/reports/daily-summary', { pollMs: 15 * 60_000 });
  const cols = assetColumns();
  return (
    <AsyncContent state={s} loading={<SkeletonLines lines={8} />} empty={<EmptyState title="Resumo diário indisponível" description="Adicione ativos à watchlist para gerar o resumo." />} errorTitle="Não foi possível gerar o resumo diário">
      {(d) => (
        <>
          <Section title="Resumo do dia" meta={<DataAge at={d.generated_at} prefix="gerado" />}>
            <div className={styles.headline}>
              <Badge tone={/defens|press|risco/i.test(d.market_tone) ? 'warning' : 'info'}>{ptBR(d.market_tone)}</Badge>
              <p className={styles.lead}>{ptBR(d.headline)}</p>
            </div>
            <div className={styles.two}>
              <div>
                <h3 className={styles.h3}>Principais leituras</h3>
                <ul className={styles.list}>
                  {d.key_takeaways.map((k) => (
                    <li key={k}>{ptBR(k)}</li>
                  ))}
                </ul>
              </div>
              <div>
                <h3 className={styles.h3}>Checklist do dia</h3>
                <ul className={styles.list}>
                  {d.action_plan.map((k) => (
                    <li key={k}>{ptBR(k)}</li>
                  ))}
                </ul>
              </div>
            </div>
          </Section>
          <Section title="Melhores leituras técnicas">
            {d.opportunities.length ? <Table caption="Melhores leituras técnicas" columns={cols} rows={d.opportunities} rowKey={(a) => a.symbol} dense stickyFirstColumn /> : <p className="muted">Nenhuma.</p>}
          </Section>
          <Section title="Pontos de atenção e volatilidade">
            {d.risks.length ? <Table caption="Pontos de atenção" columns={cols} rows={d.risks} rowKey={(a) => a.symbol} dense stickyFirstColumn /> : <p className="muted">Nenhum.</p>}
          </Section>
          <Section title="Aguardando confirmação">
            {d.watch.length ? <Table caption="Aguardando confirmação" columns={cols} rows={d.watch} rowKey={(a) => a.symbol} dense stickyFirstColumn /> : <p className="muted">Nenhum.</p>}
          </Section>
          <div className={styles.two}>
            <Section title="Eventos macro">
              {d.macro_events.length ? (
                <ul className={styles.feed}>
                  {d.macro_events.map((e) => (
                    <li key={`${e.name}-${e.date}`}>
                      <span>{e.name}</span>
                      <span className={styles.meta}>
                        {formatDateTime(e.date)}, {e.country}
                        {e.forecast ? `, proj. ${e.forecast}` : ''}
                        {e.previous ? `, ant. ${e.previous}` : ''}
                      </span>
                    </li>
                  ))}
                </ul>
              ) : (
                <p className="muted">Nenhum evento relevante.</p>
              )}
            </Section>
            <Section title="Notícias de maior impacto">
              {d.top_news.length ? (
                <ul className={styles.feed}>
                  {d.top_news.map((n) => (
                    <li key={n.url}>
                      <a href={n.url} target="_blank" rel="noreferrer">
                        {n.headline} <ArrowUpRight {...ICON_SM} className={styles.inlineIcon} aria-hidden="true" />
                      </a>
                      <span className={styles.meta}>
                        {n.source}, impacto {n.impact_score}
                      </span>
                    </li>
                  ))}
                </ul>
              ) : (
                <p className="muted">Nenhuma.</p>
              )}
            </Section>
          </div>
        </>
      )}
    </AsyncContent>
  );
}

function Levels({ levels }: { levels: SymbolLevels | null }) {
  if (!levels) return <span className="muted">sem níveis</span>;
  const p = levels.pivots;
  return (
    <span className="num muted">
      pivô {formatNumber(p.pivot)}, R1 {formatNumber(p.r1)}, R2 {formatNumber(p.r2)}, S1 {formatNumber(p.s1)}, S2 {formatNumber(p.s2)}
    </span>
  );
}

function MorningReportBlock() {
  const toast = useToast();
  const today = useApi<MorningReport>('/api/morning-report/today');
  const history = useApi<MorningReport[]>('/api/morning-report/history?limit=14');
  const [selectedId, setSelectedId] = useState<number | null>(null);
  const generate = useAction(() => api.post<MorningReport>('/api/morning-report/generate'));
  const [downloading, setDownloading] = useState(false);
  const report = (selectedId ? history.data?.find((r) => r.id === selectedId) : null) ?? today.data ?? history.data?.[0] ?? null;

  async function runGenerate() {
    const r = await generate.run();
    if (r) {
      today.mutate(r);
      history.mutate((prev) => [r, ...(prev ?? []).filter((x) => x.id !== r.id)]);
      setSelectedId(r.id);
      toast('Análise matinal gerada', 'success');
    } else toast('Não foi possível gerar a análise matinal', 'error');
  }

  async function pdf(id: number) {
    setDownloading(true);
    try {
      const blob = await fetchBlob(`/api/morning-report/${id}/pdf`);
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = `analise-matinal-${id}.pdf`;
      a.click();
      URL.revokeObjectURL(url);
      toast('PDF baixado', 'success');
    } catch (err) {
      toast(err instanceof Error ? `Não foi possível baixar o PDF: ${err.message}` : 'Não foi possível baixar o PDF', 'error');
    } finally {
      setDownloading(false);
    }
  }

  return (
    <Section
      title="Análise matinal"
      divided
      meta={report ? <DataAge at={report.generated_at} prefix="gerada" staleAfterMin={60 * 20} /> : null}
      actions={
        <>
          {report && (
            <Button size="sm" variant="ghost" icon={<FileDown {...ICON} />} loading={downloading} onClick={() => pdf(report.id)}>
              Baixar PDF
            </Button>
          )}
          <Button size="sm" icon={<RotateCw {...ICON} />} loading={generate.status === 'running'} onClick={runGenerate}>
            Gerar agora
          </Button>
        </>
      }
    >
      {today.status === 'loading' ? (
        <SkeletonLines lines={5} />
      ) : !report ? (
        <EmptyState title="Nenhuma análise matinal gerada ainda" description="Ela é gerada automaticamente antes da abertura em dias úteis. Use “Gerar agora” para criar a de hoje." />
      ) : (
        <div className={styles.morning}>
          {report.narrative && <p className={styles.narrative}>{ptBR(report.narrative)}</p>}
          <Table
            caption="Índices e commodities"
            columns={[
              { key: 'n', header: 'Índice', render: (i) => ptBR(i.name) },
              { key: 'p', header: 'Preço', align: 'right', render: (i) => <span className="num">{formatNumber(i.price)}</span> },
              { key: 'c', header: 'Variação', align: 'right', render: (i) => <ChangeText value={i.change_pct} /> },
              { key: 'l', header: 'Níveis', wrap: true, render: (i) => <Levels levels={i.levels} /> },
            ]}
            rows={report.data.indices}
            rowKey={(i) => i.key}
            dense
          />
          {report.data.watchlist.length > 0 && (
            <Table
              caption="Watchlist na análise matinal"
              columns={[
                { key: 's', header: 'Ativo', render: (r) => <strong>{r.symbol}</strong> },
                { key: 'p', header: 'Preço', align: 'right', render: (r) => <span className="num">{formatPrice(r.price, r.symbol)}</span> },
                { key: 'c', header: 'Variação', align: 'right', render: (r) => <ChangeText value={r.change_pct} /> },
                { key: 'l', header: 'Níveis', wrap: true, render: (r) => <Levels levels={r.levels} /> },
              ]}
              rows={report.data.watchlist}
              rowKey={(r) => r.symbol}
              dense
            />
          )}
          {(history.data?.length ?? 0) > 1 && (
            <div className={styles.historyRow}>
              <span className="muted">Histórico:</span>
              {history.data!.map((r) => (
                <Button key={r.id} size="sm" variant={r.id === report.id ? 'secondary' : 'ghost'} aria-pressed={r.id === report.id} onClick={() => setSelectedId(r.id)}>
                  {formatDateTime(r.generated_at)}
                </Button>
              ))}
            </div>
          )}
        </div>
      )}
    </Section>
  );
}

function WeeklyBriefBlock() {
  const brief = useApi<WeeklyBrief>('/api/intelligence/weekly-brief');
  return (
    <Section title="Resumo semanal" divided>
      <AsyncContent state={brief} loading={<SkeletonLines lines={4} />} empty={<p className="muted">Sem resumo semanal.</p>} errorTitle="Resumo semanal indisponível">
        {(b) => (
          <div className={styles.two}>
            <ul className={styles.list}>
              {b.summary.map((s) => (
                <li key={s}>{ptBR(s)}</li>
              ))}
            </ul>
            <div>
              {b.top_opportunities.length > 0 && (
                <p className={styles.meta}>
                  Mais atenção: {b.top_opportunities.map((o) => `${o.symbol} (${o.score})`).join(', ')}
                </p>
              )}
              {b.risks.length > 0 && <p className={styles.meta}>Atenção baixa ou risco: {b.risks.map((o) => `${o.symbol} (${o.score})`).join(', ')}</p>}
            </div>
          </div>
        )}
      </AsyncContent>
    </Section>
  );
}

const CONF: Record<string, { label: string; tone: 'info' | 'warning' | 'neutral' }> = {
  HIGH: { label: 'alta', tone: 'info' },
  MEDIUM: { label: 'média', tone: 'neutral' },
  LOW: { label: 'baixa', tone: 'warning' },
};

function Reliability() {
  const quality = useApi<DataQualityOverview>('/api/intelligence/data-quality', { isEmpty: (d) => d.rows.length === 0 });
  const signals = useApi<SignalQuality[]>('/api/intelligence/signal-quality');
  return (
    <Section title="Confiabilidade" divided meta="qualidade das cotações e ruído dos alertas">
      <div className={styles.two}>
        <AsyncContent state={quality} loading={<SkeletonLines lines={5} />} empty={<p className="muted">Sem dados de qualidade.</p>} errorTitle="Qualidade dos dados indisponível">
          {(q) => (
            <Table
              caption="Qualidade das cotações por ativo"
              columns={[
                { key: 's', header: 'Ativo', render: (r) => <strong>{r.symbol}</strong> },
                { key: 'c', header: 'Confiança', render: (r) => <Badge tone={CONF[r.confidence]?.tone}>{CONF[r.confidence]?.label ?? r.confidence}</Badge> },
                { key: 'd', header: 'Divergência', align: 'right', render: (r) => <span className="num">{formatNumber(r.max_divergence_pct, 2)}%</span> },
                { key: 'i', header: 'Observação', wrap: true, render: (r) => <span className="muted">{r.issues.map(ptBR).join(' ') || '—'}</span> },
              ]}
              rows={q.rows}
              rowKey={(r) => r.symbol}
              dense
            />
          )}
        </AsyncContent>
        <AsyncContent state={signals} loading={<SkeletonLines lines={5} />} empty={<p className="muted">Nenhum alerta para avaliar.</p>} errorTitle="Qualidade dos sinais indisponível">
          {(list) => (
            <Table
              caption="Ruído dos alertas por ativo"
              columns={[
                { key: 's', header: 'Ativo', render: (r) => <strong>{r.symbol}</strong> },
                { key: 'a', header: 'Alertas', align: 'right', render: (r) => <span className="num">{r.alerts}</span> },
                { key: 'n', header: 'Ruído', align: 'right', render: (r) => <span className="num">{r.noise_score}</span> },
                { key: 'x', header: 'Avaliação', wrap: true, render: (r) => <span className="muted">{ptBR(r.assessment)}</span> },
              ]}
              rows={list}
              rowKey={(r) => r.symbol}
              dense
            />
          )}
        </AsyncContent>
      </div>
    </Section>
  );
}
