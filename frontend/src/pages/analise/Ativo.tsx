import { useMemo, useState, type ReactNode } from 'react';
import { useSearchParams } from 'react-router-dom';
import { CalendarClock, FlaskConical, Gauge, ShieldCheck } from 'lucide-react';
import { useApi } from '../../hooks/useApi';
import { AnalysisReportButton } from '../../components/assistant/AnalysisReport';
import { ChartPanel, type PriceLevel } from '../../components/terminal/ChartPanel';
import { AsyncContent, Badge, ChipGroup, EmptyState, ICON, Input, Section, SkeletonLines } from '../../components/ui';
import type { BadgeTone } from '../../components/ui/Badge';
import { chartPath, TIMEFRAMES } from '../../lib/timeframes';
import { formatNumber, priceDigits } from '../../lib/format';
import { binOf } from '../../lib/heatmap';
import { riskPlan } from '../../lib/riskPlan';
import type { AssetBrief, ChartData, PlanLiveSummary, PlanScoreboard, SessionForecast, TradePlan, VolfcScoreboard } from '../../types';
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
  const [dir, setDir] = useState<'long' | 'short'>('long');
  const [mt5Entry, setMt5Entry] = useState('');
  const entryNum = Number(mt5Entry.replace(/\./g, '').replace(',', '.'));
  const entryParam = mt5Entry.trim() && entryNum > 0 ? `&entry=${entryNum}` : '';
  const plan = useApi<TradePlan>(`/api/analysis/trade-plan/${b.key}?direction=${dir}&stop_atr=${mult}${entryParam}`, { pollMs: 120_000 });
  const levels = useMemo<PriceLevel[]>(() => {
    const p = plan.data;
    if (p?.available) {
      return [
        { label: p.entry_source === 'mt5' ? 'Entrada (seu MT5)' : 'Entrada (preço do futuro)', value: p.entry, colorVar: '--chart-level-entry' },
        { label: `Stop (${multLabel}x ATR 1h)`, value: p.stop, colorVar: '--chart-level-stop' },
        ...p.targets.map((t) => ({ label: `TP${t.target_r} (${t.target_r}R)`, value: t.price, colorVar: '--chart-level-target' })),
      ];
    }
    if (!m.price || !stopPoints) return [];
    return [
      { label: `Stop se comprar (${multLabel}x ATR 1h)`, value: m.price - stopPoints, colorVar: '--chart-level-stop' },
      { label: `Stop se vender (${multLabel}x ATR 1h)`, value: m.price + stopPoints, colorVar: '--chart-level-stop' },
    ];
  }, [plan.data, m.price, stopPoints, multLabel]);
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
          {b.freshness && <Freshness f={b.freshness} />}
          <div className={styles.heroAction}>
            <AnalysisReportButton assetKey={b.key} label={b.label} />
          </div>
        </div>
        <div className={styles.tiles}>
          <Tile icon={<Gauge {...ICON} />} label="Movimento típico do dia" value={m.atr_d1 != null ? `${formatNumber(m.atr_d1, dp)}` : '—'} sub="ATR de 14 dias, em preço" />
          <Tile icon={<Gauge {...ICON} />} label="Movimento típico da hora" value={m.atr_h1 != null ? `${formatNumber(m.atr_h1, dp)}` : '—'} sub="ATR de 14 horas, em preço" />
          <Tile
            icon={<ShieldCheck {...ICON} />}
            label={`Spread no ${b.broker.symbol}`}
            value={b.broker.spread_points != null ? `${formatNumber(b.broker.spread_points, b.broker.spread_points >= 0.1 ? 2 : 5)}` : 'sem medição'}
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
      {b.session_forecast && <SessionForecastCard f={b.session_forecast} dp={dp} />}
      <Scoreboard assetKey={b.key} />

      <Section
        title="Plano de trade"
        meta={<span className={styles.meta}>para a direção que você escolher · confiança medida, não estimada</span>}
      >
        <div className={styles.planControls}>
          <ChipGroup
            label="Direção"
            value={dir}
            onChange={(v) => setDir(v as 'long' | 'short')}
            items={[
              { value: 'long', label: 'Se eu comprar' },
              { value: 'short', label: 'Se eu vender' },
            ]}
          />
          <ChipGroup label="Distância do stop" value={mult} onChange={setMult} items={STOP_MULTIPLES} />
          <Input
            label={`Seu preço de entrada no ${b.broker.symbol} (opcional)`}
            inputMode="decimal"
            placeholder="ex.: 30897,85"
            value={mt5Entry}
            onChange={(e) => setMt5Entry(e.target.value)}
          />
        </div>
        <AsyncContent state={plan} loading={<SkeletonLines lines={5} />} empty={<EmptyState title="Plano indisponível" />} errorTitle="Plano indisponível">
          {(p) => (p.available ? <PlanTable p={p} dp={dp} /> : <p className={styles.meta}>{p.reason}</p>)}
        </AsyncContent>
      </Section>

      <PlanLive assetKey={b.key} />

      <section className={styles.chart} aria-label="Gráfico de 5 dias com o plano de trade">
        <AsyncContent state={chart} loading={<SkeletonLines lines={8} />} empty={<EmptyState title="Sem gráfico agora" />}>
          {(d) => <ChartPanel data={d} timeframe={FIVE_DAYS} height={340} levels={levels} label={b.symbol} />}
        </AsyncContent>
        <p className={styles.meta}>
          As linhas mostram o plano escolhido acima: entrada no preço atual, stop de {multLabel}x o movimento típico da hora e alvos de 1R, 2R e 3R. É gestão de risco, não previsão de direção.
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
          {f.us_holiday ? ` Atenção: é feriado nos EUA (${f.us_holiday}); o pregão tende a ser mais calmo do que o previsto.` : ''}
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

function Scoreboard({ assetKey }: { assetKey: string }) {
  const data = useApi<VolfcScoreboard>('/api/analysis/volfc-scoreboard', { pollMs: 30 * 60_000 });
  const a = data.data?.assets[assetKey];
  if (!a || !a.summary) return null;
  const s = a.summary;
  const fmtDay = (iso: string) => iso.split('-').reverse().slice(0, 2).join('/');
  return (
    <Section title="Placar ao vivo da previsão" meta={<span className={styles.meta}>desde {a.start ? fmtDay(a.start) : '12/10'}</span>}>
      {s.days === 0 ? (
        <p className={styles.meta}>O primeiro pregão acompanhado ainda não fechou. A cada dia, a previsão feita na véspera é comparada com o que aconteceu.</p>
      ) : (
        <>
          <p className={styles.meta}>
            <strong>
              {s.inside80} de {s.days}
            </strong>{' '}
            pregões ficaram dentro da faixa de 80% (esperado: cerca de 8 em 10). A previsão errou menos que a média de 14 dias em {s.beats_atr_days} de {s.days}.
            {s.registered_before ? ` ${s.registered_before} previsões foram gravadas no banco antes do pregão começar e não mudam mais.` : ''}
            {s.days < 20 ? ' Com menos de 20 dias, o placar ainda é ruído.' : ''}
          </p>
          <div className={styles.scoreWrap}>
            <table className={styles.scoreTable}>
              <thead>
                <tr>
                  <th scope="col">Pregão</th>
                  <th scope="col">Previsto</th>
                  <th scope="col">Faixa 80%</th>
                  <th scope="col">Realizado</th>
                  <th scope="col">Dentro?</th>
                  <th scope="col">Previsão gravada</th>
                </tr>
              </thead>
              <tbody>
                {[...a.rows].reverse().map((r) => (
                  <tr key={r.date}>
                    <td>
                      {fmtDay(r.date)}
                      {r.event ? ' · evento' : ''}
                    </td>
                    <td>{formatNumber(r.expected_pct, 2)}%</td>
                    <td>
                      {formatNumber(r.low80_pct, 2)}–{formatNumber(r.high80_pct, 2)}%
                    </td>
                    <td>{formatNumber(r.realized_pct, 2)}%</td>
                    <td>{r.inside80 ? 'sim' : 'não'}</td>
                    <td>{r.registered === 'antes' ? 'antes do pregão' : r.registered === 'durante' ? 'com o pregão aberto' : 'reconstruída'}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </>
      )}
    </Section>
  );
}

const STATUS_TEXT = { acumulando: 'acumulando planos', confirmado: 'chance confirmada', divergente: 'divergente do anunciado' } as const;
const RESULT_TEXT = { hit: 'alvo', stop: 'stop', expired: 'expirou', open: 'em andamento' } as const;

/** Placar ao vivo do plano: a chance anunciada contra planos registrados por regra fixa (plan_live_v1). */
function PlanLive({ assetKey }: { assetKey: string }) {
  const data = useApi<PlanScoreboard>('/api/analysis/plan-scoreboard', { pollMs: 15 * 60_000 });
  const a = data.data?.assets[assetKey];
  if (!a || !a.live) return null;
  const fmtDay = (iso: string) => iso.split('-').reverse().slice(0, 2).join('/');
  const liveClosed = a.live.summary.long.targets[0]?.closed ?? 0;
  return (
    <Section title="Placar ao vivo do plano" meta={<span className={styles.meta}>desde {a.start ? fmtDay(a.start) : '15/10'} · todo dia às {a.entry_time_brasilia ?? '10:30'} de Brasília</span>}>
      <p className={styles.meta}>
        {a.note}
        {a.live.stored ? ` ${a.live.stored} planos gravados ao vivo (enquanto estavam abertos); encerrado não muda mais.` : ''}
      </p>
      {liveClosed === 0 ? (
        <p className={styles.meta}>O primeiro plano ao vivo ainda não fechou. Enquanto isso, veja abaixo a conferência retroativa (fora do placar).</p>
      ) : (
        <PlanLiveTable s={a.live.summary} />
      )}
      {a.live.rows.length > 0 && (
        <p className={styles.meta}>
          Últimos planos:{' '}
          {[...a.live.rows]
            .reverse()
            .slice(0, 6)
            .map((r) => `${fmtDay(r.date)} ${r.direction === 'long' ? 'compra' : 'venda'} 2R: ${RESULT_TEXT[r.results['2']]}`)
            .join(' · ')}
        </p>
      )}
      {a.retro && (
        <details className={styles.retro}>
          <summary>Conferência retroativa (de {fmtDay(a.retro.from)} até antes de {fmtDay(a.start ?? '2026-10-15')}, não conta no placar)</summary>
          <PlanLiveTable s={a.retro.summary} />
        </details>
      )}
    </Section>
  );
}

function PlanLiveTable({ s }: { s: PlanLiveSummary }) {
  return (
    <div className={styles.scoreWrap}>
      <table className={styles.scoreTable}>
        <thead>
          <tr>
            <th scope="col">Plano</th>
            <th scope="col">Alvo</th>
            <th scope="col">Anunciado</th>
            <th scope="col">Medido</th>
            <th scope="col">Faixa de 95%</th>
            <th scope="col">Dentro?</th>
          </tr>
        </thead>
        <tbody>
          {(['long', 'short'] as const).flatMap((dir) =>
            s[dir].targets.map((t, i) => (
              <tr key={`${dir}-${t.target_r}`}>
                <td>{i === 0 ? `${dir === 'long' ? 'Compra' : 'Venda'} · ${STATUS_TEXT[s[dir].status]}` : ''}</td>
                <td>TP{t.target_r} ({t.target_r}R)</td>
                <td>{pct0(t.announced)}</td>
                <td>
                  {t.hits} de {t.closed} ({pct0(t.rate)})
                </td>
                <td>{t.wilson95 ? `${pct0(t.wilson95[0])}–${pct0(t.wilson95[1])}` : '—'}</td>
                <td>{t.consistent == null ? '—' : t.consistent ? 'sim' : 'não'}</td>
              </tr>
            )),
          )}
        </tbody>
      </table>
    </div>
  );
}

/** Até o fechamento de NY (sessfc_v1): só aparece para ativo aprovado no teste pré-registrado. */
function SessionForecastCard({ f, dp }: { f: SessionForecast; dp: number }) {
  const close = new Date(f.close_utc).toLocaleTimeString('pt-BR', { hour: '2-digit', minute: '2-digit', timeZone: 'America/Sao_Paulo' });
  return (
    <Section title="Das 10:30 até o fechamento de Nova York" meta={<Badge tone="positive">Aprovado em teste pré-registrado</Badge>}>
      <p className={styles.meta}>
        Deve andar cerca de <strong>{formatNumber(f.expected_points, dp)}</strong> ({formatNumber(f.expected_pct, 2)}%) entre máxima e mínima até as {close} de
        Brasília. Em 8 de cada 10 dias, de {formatNumber(f.low80_points, dp)} a {formatNumber(f.high80_points, dp)}.{f.event ? ' Dia de evento: a previsão já inclui o efeito.' : ''}{' '}
        {f.closed ? 'Janela encerrada, andou' : 'Até agora'}: {formatNumber((f.so_far_pct / 100) * f.entry_price, dp)} ({formatNumber(f.so_far_pct, 2)}%)
        {(f.so_far_pct / 100) * f.entry_price > f.high80_points ? ' — acima da faixa: é um dos 2 em cada 10 dias que passam dela.' : '.'} Diz quanto, não para onde.
      </p>
    </Section>
  );
}

const pct0 = (x: number | null | undefined) => (x == null ? '—' : `${formatNumber(x * 100, 0)}%`);

function PlanTable({ p, dp }: { p: TradePlan; dp: number }) {
  const sideWord = p.direction === 'long' ? 'compra' : 'venda';
  const fromMt5 = p.entry_source === 'mt5';
  const [below, above] = p.direction === 'long' ? ['abaixo', 'acima'] : ['acima', 'abaixo'];
  return (
    <div className={styles.plan}>
      {!fromMt5 && p.basis_note && <p className={styles.planBasis}>{p.basis_note}</p>}
      <dl className={styles.planHead}>
        <dt>Stop</dt>
        <dd>
          <strong>{formatNumber(p.stop_distance, dp)}</strong> {below} da entrada
          {fromMt5 && <span className={styles.meta}> · no MT5: {formatNumber(p.stop, dp)}</span>}
        </dd>
        <dt>Entrada</dt>
        <dd>{fromMt5 ? `${formatNumber(p.entry, dp)} (seu preço no MT5)` : <span className={styles.meta}>informe seu preço no MT5 para ver os níveis exatos</span>}</dd>
        {p.min_lot && (
          <>
            <dt>Saldo mínimo</dt>
            <dd>
              <strong>US$ {formatNumber(p.min_lot.balance_1pct, 0)}</strong> para arriscar 1% com o menor lote
              <span className={styles.meta}>
                {' '}
                · {formatNumber(p.min_lot.volume_min, 2)} lote no {p.min_lot.symbol} arrisca US$ {formatNumber(p.min_lot.risk_usd, 2)} neste stop (2%: US${' '}
                {formatNumber(p.min_lot.balance_2pct, 0)})
              </span>
            </dd>
          </>
        )}
      </dl>
      <div className={styles.scoreWrap}>
        <table className={styles.scoreTable}>
          <thead>
            <tr>
              <th scope="col">Alvo</th>
              <th scope="col">Distância</th>
              {fromMt5 && <th scope="col">Preço no MT5</th>}
              <th scope="col">Chance antes do stop</th>
              <th scope="col">Nesta hora</th>
              <th scope="col">Resultado médio</th>
            </tr>
          </thead>
          <tbody>
            {p.targets.map((t) => (
              <tr key={t.target_r}>
                <td>
                  TP{t.target_r} ({t.target_r}R)
                </td>
                <td>
                  {formatNumber(t.distance, dp)} {above}
                </td>
                {fromMt5 && <td>{formatNumber(t.price, dp)}</td>}
                <td>
                  <strong>{pct0(t.p_target)}</strong>
                </td>
                <td>{pct0(t.p_target_this_hour)}</td>
                <td>{t.mean_r == null ? '—' : `${t.mean_r >= 0 ? '+' : ''}${formatNumber(t.mean_r, 2)}R`}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <p className={styles.meta}>
        Grau de confiança medido: em {p.targets[0]?.n?.toLocaleString('pt-BR') ?? '—'} entradas de {sideWord} desse tipo ({p.measured_period}), essa foi a
        frequência de bater cada alvo antes do stop, já com o spread. Um anúncio de 80% a 95% de acerto não sobrevive a essa conta.
      </p>
      {p.warnings.length > 0 && (
        <ul className={styles.planWarnings}>
          {p.warnings.map((w) => (
            <li key={w}>{w}</li>
          ))}
        </ul>
      )}
      <p className={styles.meta}>{p.note}</p>
    </div>
  );
}

function Freshness({ f }: { f: NonNullable<AssetBrief['freshness']> }) {
  const tone = f.status === 'ok' ? 'positive' : f.status === 'warn' ? 'warning' : 'negative';
  const problems = f.checks.filter((c) => c.status !== 'ok');
  return (
    <p className={styles.meta}>
      <Badge tone={tone}>{f.status === 'ok' ? 'Dados em dia' : f.status === 'warn' ? 'Dados com atraso' : 'Dados com problema'}</Badge>{' '}
      {f.source}
      {f.intraday_age_minutes != null && ` · última barra há ${formatNumber(f.intraday_age_minutes, 0)} min`}
      {problems.length > 0 && ` · ${problems.map((c) => c.detail).join(' ')}`}
    </p>
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
          <dd>
            {formatNumber(stopPoints!, dp)} de distância no preço
            {b.range_forecast && (
              <span className={styles.meta}>
                {' '}
                · {formatNumber((stopPoints! / b.range_forecast.expected_price) * 100, 0)}% do movimento previsto para o pregão
                {stopPoints! / b.range_forecast.expected_price < 0.2 ? ' (curto: o ruído do dia costuma alcançar)' : ''}
              </span>
            )}
          </dd>
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
