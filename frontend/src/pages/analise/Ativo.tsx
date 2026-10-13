import { useMemo, useState, type ReactNode } from 'react';
import { useSearchParams } from 'react-router-dom';
import { CalendarClock, FlaskConical, Gauge, ShieldCheck } from 'lucide-react';
import { useApi } from '../../hooks/useApi';
import { ChartPanel, type PriceLevel } from '../../components/terminal/ChartPanel';
import { AsyncContent, Badge, ChipGroup, EmptyState, ICON, Input, Section, SkeletonLines } from '../../components/ui';
import type { BadgeTone } from '../../components/ui/Badge';
import { chartPath, TIMEFRAMES } from '../../lib/timeframes';
import { formatNumber, priceDigits } from '../../lib/format';
import { binOf } from '../../lib/heatmap';
import { riskPlan } from '../../lib/riskPlan';
import type { AssetBrief, ChartData } from '../../types';
import styles from './Ativo.module.css';

const ASSETS = [
  { value: 'NAS100', label: 'Nasdaq 100' },
  { value: 'SPX500', label: 'S&P 500' },
  { value: 'XAUUSD', label: 'Ouro' },
  { value: 'EURUSD', label: 'Euro/dólar' },
];

const STOP_MULTIPLES = [
  { value: '1', label: '1x ATR 1h' },
  { value: '1.5', label: '1,5x' },
  { value: '2', label: '2x' },
];

const EVIDENCE: Record<string, { label: string; tone: BadgeTone }> = {
  PASSED: { label: 'Aprovado', tone: 'positive' },
  FAILED: { label: 'Reprovado', tone: 'negative' },
  NOT_SIGNIFICANT: { label: 'Sem evidência', tone: 'neutral' },
  MIXED: { label: 'Misto', tone: 'warning' },
  DEGRADED: { label: 'Degradado', tone: 'warning' },
  PENDING: { label: 'Pendente', tone: 'neutral' },
};

const FIVE_DAYS = TIMEFRAMES.find((t) => t.id === '5D')!;

/** Análise › Ativo: o que o preço está fazendo, quanto ele costuma mexer, quanto custa e quanto operar. */
export function Ativo() {
  const [params, setParams] = useSearchParams();
  const key = ASSETS.some((a) => a.value === params.get('ativo')) ? params.get('ativo')! : 'NAS100';
  const brief = useApi<AssetBrief>(`/api/analysis/asset/${key}`, { pollMs: 120_000 });
  const pick = (v: string) => {
    const p = new URLSearchParams(params);
    p.set('ativo', v);
    setParams(p, { replace: true });
  };
  return (
    <div className={styles.page}>
      <ChipGroup label="Ativo" value={key} onChange={pick} items={ASSETS} />
      <AsyncContent state={brief} loading={<SkeletonLines lines={12} />} empty={<EmptyState title="Sem dados do ativo" />} errorTitle="Análise indisponível">
        {(b) => <Brief b={b} />}
      </AsyncContent>
    </div>
  );
}

function Brief({ b }: { b: AssetBrief }) {
  const m = b.market;
  const [mult, setMult] = useState('1.5');
  const stopPoints = m.atr_h1 ? m.atr_h1 * Number(mult) : null;
  const now = b.hours_ahead[0];
  const chart = useApi<ChartData>(chartPath(b.symbol, FIVE_DAYS), { isEmpty: (d) => d.close.length === 0 });
  const multLabel = mult.replace('.', ',');
  const levels = useMemo<PriceLevel[]>(() => {
    if (!m.price || !stopPoints) return [];
    return [
      { label: `Stop se comprar (${multLabel}x ATR 1h)`, value: m.price - stopPoints, colorVar: '--chart-level-stop' },
      { label: `Stop se vender (${multLabel}x ATR 1h)`, value: m.price + stopPoints, colorVar: '--chart-level-stop' },
    ];
  }, [m.price, stopPoints, multLabel]);
  const spreadOfAtr = b.broker.spread_points && m.atr_h1 ? b.broker.spread_points / m.atr_h1 : null;
  const dp = priceDigits(m.price);

  return (
    <div className={styles.brief}>
      <header className={styles.hero}>
        <div>
          <p className={styles.kicker}>
            {b.label} · {b.symbol} no gráfico · {b.broker.symbol} na corretora
          </p>
          {m.available && m.price != null ? (
            <p className={styles.price}>
              {formatNumber(m.price, dp)}
              {m.change_pct != null && (
                <span className={m.change_pct >= 0 ? styles.up : styles.down}>
                  {' '}
                  {m.change_pct >= 0 ? '+' : ''}
                  {formatNumber(m.change_pct, 2)}%
                </span>
              )}
            </p>
          ) : (
            <p className={styles.meta}>Preço indisponível agora.</p>
          )}
          {m.trend?.available && m.trend.agreement && <p className={styles.meta}>Tendência de 1, 3 e 12 meses: {m.trend.agreement} (descrição do preço, sem evidência de que continue).</p>}
        </div>
        <div className={styles.tiles}>
          <Tile icon={<Gauge {...ICON} />} label="Movimento típico do dia" value={m.atr_d1 != null ? `${formatNumber(m.atr_d1, dp)}` : '—'} sub="ATR de 14 dias, em preço" />
          <Tile icon={<Gauge {...ICON} />} label="Movimento típico da hora" value={m.atr_h1 != null ? `${formatNumber(m.atr_h1, dp)}` : '—'} sub="ATR de 14 horas, em preço" />
          <Tile
            icon={<ShieldCheck {...ICON} />}
            label={`Spread no ${b.broker.symbol}`}
            value={b.broker.spread_points != null ? `${formatNumber(b.broker.spread_points, 2)}` : 'sem medição'}
            sub={spreadOfAtr != null ? `${formatNumber(spreadOfAtr * 100, 1)}% do movimento de 1 hora` : 'mediana de dias úteis'}
          />
          <Tile
            icon={<CalendarClock {...ICON} />}
            label="Esta hora costuma ser"
            value={now?.ratio != null ? `${formatNumber(now.ratio, 1)}x` : 'fechado'}
            sub={now?.ratio != null ? 'a hora típica do ativo' : 'sem negociação nesta hora'}
          />
        </div>
      </header>

      {b.range_forecast && <Forecast f={b.range_forecast} dp={dp} />}

      <section className={styles.chart} aria-label="Gráfico de 5 dias com stops por ATR">
        <AsyncContent state={chart} loading={<SkeletonLines lines={8} />} empty={<EmptyState title="Sem gráfico agora" />}>
          {(d) => <ChartPanel data={d} timeframe={FIVE_DAYS} height={340} levels={levels} label={b.symbol} />}
        </AsyncContent>
        <p className={styles.meta}>
          As linhas mostram onde ficaria um stop de {multLabel}x o movimento típico da hora, para compra e para venda. É distância de risco, não previsão de direção.
        </p>
      </section>

      <div className={styles.columns}>
        <Section title="Próximas horas">
          <ol className={styles.hours}>
            {b.hours_ahead.map((h) => (
              <li key={h.starts_at} className={styles.hour}>
                <span className={styles.hourSwatch} style={{ background: h.ratio != null ? `var(--heat-vol-${binOf('ratio', h.ratio) + 1})` : undefined }} aria-hidden />
                <span className={styles.hourLabel}>
                  {new Date(h.starts_at).toLocaleString('pt-BR', { weekday: 'short', hour: '2-digit', timeZone: 'America/Sao_Paulo' })}h
                </span>
                <span className={styles.hourValue}>{h.ratio != null ? `${formatNumber(h.ratio, 1)}x` : 'fechado'}</span>
              </li>
            ))}
          </ol>
          <p className={styles.meta}>Movimento típico da hora contra a média do ativo, medido em 2 anos (horário de Brasília). Mapa completo na aba Horários.</p>
        </Section>

        <Section title="Eventos à frente">
          {b.events.length === 0 ? (
            <p className={styles.meta}>Nenhum evento de alto impacto nos próximos 3 dias.</p>
          ) : (
            <ul className={styles.events}>
              {b.events.map((e) => (
                <li key={e.event_name + e.event_date}>
                  <span className={styles.eventWhen}>{fmtWhen(e.event_date)}</span>
                  <span className={styles.eventName}>{e.event_name}</span>
                  {e.measured && e.post30 != null ? (
                    <Badge tone="warning">{formatNumber(e.post30, 1)}x nos 30 min</Badge>
                  ) : (
                    <Badge tone="neutral">alto impacto</Badge>
                  )}
                </li>
              ))}
            </ul>
          )}
          <p className={styles.meta}>Multiplicador = quanto o preço deste ativo costuma mexer nos 30 min após a divulgação, contra um dia sem evento (estudo de 2019 a 2026). Não indica direção.</p>
        </Section>
      </div>

      <Section title="Quanto operar" meta={<span className={styles.meta}>Calculadora — nada é enviado à corretora</span>}>
        <RiskCalculator b={b} stopPoints={stopPoints} mult={mult} setMult={setMult} dp={dp} />
      </Section>

      <Section title="O que já testamos neste ativo" meta={<FlaskConical {...ICON} aria-hidden />}>
        <ul className={styles.evidence}>
          {b.evidence.map((e) => (
            <li key={e.test}>
              <Badge tone={EVIDENCE[e.status]?.tone ?? 'neutral'}>{EVIDENCE[e.status]?.label ?? e.status}</Badge>
              <div>
                <p className={styles.evTitle}>{e.title}</p>
                <p className={styles.meta}>{e.detail}</p>
              </div>
            </li>
          ))}
        </ul>
        <p className={styles.meta}>{b.note}</p>
      </Section>
    </div>
  );
}

function Forecast({ f, dp }: { f: NonNullable<AssetBrief['range_forecast']>; dp: number }) {
  const day = new Date(`${f.target_date}T12:00:00`).toLocaleDateString('pt-BR', { weekday: 'long', day: '2-digit', month: '2-digit' });
  const vsAtr = f.expected_pct / f.atr14_pct - 1;
  return (
    <section className={styles.forecast} aria-label="Amplitude esperada do próximo pregão">
      <div>
        <p className={styles.kicker}>
          Quanto deve mexer no pregão de {day} <Badge tone="positive">Aprovado em teste</Badge>
        </p>
        <p className={styles.forecastValue}>
          {formatNumber(f.expected_price, dp)} <span>({formatNumber(f.expected_pct, 2)}%)</span>
        </p>
        <p className={styles.meta}>
          Em 8 de cada 10 dias, a distância entre máxima e mínima fica entre <strong>{formatNumber(f.low80_price, dp)}</strong> e{' '}
          <strong>{formatNumber(f.high80_price, dp)}</strong>.
          {f.event ? ` Inclui o efeito de ${f.event} nesse dia.` : ''}
        </p>
      </div>
      <ul className={styles.forecastFacts}>
        <li>
          {vsAtr >= 0 ? `${formatNumber(vsAtr * 100, 0)}% acima` : `${formatNumber(-vsAtr * 100, 0)}% abaixo`} da média dos últimos 14 dias
        </li>
        <li>Faixa de 80% acertou {f.coverage80_test != null ? `${formatNumber(f.coverage80_test * 100, 0)}%` : '~80%'} dos dias em 2023-2026</li>
        <li>Diz quanto, não para onde</li>
      </ul>
    </section>
  );
}

function Tile({ icon, label, value, sub }: { icon: ReactNode; label: string; value: string; sub: string }) {
  return (
    <div className={styles.tile}>
      <span className={styles.tileIcon} aria-hidden>
        {icon}
      </span>
      <p className={styles.tileLabel}>{label}</p>
      <p className={styles.tileValue}>{value}</p>
      <p className={styles.tileSub}>{sub}</p>
    </div>
  );
}

function RiskCalculator({ b, stopPoints, mult, setMult, dp }: { b: AssetBrief; stopPoints: number | null; mult: string; setMult: (v: string) => void; dp: number }) {
  const [balance, setBalance] = useState('1000');
  const [riskPct, setRiskPct] = useState('1');
  const plan = stopPoints
    ? riskPlan({
        balance: Number(balance.replace(',', '.')),
        riskPct: Number(riskPct.replace(',', '.')),
        stopPoints,
        contractSize: b.broker.contract_size,
        volumeMin: b.broker.volume_min,
        volumeStep: b.broker.volume_step,
        spreadPoints: b.broker.spread_points,
      })
    : null;
  const usd = (x: number) => `US$ ${formatNumber(x, 2)}`;
  return (
    <div className={styles.calc}>
      <div className={styles.calcInputs}>
        <Input label="Saldo da conta (US$)" inputMode="decimal" value={balance} onChange={(e) => setBalance(e.target.value)} />
        <Input label="Risco por operação (%)" inputMode="decimal" value={riskPct} onChange={(e) => setRiskPct(e.target.value)} />
        <div className={styles.field}>
          <span>Distância do stop</span>
          <ChipGroup label="Distância do stop" value={mult} onChange={setMult} items={STOP_MULTIPLES} />
        </div>
      </div>
      {plan ? (
        <dl className={styles.calcOut}>
          <dt>Stop</dt>
          <dd>{formatNumber(stopPoints!, dp)} de distância no preço</dd>
          <dt>Risco desejado</dt>
          <dd>{usd(plan.riskMoney)}</dd>
          <dt>Tamanho no {b.broker.symbol}</dt>
          <dd className={styles.big}>{plan.belowMinimum ? 'abaixo do lote mínimo' : `${formatNumber(plan.lots, 2)} lote(s)`}</dd>
          <dt>Risco real com esse lote</dt>
          <dd>{usd(plan.actualRisk)}</dd>
          {plan.spreadCost != null && (
            <>
              <dt>Custo do spread (ida e volta)</dt>
              <dd>
                {usd(plan.spreadCost)}
                {plan.spreadShareOfRisk != null && <span className={styles.meta}> · {formatNumber(plan.spreadShareOfRisk * 100, 1)}% do risco</span>}
              </dd>
            </>
          )}
        </dl>
      ) : (
        <p className={styles.meta}>Preencha saldo e risco; o ATR precisa estar disponível.</p>
      )}
      {plan?.belowMinimum && (
        <p className={styles.warn}>
          Com esse saldo e esse stop, o lote mínimo ({b.broker.volume_min}) arriscaria {usd(b.broker.volume_min * stopPoints! * b.broker.contract_size)}, acima do seu limite. Reduza o stop
          só se fizer sentido no gráfico, ou não opere este ativo com este saldo.
        </p>
      )}
    </div>
  );
}

function fmtWhen(iso: string) {
  return new Date(iso).toLocaleString('pt-BR', { weekday: 'short', day: '2-digit', month: '2-digit', hour: '2-digit', minute: '2-digit', timeZone: 'America/Sao_Paulo' });
}
