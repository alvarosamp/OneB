import { useState, type FormEvent } from 'react';
import { AlertTriangle, Info } from 'lucide-react';
import { api, ApiError } from '../../api/client';
import { Badge, Button, ChipGroup, ICON, Input, Section, Stat } from '../../components/ui';
import { formatCurrency, formatNumber } from '../../lib/format';
import { parseMoney } from '../../lib/money';
import type { AllocationItem, Simulation, TimelinePoint } from './types';
import styles from './Brasil.module.css';

type Goal = 'reserva' | 'objetivo' | 'aposentadoria';
type Reaction = 'vender' | 'esperar' | 'comprar';
type Experience = 'nenhuma' | 'pouca' | 'boa';
type YesNo = 'sim' | 'nao';

const GOALS = [
  { value: 'reserva' as const, label: 'Reserva de emergência' },
  { value: 'objetivo' as const, label: 'Um objetivo com data' },
  { value: 'aposentadoria' as const, label: 'Longo prazo / aposentadoria' },
];
const REACTIONS = [
  { value: 'vender' as const, label: 'Vendo para não perder mais' },
  { value: 'esperar' as const, label: 'Espero passar' },
  { value: 'comprar' as const, label: 'Aproveito para comprar mais' },
];
const EXPERIENCES = [
  { value: 'nenhuma' as const, label: 'Nunca investi' },
  { value: 'pouca' as const, label: 'Já investi um pouco' },
  { value: 'boa' as const, label: 'Invisto há anos' },
];
const YES_NO = [
  { value: 'sim' as const, label: 'Sim' },
  { value: 'nao' as const, label: 'Ainda não' },
];

const brl = (x: number | null | undefined) => formatCurrency(x, 'BRL', 0);

const GROUP_COLOR: Record<string, string> = {
  tesouro_selic: 'var(--series-1)',
  cdb_liquidez: 'var(--series-1)',
  lci_lca: 'var(--series-2)',
  tesouro_prefixado: 'var(--series-3)',
  tesouro_ipca: 'var(--series-3)',
  fii: 'var(--series-gold)',
  acoes_br: 'var(--series-4)',
  exterior: 'var(--series-4)',
};

/** Brasil › Simulador: perfil, divisão por classe com o porquê e projeção líquida de IR. */
export function Simulador() {
  const [goal, setGoal] = useState<Goal>('aposentadoria');
  const [initial, setInitial] = useState('1000');
  const [monthly, setMonthly] = useState('300');
  const [years, setYears] = useState('10');
  const [hasReserve, setHasReserve] = useState<YesNo>('nao');
  const [expenses, setExpenses] = useState('2500');
  const [reaction, setReaction] = useState<Reaction>('esperar');
  const [experience, setExperience] = useState<Experience>('nenhuma');
  const [realRate, setRealRate] = useState('6,5');
  const [premium, setPremium] = useState('2');
  const [result, setResult] = useState<Simulation | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  async function submit(e: FormEvent) {
    e.preventDefault();
    const ini = parseMoney(initial);
    const mon = parseMoney(monthly);
    const months = Math.round(parseMoney(years) * 12);
    const exp = parseMoney(expenses);
    if ([ini, mon, months].some(Number.isNaN) || ini < 0 || mon < 0) return setError('Confira os valores digitados.');
    if (ini <= 0 && mon <= 0) return setError('Informe um valor inicial ou um aporte mensal (pode ser pouco: R$ 50 já serve).');
    if (months < 1 || months > 480) return setError('O prazo deve ficar entre 1 mês (0,1 ano) e 40 anos.');
    setError(null);
    setLoading(true);
    try {
      const body = {
        initial: ini,
        monthly: mon,
        months,
        goal,
        has_reserve: goal === 'reserva' || hasReserve === 'sim',
        monthly_expenses: hasReserve === 'nao' && exp > 0 ? exp : null,
        drop_reaction: reaction,
        experience,
        ipca_real_rate: parseMoney(realRate) || 6.5,
        equity_premium: Number.isNaN(parseMoney(premium)) ? null : parseMoney(premium),
      };
      setResult(await api.post<Simulation>('/api/brasil/simulate', body));
    } catch (err) {
      setError(err instanceof ApiError ? err.message : 'Não foi possível simular agora.');
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className={styles.page}>
      <Section title="Conte o seu caso">
        <form onSubmit={submit} className={styles.page} style={{ gap: 'var(--sp-4)' }}>
          <ChipGroup label="Para que é esse dinheiro?" value={goal} onChange={setGoal} items={GOALS} />
          <div className={styles.form}>
            <Input label="Quanto você tem para começar (R$)" inputMode="decimal" value={initial} onChange={(e) => setInitial(e.target.value)} />
            <Input label="Quanto consegue guardar por mês (R$)" inputMode="decimal" value={monthly} onChange={(e) => setMonthly(e.target.value)} />
            <Input
              label="Por quantos anos"
              hint={goal === 'reserva' ? 'Só para a projeção; a reserva fica sempre disponível.' : 'Ex.: 0,5 = 6 meses'}
              inputMode="decimal"
              value={years}
              onChange={(e) => setYears(e.target.value)}
            />
          </div>
          {goal !== 'reserva' && (
            <div className={styles.form}>
              <div>
                <p className={styles.meta}>Você já tem reserva de emergência?</p>
                <ChipGroup label="Já tem reserva de emergência?" value={hasReserve} onChange={setHasReserve} items={YES_NO} />
              </div>
              {hasReserve === 'nao' && (
                <Input label="Seus gastos por mês (R$)" hint="Para calcular a reserva (6 meses)." inputMode="decimal" value={expenses} onChange={(e) => setExpenses(e.target.value)} />
              )}
            </div>
          )}
          <div>
            <p className={styles.meta}>Se seus investimentos caíssem 20% em um mês, você…</p>
            <ChipGroup label="Reação a uma queda de 20%" value={reaction} onChange={setReaction} items={REACTIONS} />
          </div>
          <div>
            <p className={styles.meta}>Sua experiência</p>
            <ChipGroup label="Experiência com investimentos" value={experience} onChange={setExperience} items={EXPERIENCES} />
          </div>
          <details>
            <summary className={styles.meta}>Premissas avançadas (opcional)</summary>
            <div className={styles.form} style={{ marginTop: 'var(--sp-3)' }}>
              <Input label="Tesouro IPCA+: taxa acima da inflação (% a.a.)" inputMode="decimal" value={realRate} onChange={(e) => setRealRate(e.target.value)} />
              <Input
                label="Ações: retorno esperado acima do CDI (p.p. a.a.)"
                hint="Use 0 ou negativo para um cenário pessimista."
                inputMode="decimal"
                value={premium}
                onChange={(e) => setPremium(e.target.value)}
              />
            </div>
          </details>
          <div className={styles.formActions}>
            <Button type="submit" variant="primary" disabled={loading}>
              {loading ? 'Simulando…' : 'Simular'}
            </Button>
            {error && (
              <span role="alert" className={styles.down}>
                {error}
              </span>
            )}
          </div>
        </form>
      </Section>
      {result && <Result r={result} />}
    </div>
  );
}

function Result({ r }: { r: Simulation }) {
  const p = r.projection;
  return (
    <>
      <Section title={`Seu perfil: ${r.profile.label}`} divided>
        <p className={styles.lead}>{r.profile.text}</p>
        <ul className={styles.meta}>
          {r.profile.factors.map((f) => (
            <li key={f}>{f}</li>
          ))}
        </ul>
      </Section>

      <Section title="O plano">
        <ol className={styles.steps}>
          {r.steps.map((s) => (
            <li key={s.title}>
              <strong>{s.title}</strong>
              <span className={styles.meta}>{s.text}</span>
            </li>
          ))}
        </ol>
      </Section>

      <Section title="Onde colocar e por quê" meta="divisão por tipo de investimento">
        {r.allocation.map((a) => (
          <AllocationRow key={a.key} a={a} />
        ))}
      </Section>

      <Section title={`Quanto pode virar em ${p.years >= 1 ? `${formatNumber(p.years, p.years % 1 ? 1 : 0)} ${p.years === 1 ? 'ano' : 'anos'}` : `${p.months} meses`}`} meta="líquido de imposto e taxas">
        <div className={styles.stats}>
          <Stat label="Você terá aplicado" value={brl(p.invested)} />
          <Stat
            label={p.has_variable ? 'Cenário do meio' : 'Valor estimado'}
            value={brl(p.median)}
            sub={`≈ ${brl(p.median_today_money)} em dinheiro de hoje`}
          />
          {p.has_variable && <Stat label="Faixa de 80% dos cenários" value={`${brl(p.p10)} a ${brl(p.p90)}`} />}
          <Stat label="Na poupança" value={brl(p.poupanca)} sub={p.vs_poupanca > 0 ? `${brl(p.vs_poupanca)} a menos que o plano` : undefined} />
        </div>
        <ProjectionChart points={p.timeline} band={p.has_variable} />
      </Section>

      {r.warnings.length > 0 && (
        <Section title="Atenção">
          {r.warnings.map((w) => (
            <p key={w} className={styles.callout}>
              <AlertTriangle {...ICON} aria-hidden /> {w}
            </p>
          ))}
        </Section>
      )}

      <Section title="Premissas usadas">
        <dl className={styles.dl}>
          <dt>Selic / CDI / IPCA</dt>
          <dd>
            {formatNumber(r.assumptions.selic)}% / {formatNumber(r.assumptions.cdi)}% / {formatNumber(r.assumptions.ipca_12m)}% ao ano, constantes no prazo
            {r.assumptions.rates_stale ? ' (Banco Central fora do ar: valores de reserva)' : ''}
          </dd>
          <dt>Poupança</dt>
          <dd>{formatNumber(r.assumptions.poupanca)}% ao ano</dd>
          <dt>Tesouro IPCA+</dt>
          <dd>IPCA + {formatNumber(r.assumptions.ipca_real_rate, 1)}% ao ano</dd>
          <dt>Tesouro Prefixado</dt>
          <dd>{formatNumber(r.assumptions.prefixado_rate)}% ao ano</dd>
          <dt>Renda variável</dt>
          <dd>
            CDI + prêmio (ações {formatNumber(r.assumptions.variable.acoes_br?.premium_over_cdi, 1)} p.p., exterior{' '}
            {formatNumber(r.assumptions.variable.exterior?.premium_over_cdi, 1)} p.p., FIIs {formatNumber(r.assumptions.variable.fii?.premium_over_cdi, 1)} p.p.),
            com a oscilação típica de cada classe
            {r.assumptions.scenarios ? `, em ${formatNumber(r.assumptions.scenarios, 0)} cenários` : ''}
          </dd>
          <dt>Impostos</dt>
          <dd>IR regressivo por aporte, isenções de LCI/LCA e poupança, 15% em ETFs, 20% no lucro de FIIs, taxa B3 de 0,20% no Tesouro</dd>
        </dl>
        <p className={[styles.callout, styles.info].join(' ')}>
          <Info {...ICON} aria-hidden /> {r.disclaimer}
        </p>
      </Section>
    </>
  );
}

function AllocationRow({ a }: { a: AllocationItem }) {
  return (
    <div className={styles.allocRow}>
      <div className={styles.allocHead}>
        <span>
          {a.label}{' '}
          <Badge tone={a.group === 'renda_fixa' ? 'info' : 'warning'}>{a.group === 'renda_fixa' ? 'renda fixa' : 'renda variável'}</Badge>
        </span>
        <span>
          {a.pct}% · {a.initial_amount > 0 ? `${brl(a.initial_amount)} agora` : ''}
          {a.initial_amount > 0 && a.monthly_amount > 0 ? ' + ' : ''}
          {a.monthly_amount > 0 ? `${brl(a.monthly_amount)}/mês${a.monthly_from > 1 ? ` a partir do mês ${a.monthly_from}` : ''}` : ''}
        </span>
      </div>
      <div className={styles.bar} aria-hidden>
        <span style={{ width: `${a.pct}%`, background: GROUP_COLOR[a.key] ?? 'var(--brand)' }} />
      </div>
      <p className={styles.reason}>{a.reason}</p>
      <p className={styles.meta}>
        Resgate: {a.liquidity}. Garantia: {a.guarantee}. Imposto: {a.tax}.
      </p>
    </div>
  );
}

const W = 640;
const H = 260;
const PAD = { l: 64, r: 12, t: 12, b: 28 };

function ProjectionChart({ points, band }: { points: TimelinePoint[]; band: boolean }) {
  if (points.length < 2) return null;
  const maxX = points[points.length - 1].month || 1;
  const maxY = Math.max(...points.map((p) => Math.max(p.p90, p.poupanca, p.invested))) || 1;
  const x = (m: number) => PAD.l + (m / maxX) * (W - PAD.l - PAD.r);
  const y = (v: number) => H - PAD.b - (v / maxY) * (H - PAD.t - PAD.b);
  const line = (k: keyof TimelinePoint) => points.map((p, i) => `${i ? 'L' : 'M'}${x(p.month).toFixed(1)},${y(p[k]).toFixed(1)}`).join(' ');
  const area = `${points.map((p, i) => `${i ? 'L' : 'M'}${x(p.month).toFixed(1)},${y(p.p90).toFixed(1)}`).join(' ')} ${[...points]
    .reverse()
    .map((p) => `L${x(p.month).toFixed(1)},${y(p.p10).toFixed(1)}`)
    .join(' ')} Z`;
  const ticks = [0, 0.5, 1].map((f) => f * maxY);
  const yearsTotal = maxX / 12;
  return (
    <figure style={{ margin: 'var(--sp-4) 0 0' }}>
      <svg viewBox={`0 0 ${W} ${H}`} className={styles.chart} role="img" aria-label="Evolução do patrimônio no plano, na poupança e do total aplicado">
        {ticks.map((t) => (
          <g key={t}>
            <line x1={PAD.l} x2={W - PAD.r} y1={y(t)} y2={y(t)} stroke="var(--chart-grid)" />
            <text x={PAD.l - 6} y={y(t) + 4} textAnchor="end" fontSize="11" fill="var(--chart-text)">
              {formatCurrency(t, 'BRL', 0)}
            </text>
          </g>
        ))}
        <text x={x(maxX)} y={H - 8} textAnchor="end" fontSize="11" fill="var(--chart-text)">
          {yearsTotal >= 1 ? `${formatNumber(yearsTotal, yearsTotal % 1 ? 1 : 0)} anos` : `${maxX} meses`}
        </text>
        <text x={PAD.l} y={H - 8} fontSize="11" fill="var(--chart-text)">
          hoje
        </text>
        {band && <path d={area} fill="var(--chart-band)" opacity={0.9} />}
        <path d={line('invested')} fill="none" stroke="var(--text-tertiary)" strokeDasharray="4 4" strokeWidth={1.5} />
        <path d={line('poupanca')} fill="none" stroke="var(--series-2)" strokeWidth={2} />
        <path d={line('p50')} fill="none" stroke="var(--series-1)" strokeWidth={2.5} />
      </svg>
      <figcaption className={styles.legend}>
        <span>
          <i style={{ background: 'var(--series-1)' }} />
          Plano{band ? ' (cenário do meio)' : ''}
        </span>
        {band && (
          <span>
            <i style={{ background: 'var(--chart-band)' }} />
            80% dos cenários
          </span>
        )}
        <span>
          <i style={{ background: 'var(--series-2)' }} />
          Poupança
        </span>
        <span>
          <i style={{ background: 'var(--text-tertiary)' }} />
          Total aplicado
        </span>
      </figcaption>
    </figure>
  );
}
