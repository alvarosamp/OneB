import { useEffect, useState, type FormEvent } from 'react';
import { Link } from 'react-router-dom';
import { LineChart } from 'lucide-react';
import { api } from '../../api/client';
import { useAction } from '../../hooks/useAction';
import { readCopilot, dataConfidence, voteLabel } from '../../lib/assistant';
import { formatCurrency, formatNumber, isNum } from '../../lib/format';
import { ptBR } from '../../lib/text';
import type { CopilotAnalysis, MovementExplanation } from '../../types';
import { Badge, Button, ErrorState, ICON, Input, SkeletonLines, Textarea } from '../ui';
import { buttonClass } from '../ui/buttonClass';
import { AnswerCard } from './AnswerCard';
import { createAlertHref } from '../../lib/watchlist';
import styles from './Assistant.module.css';

interface DataQuality {
  confidence: string;
  freshest_age_minutes: number | null;
  issues: string[];
}

interface Result {
  copilot: CopilotAnalysis;
  explain: MovementExplanation | null;
  quality: DataQuality | null;
}

async function analyze(symbol: string, question: string, capital?: number, risk?: number): Promise<Result> {
  const clean = symbol.trim().toUpperCase();
  const [copilot, explain, quality] = await Promise.all([
    api.post<CopilotAnalysis>('/api/copilot/analyze', {
      symbol: clean,
      question,
      ...(capital ? { capital_usd: capital } : {}),
      ...(risk ? { risk_budget_pct: risk } : {}),
    }),
    api.get<MovementExplanation>(`/api/intelligence/explain/${encodeURIComponent(clean)}`).catch(() => null),
    api.get<DataQuality>(`/api/intelligence/data-quality/${encodeURIComponent(clean)}`).catch(() => null),
  ]);
  return { copilot, explain, quality };
}

const SYMBOL_RE = /^[A-Z0-9.^=-]{1,15}$/;

/** Modo "Analisar ativo" (antigo Copiloto, leitura geral). */
export function AssetAnalysis({ initialSymbol }: { initialSymbol?: string }) {
  const [symbol, setSymbol] = useState(initialSymbol ?? '');
  const action = useAction(analyze);
  const [invalid, setInvalid] = useState<string | null>(null);

  useEffect(() => {
    if (initialSymbol && SYMBOL_RE.test(initialSymbol.toUpperCase())) {
      setSymbol(initialSymbol.toUpperCase());
      void action.run(initialSymbol, '');
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [initialSymbol]);

  function submit(e: FormEvent) {
    e.preventDefault();
    const s = symbol.trim().toUpperCase();
    if (!SYMBOL_RE.test(s)) {
      setInvalid('Use um símbolo válido, por exemplo NVDA, QQQ ou GC=F.');
      return;
    }
    setInvalid(null);
    void action.run(s, '');
  }

  return (
    <div className={styles.mode}>
      <form className={styles.form} onSubmit={submit}>
        <Input label="Ativo" className={styles.symbol} value={symbol} onChange={(e) => setSymbol(e.target.value.toUpperCase())} placeholder="NVDA" error={invalid} autoComplete="off" spellCheck={false} />
        <Button type="submit" variant="primary" loading={action.status === 'running'}>
          Analisar ativo
        </Button>
      </form>
      {action.status === 'idle' && <p className={styles.hint}>Combina técnico, notícias, macro, risco e seu histórico para explicar o momento do ativo.</p>}
      {action.status === 'running' && <SkeletonLines lines={6} label="Analisando" />}
      {action.status === 'error' && <ErrorState title="Não foi possível analisar o ativo" error={action.error} onRetry={() => void action.run(symbol, '')} />}
      {action.status === 'done' && action.data && <CopilotAnswer result={action.data} />}
    </div>
  );
}

/** Modo "Revisar setup": o plano do usuário passa pelo mesmo motor, com capital e risco. */
export function SetupReview({ initialSymbol }: { initialSymbol?: string }) {
  const [symbol, setSymbol] = useState(initialSymbol ?? '');
  const [capital, setCapital] = useState('20000');
  const [risk, setRisk] = useState('1');
  const [thesis, setThesis] = useState('');
  const action = useAction(analyze);
  const [invalid, setInvalid] = useState<string | null>(null);

  function submit(e: FormEvent) {
    e.preventDefault();
    const s = symbol.trim().toUpperCase();
    if (!SYMBOL_RE.test(s)) {
      setInvalid('Informe o símbolo do setup.');
      return;
    }
    setInvalid(null);
    void action.run(s, thesis, Number(capital) || undefined, Number(risk) || undefined);
  }

  return (
    <div className={styles.mode}>
      <form className={styles.form} onSubmit={submit}>
        <Input label="Ativo" className={styles.symbol} value={symbol} onChange={(e) => setSymbol(e.target.value.toUpperCase())} placeholder="NVDA" error={invalid} autoComplete="off" />
        <Input label="Capital (US$)" className={styles.number} type="number" min="1" step="1" value={capital} onChange={(e) => setCapital(e.target.value)} />
        <Input label="Risco máximo (%)" className={styles.number} type="number" min="0.1" max="10" step="0.1" value={risk} onChange={(e) => setRisk(e.target.value)} />
        <Textarea
          label="Sua tese e gatilho"
          className={styles.grow}
          rows={2}
          value={thesis}
          onChange={(e) => setThesis(e.target.value)}
          placeholder="Ex.: rompimento da máxima de 20 dias com volume acima da média; invalida se fechar abaixo da EMA 20."
        />
        <Button type="submit" variant="primary" loading={action.status === 'running'}>
          Revisar setup
        </Button>
      </form>
      {action.status === 'running' && <SkeletonLines lines={6} label="Revisando" />}
      {action.status === 'error' && <ErrorState title="Não foi possível revisar o setup" error={action.error} />}
      {action.status === 'done' && action.data && <CopilotAnswer result={action.data} showPlan />}
    </div>
  );
}

function CopilotAnswer({ result, showPlan }: { result: Result; showPlan?: boolean }) {
  const { copilot: a, explain, quality } = result;
  const read = readCopilot(a);
  const plan = a.trade_plan;
  const conf = dataConfidence(quality?.confidence);
  const evidences = [...a.why.slice(0, 2), ...a.votes.slice(0, 3).map((v) => `${ptBR(v.name)}: ${v.summary}`)].map(ptBR).slice(0, 5);

  return (
    <AnswerCard
      subject={a.symbol}
      subtitle={isNum(a.entry_price) ? `Último preço ${formatCurrency(a.entry_price)}` : undefined}
      state={read.state}
      bias={read.bias}
      confidence={conf}
      confidenceDetail={
        quality
          ? [isNum(quality.freshest_age_minutes) ? `cotação de ${formatNumber(quality.freshest_age_minutes, 0)} min atrás` : null, quality.issues[0] ? ptBR(quality.issues[0]) : null].filter(Boolean).join('; ')
          : 'qualidade da fonte não informada'
      }
      conclusion={ptBR(explain?.hypotheses[0] ?? a.why[0] ?? plan.reason)}
      evidences={evidences}
      counterpoints={a.contrary_view.slice(0, 4).map(ptBR)}
      actions={
        <>
          <Link to={`/ativo/${encodeURIComponent(a.symbol)}`} className={buttonClass({ size: 'sm' })}>
            <LineChart {...ICON} aria-hidden="true" />
            Ver gráfico
          </Link>
          <Link to={createAlertHref(a.symbol)} className={buttonClass({ size: 'sm', variant: 'ghost' })}>
            Criar alerta
          </Link>
        </>
      }
      details={
        <div className={styles.detailGrid}>
          <div className={styles.subsection}>
            <h3 className={styles.hint}>Consenso dos agentes: {a.confidence}%</h3>
            {a.votes.map((v) => (
              <div key={v.name} className={styles.vote}>
                <header>
                  <strong>{ptBR(v.name)}</strong>
                  <Badge tone={voteLabel(v.vote) === 'Construtivo' ? 'info' : voteLabel(v.vote) === 'Desfavorável' ? 'warning' : 'neutral'}>{voteLabel(v.vote)}</Badge>
                  <span className="muted num">{v.confidence}%</span>
                </header>
                <ul>
                  {v.evidence.map((e) => (
                    <li key={e}>{ptBR(e)}</li>
                  ))}
                </ul>
              </div>
            ))}
          </div>
          {explain && explain.facts.length > 0 && (
            <div className={styles.vote}>
              <strong>Fatos do último snapshot</strong>
              <ul>
                {explain.facts.map((f) => (
                  <li key={f}>{ptBR(f)}</li>
                ))}
              </ul>
            </div>
          )}
          {a.simulation.available && (
            <div className={styles.vote}>
              <strong>Simulação histórica</strong>
              <p className="muted">{ptBR(a.simulation.summary)}</p>
            </div>
          )}
          {a.patterns.length > 0 && (
            <div className={styles.vote}>
              <strong>Padrões na watchlist</strong>
              <ul>
                {a.patterns.map((p) => (
                  <li key={p}>{ptBR(p)}</li>
                ))}
              </ul>
            </div>
          )}
        </div>
      }
    >
      {showPlan && <PlanBlock plan={plan} riskPlan={a.risk_plan} />}
    </AnswerCard>
  );
}

function PlanBlock({ plan, riskPlan }: { plan: CopilotAnalysis['trade_plan']; riskPlan: string[] }) {
  if (!plan.available) return <p className={styles.hint}>{ptBR(plan.reason)}</p>;
  const cell = (label: string, value: string) => (
    <div>
      <span className={styles.planLabel}>{label}</span>
      <div className="num">{value}</div>
    </div>
  );
  return (
    <div className={styles.subsection}>
      <h3 className={styles.hint}>Plano condicional (diário, {plan.holding_window ?? 'janela não informada'})</h3>
      <div className={styles.planGrid}>
        {cell('Entrada de referência', formatCurrency(plan.entry_price))}
        {cell('Invalidação (stop)', formatCurrency(plan.stop_price))}
        {cell('Alvo 1 (2R)', formatCurrency(plan.target_1_price))}
        {cell('Alvo 2 (3R)', formatCurrency(plan.target_2_price))}
        {cell('Tamanho máximo', isNum(plan.suggested_shares) ? `${plan.suggested_shares} ações` : '—')}
        {cell('Risco planejado', formatCurrency(plan.risk_amount_usd))}
      </div>
      <ul className={styles.planList}>
        {[plan.invalidation, ...riskPlan].filter(Boolean).map((r) => (
          <li key={r}>{ptBR(r as string)}</li>
        ))}
      </ul>
    </div>
  );
}
