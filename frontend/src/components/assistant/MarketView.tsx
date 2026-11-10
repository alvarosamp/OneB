import { useMemo, useState } from 'react';
import { AlertTriangle, Info, RotateCw } from 'lucide-react';
import { api } from '../../api/client';
import { useApi } from '../../hooks/useApi';
import { useAction } from '../../hooks/useAction';
import { useToast } from '../../context/ToastContext';
import { fromBackendAction, STATE_LABEL, type DecisionState } from '../../lib/decisionState';
import { formatDate, formatPrice, formatSignedPct } from '../../lib/format';
import { ptBR } from '../../lib/text';
import type { DecisionDesk, MarketDivergence, RecommendationDecision, ReliabilityScoreboard } from '../../types';
import { AsyncContent, Button, EmptyState, ICON, Section, SkeletonLines, Table, type Column } from '../ui';
import { DecisionBadge } from '../terminal/DecisionBadge';
import { DataAge } from '../terminal/DataAge';
import { ReliabilityChart } from '../ReliabilityChart';
import { AnswerCard } from './AnswerCard';
import styles from './Assistant.module.css';

type Row = DecisionDesk['recommendations'][number];

const ORDER: Record<DecisionState, number> = { formacao: 0, observar: 1, 'sem-setup': 2 };

/** Modo "Visão do mercado": mesa de decisão (antiga Mesa IA) em formato de resposta. */
export function MarketView({ onAnalyze }: { onAnalyze: (symbol: string) => void }) {
  const desk = useApi<DecisionDesk>('/api/decision-desk/recommendations', { isEmpty: (d) => d.recommendations.length === 0 });
  const divergence = useApi<MarketDivergence>('/api/decision-desk/market-divergence');
  const toast = useToast();
  const record = useAction(() => api.get<DecisionDesk>('/api/decision-desk/recommendations?record=true'));
  const [showHistory, setShowHistory] = useState(false);

  async function registerRead() {
    const result = await record.run();
    if (result) {
      desk.mutate(result);
      toast(`Leitura registrada (${result.recorded} ativos)`, 'success');
    } else {
      toast('Não foi possível registrar a leitura', 'error');
    }
  }

  const rows = useMemo(
    () =>
      (desk.data?.recommendations ?? [])
        .map((r) => ({ ...r, read: fromBackendAction(r.action) }))
        .sort((a, b) => ORDER[a.read.state] - ORDER[b.read.state] || b.confidence - a.confidence),
    [desk.data],
  );
  const counts = rows.reduce<Record<DecisionState, number>>(
    (acc, r) => ((acc[r.read.state] += 1), acc),
    { formacao: 0, observar: 0, 'sem-setup': 0 },
  );

  const columns: Column<Row & { read: ReturnType<typeof fromBackendAction> }>[] = [
    { key: 'ativo', header: 'Ativo', render: (r) => <strong>{r.symbol}</strong>, sortValue: (r) => r.symbol },
    { key: 'estado', header: 'Estado', render: (r) => <DecisionBadge state={r.read.state} bias={r.read.bias} size="sm" />, sortValue: (r) => ORDER[r.read.state] },
    { key: 'preco', header: 'Preço', align: 'right', render: (r) => <span className="num">{formatPrice(r.price, r.symbol)}</span> },
    { key: 'conf', header: 'Confiança', align: 'right', render: (r) => <span className="num">{r.confidence}%</span>, sortValue: (r) => r.confidence },
    { key: 'motivo', header: 'Por quê', wrap: true, render: (r) => <span className="muted">{ptBR(firstClause(r.fair_reason))}</span> },
  ];

  return (
    <div className={styles.mode}>
      {divergence.data?.available && divergence.data.note && (
        <p className={[styles.banner, divergence.data.divergent ? '' : styles.info].join(' ')}>
          {divergence.data.divergent ? <AlertTriangle {...ICON} aria-hidden="true" /> : <Info {...ICON} aria-hidden="true" />}
          <span>
            {ptBR(divergence.data.note)}
            {divergence.data.benchmark_symbol && divergence.data.benchmark_move_pct !== null && (
              <> ({divergence.data.benchmark_symbol} {formatSignedPct(divergence.data.benchmark_move_pct)})</>
            )}
          </span>
        </p>
      )}
      {desk.data?.circuit_breaker.tripped && (
        <p className={styles.banner}>
          <AlertTriangle {...ICON} aria-hidden="true" />
          Freio de portfólio ativo: acerto recente de {desk.data.circuit_breaker.win_rate_pct}% em {desk.data.circuit_breaker.samples} leituras. Setups de alta foram rebaixados para observação.
        </p>
      )}
      {desk.data?.decision_health.tripped && (
        <p className={[styles.banner, styles.info].join(' ')}>
          <Info {...ICON} aria-hidden="true" />
          {ptBR(desk.data.decision_health.reason)} Os sinais seguem visíveis apenas para observação.
        </p>
      )}

      <AsyncContent
        state={desk}
        loading={<SkeletonLines lines={8} />}
        empty={<EmptyState title="Sem ativos para avaliar" description="Adicione ativos à watchlist para a leitura do mercado considerar." />}
        errorTitle="Não foi possível montar a visão do mercado"
      >
        {(data) => (
          <AnswerCard
            subject="Mercado agora"
            subtitle={
              <>
                Referência {data.benchmark}, <DataAge at={data.generated_at} prefix="gerado" />
              </>
            }
            confidence={data.decision_health.allowed ? 'media' : 'baixa'}
            confidenceDetail={data.calibration_source === 'walk_forward_calibrated' ? 'calibração walk-forward' : 'calibração padrão, sem validação recente'}
            conclusion={ptBR(data.headline)}
            evidences={[
              `${counts.formacao} ativo(s) com ${STATE_LABEL.formacao.toLowerCase()}, ${counts.observar} para observar e ${counts['sem-setup']} sem setup.`,
              ...(data.macro_context.dxy !== null ? [`Dólar (DXY) ${formatSignedPct(data.macro_context.dxy_change_20d_pct)} em 20 dias.`] : []),
              ...(data.macro_context.oil !== null ? [`Petróleo WTI ${formatSignedPct(data.macro_context.oil_change_20d_pct)} em 20 dias.`] : []),
            ]}
            actions={
              <Button size="sm" icon={<RotateCw {...ICON} />} loading={record.status === 'running'} onClick={registerRead}>
                Registrar leitura
              </Button>
            }
          >
            <Table
              caption="Leitura por ativo"
              columns={columns}
              rows={rows}
              rowKey={(r) => r.symbol}
              onRowClick={(r) => onAnalyze(r.symbol)}
              rowLabel={(r) => `Analisar ${r.symbol}`}
              dense
              stickyFirstColumn
            />
          </AnswerCard>
        )}
      </AsyncContent>

      <Section
        title="Histórico e confiabilidade"
        divided
        actions={
          <Button size="sm" variant="ghost" aria-expanded={showHistory} onClick={() => setShowHistory((v) => !v)}>
            {showHistory ? 'Ocultar' : 'Mostrar'}
          </Button>
        }
      >
        <p className={styles.hint}>Compara a confiança declarada em leituras registradas com o resultado real, checado 5 pregões depois.</p>
        {showHistory && <History />}
      </Section>
    </div>
  );
}

function History() {
  const scoreboard = useApi<ReliabilityScoreboard>('/api/decision-desk/scoreboard', { isEmpty: (d) => d.total_samples === 0 });
  const history = useApi<RecommendationDecision[]>('/api/decision-desk/history?limit=20');
  const columns: Column<RecommendationDecision>[] = [
    { key: 'data', header: 'Data', render: (r) => <span className="num">{formatDate(r.created_at)}</span>, sortValue: (r) => r.created_at },
    { key: 'ativo', header: 'Ativo', render: (r) => <strong>{r.symbol}</strong> },
    { key: 'estado', header: 'Estado', render: (r) => <DecisionBadge {...fromBackendAction(r.action)} size="sm" /> },
    { key: 'conf', header: 'Confiança', align: 'right', render: (r) => <span className="num">{r.confidence}%</span> },
    { key: 'r1', header: '1 dia', align: 'right', render: (r) => <Ret v={r.outcome_return_1d_pct} /> },
    { key: 'r5', header: '5 dias', align: 'right', render: (r) => <Ret v={r.outcome_return_5d_pct} /> },
    { key: 'r20', header: '20 dias', align: 'right', render: (r) => <Ret v={r.outcome_return_20d_pct} /> },
  ];
  return (
    <div className={styles.subsection}>
      <AsyncContent state={scoreboard} empty={<EmptyState title="Ainda sem leituras avaliadas" description="Registre leituras por alguns dias; o placar aparece depois de 5 pregões." />}>
        {(data) => <ReliabilityChart data={data} />}
      </AsyncContent>
      <AsyncContent state={history} empty={<EmptyState title="Nenhuma leitura registrada" description="Use “Registrar leitura” para começar o histórico." />}>
        {(rows) => <Table caption="Leituras registradas" columns={columns} rows={rows} rowKey={(r) => r.id} dense />}
      </AsyncContent>
    </div>
  );
}

function Ret({ v }: { v: number | null }) {
  if (v === null) return <span className="muted">pendente</span>;
  return <span className={v > 0 ? 'num up' : v < 0 ? 'num down' : 'num'}>{formatSignedPct(v)}</span>;
}

function firstClause(text: string) {
  const s = text.split(/(?<=\.)\s/)[0] ?? text;
  return s.length > 140 ? `${s.slice(0, 137)}…` : s;
}
