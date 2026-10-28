import { CheckCircle2, ShieldCheck, XCircle } from 'lucide-react';
import { useApi } from '../../hooks/useApi';
import { AsyncContent, Badge, EmptyState, ICON, Section, SkeletonLines } from '../../components/ui';
import { formatNumber } from '../../lib/format';
import styles from './Confianca.module.css';

interface Proof {
  forecast: { key: string; label: string; error_reduction: number; coverage80: number; test_days: number }[];
  forecast_pass: boolean;
  forecast_mean_reduction: number | null;
  live: { key: string; label: string; since: string; days: number; inside80: number; beats_atr_days: number }[];
  events: { key: string; label: string; event: string; post30: number; events: number }[];
  odds: { key: string; label: string; direction: 'long' | 'short'; target_r: number; p_target: number; n: number }[];
  promise_test: { key: string; label: string; tp1_r: number; win_rate: number; mean_r: number }[];
  promise_period: string | null;
  not_promised: { title: string; detail: string }[];
  replay?: { key: string; label: string; rule: string; rule_label: string; trades: number | null; mean_r: number | null; final_balance: number | null; passed: boolean }[];
  replay_passed?: string[];
  plan_live?: { key: string; label: string; part: 'live' | 'retro'; direction: 'long' | 'short'; status: string; target_r: number; announced: number | null; hits: number; closed: number; consistent: boolean | null }[];
  plan_live_start?: string;
  plan_live_retro_from?: string;
  ai_reliability?: {
    tests: { generated_at: string; golden: { cases: number; passed: number; ungrounded_number_cases: number; order_language_cases: number };
      routing: { cases: number; passed: number; routes: number } } | null;
    live: { days: number; answers: number; verified: number; rated: number; useful: number };
  };
  session_test?: {
    passed_assets: string[];
    assets: { key: string; label: string; error_reduction: number; coverage80: number; test_days: number; passed: boolean;
      live: { days: number; inside80: number; coverage80: number | null } | null }[];
  } | null;
  diary?: {
    date: string;
    assets: {
      key: string;
      label: string;
      range?: { expected_pct: number; low80_pct: number; high80_pct: number; realized_pct: number; inside80: boolean; event: boolean };
      plans?: Partial<Record<'long' | 'short', Record<string, 'hit' | 'stop' | 'expired' | 'open'>>>;
    }[];
  }[];
}

const pct = (x: number, d = 0) => `${formatNumber(x * 100, d)}%`;
const r3 = (x: number) => `${x >= 0 ? '+' : ''}${formatNumber(x, 3)}R`;
const day = (iso: string) => iso.split('-').reverse().slice(0, 2).join('/');

/** Análise › Por que confiar: só números medidos; o que é comprovado e o que não prometemos. */
export function Confianca() {
  const data = useApi<Proof>('/api/analysis/proof', { isEmpty: (d) => d.forecast.length === 0 });
  return (
    <AsyncContent state={data} loading={<SkeletonLines lines={14} />} empty={<EmptyState title="Resultados indisponíveis" />} errorTitle="Página indisponível">
      {(d) => <ProofPage d={d} />}
    </AsyncContent>
  );
}

function ProofPage({ d }: { d: Proof }) {
  const nas = d.forecast.find((f) => f.key === 'NAS100');
  const cpiNas = d.events.find((e) => e.key === 'NAS100' && e.event.startsWith('CPI'));
  const totalN = d.odds.filter((o) => o.target_r === 1).reduce((s, o) => s + o.n, 0);
  const odd = (key: string, dir: 'long' | 'short', r: number) => d.odds.find((o) => o.key === key && o.direction === dir && o.target_r === r);
  return (
    <div className={styles.page}>
      <header className={styles.hero}>
        <p className={styles.kicker}>
          <ShieldCheck {...ICON} aria-hidden /> Por que confiar no OneB
        </p>
        <h2 className={styles.heroTitle}>Nada aqui é palpite: cada número foi medido em anos de dados reais, já descontando o spread da corretora.</h2>
        <p className={styles.lead}>
          A IA do OneB diz quanto o mercado deve mexer, quando os eventos aumentam o risco, quanto custa operar e a chance real de cada alvo.
          Cada uma dessas respostas passou por teste com regra definida antes do resultado.
        </p>
        <div className={styles.tiles}>
          {d.forecast_mean_reduction != null && (
            <Tile value={pct(d.forecast_mean_reduction)} label="menos erro que o ATR" sub="prevendo quanto o mercado mexe amanhã" />
          )}
          {nas && <Tile value={pct(nas.coverage80)} label="dos dias dentro da faixa prevista" sub="Nasdaq, 2023 a 2026 (meta: 80%)" />}
          {cpiNas && <Tile value={`${formatNumber(cpiNas.post30, 1)}x`} label="movimento após o CPI" sub={`Nasdaq, medido em ${cpiNas.events} divulgações`} />}
          {totalN > 0 && <Tile value={formatNumber(totalN, 0)} label="entradas medidas" sub="para calcular a chance real de cada alvo" />}
        </div>
      </header>

      <Section title="O que a IA acerta — comprovado" meta={<Badge tone="positive">Aprovado em teste pré-registrado</Badge>}>
        <p className={styles.reading}>
          Previsão de <strong>quanto</strong> o preço vai se mover no próximo pregão (máxima menos mínima), testada em 2023 a 2026 — anos que o modelo
          nunca tinha visto. Ela erra menos que a média de 14 dias que todo trader usa, e a faixa de 80% acerta perto de 8 em cada 10 dias.
        </p>
        <Table
          head={['Ativo', 'Erro menor que o ATR', 'Dias dentro da faixa de 80%', 'Dias testados']}
          rows={d.forecast.map((f) => [f.label, pct(f.error_reduction), pct(f.coverage80), formatNumber(f.test_days, 0)])}
        />
        {d.live.length > 0 && (
          <p className={styles.meta}>
            Placar ao vivo (previsão feita na véspera, sem ajuste posterior):{' '}
            {d.live.map((l) => `${l.label} ${l.inside80} de ${l.days} pregões dentro da faixa desde ${day(l.since)}`).join(' · ')}.
          </p>
        )}
      </Section>

      <Section title="Eventos: o risco que a IA avisa antes" meta={<Badge tone="positive">Aprovado em teste</Badge>}>
        <p className={styles.reading}>Quanto o movimento costuma multiplicar na primeira meia hora após cada divulgação, contra um dia normal no mesmo horário (2019 a 2026).</p>
        <Table
          head={['Evento', 'Nasdaq', 'Ouro']}
          rows={['CPI (inflação)', 'Payroll (emprego)', 'FOMC (juros do Fed)'].map((ev) => [
            ev,
            ...['NAS100', 'XAUUSD'].map((k) => {
              const e = d.events.find((x) => x.key === k && x.event === ev);
              return e ? `${formatNumber(e.post30, 1)}x` : '—';
            }),
          ])}
        />
      </Section>

      <Section title="A chance real de cada alvo" meta={<span className={styles.meta}>stop de 1,5 ATR de 1 hora · já descontando o spread</span>}>
        <p className={styles.reading}>
          Quando você monta um plano no OneB, a confiança mostrada é esta: a frequência real com que o alvo foi atingido antes do stop, medida em milhares
          de entradas de 2023 a 2026. Alvo mais longe paga mais, mas acontece menos — e é isso que define o tamanho do seu lote.
        </p>
        <Table
          head={['Alvo', 'Nasdaq (compra)', 'Nasdaq (venda)', 'Ouro (compra)', 'Ouro (venda)']}
          rows={[1, 2, 3].map((r) => [
            `${r}R`,
            ...(['NAS100', 'XAUUSD'] as const).flatMap((k) => (['long', 'short'] as const).map((dir) => {
              const o = odd(k, dir, r);
              return o ? pct(o.p_target) : '—';
            })),
          ])}
        />
      </Section>

      {d.plan_live && d.plan_live.length > 0 && <PlanLiveProof d={d} />}
      {d.diary && d.diary.length > 0 && <Diary diary={d.diary} />}
      {d.session_test && d.session_test.assets.length > 0 && (
        <Section
          title="Das 10:30 até o fechamento de Nova York"
          meta={
            <Badge tone={d.session_test.passed_assets.length ? 'positive' : 'negative'}>
              {d.session_test.passed_assets.length ? 'Aprovado em teste pré-registrado' : 'Reprovado: não aparece no app'}
            </Badge>
          }
        >
          <p className={styles.reading}>
            Previsão de quanto o preço ainda anda da hora do plano (10:30 de Brasília) até o fechamento de Nova York, testada em 2023 a 2026 contra a média
            simples da mesma janela. Só aparece no app o ativo aprovado nas duas condições: erro pelo menos 5% menor e faixa de 80% acertando entre 75% e 85%.
          </p>
          <Table
            head={['Ativo', 'Erro menor que a média', 'Dias dentro da faixa de 80%', 'Dias testados', 'Resultado', 'Ao vivo']}
            rows={d.session_test.assets.map((a) => [
              a.label,
              pct(a.error_reduction),
              pct(a.coverage80),
              formatNumber(a.test_days, 0),
              a.passed ? 'aprovado' : 'reprovado',
              a.live && a.live.days ? `${a.live.inside80} de ${a.live.days} dias dentro da faixa` : a.passed ? 'começando' : '—',
            ])}
          />
        </Section>
      )}

      <Section title="O teste que fazemos com qualquer promessa de acerto">
        <p className={styles.reading}>
          Serviços de sinais anunciam de 66% a 95% de acerto contando como vitória qualquer toque no primeiro alvo (TP1). Fizemos o teste: entradas no
          <strong> cara ou coroa</strong>, com essa mesma regra, nos dados reais de {d.promise_period ?? '2025 a 2026'}. O "acerto" fica igual ao anunciado — e o
          resultado é negativo. Por isso o OneB nunca mostra taxa de acerto solta: mostra quanto se ganha ou perde por trade, já descontando o spread.
        </p>
        <Table
          head={['TP1 a (do stop)', 'Nasdaq: "acerto"', 'Nasdaq: resultado', 'Ouro: "acerto"', 'Ouro: resultado']}
          rows={[0.1, 0.2, 0.5, 1].map((tp) => {
            const n = d.promise_test.find((x) => x.key === 'NAS100' && x.tp1_r === tp);
            const g = d.promise_test.find((x) => x.key === 'XAUUSD' && x.tp1_r === tp);
            return [`${formatNumber(tp, 1)}R`, n ? pct(n.win_rate) : '—', n ? r3(n.mean_r) : '—', g ? pct(g.win_rate) : '—', g ? r3(g.mean_r) : '—'];
          })}
        />
        <p className={styles.callout}>Antes de pagar por sinais, peça: resultado médio por trade já descontando o spread, histórico completo sinal a sinal publicado antes do resultado, e auditor com nome.</p>
      </Section>

      {d.replay && d.replay.length > 0 && (
        <Section
          title="Simulamos um cliente seguindo sinais de compra e venda"
          meta={<Badge tone={d.replay_passed?.length ? 'positive' : 'negative'}>{d.replay_passed?.length ? 'Regra aprovada' : 'Nenhuma regra aprovada'}</Badge>}
        >
          <p className={styles.reading}>
            Um cliente abre a plataforma em 7 horários por dia (de 05:00 às 17:00 de Brasília), segue o plano do OneB (stop de 1,5 ATR, alvo 2R, 1% de
            risco, sem entrar perto de CPI, payroll e FOMC) e escolhe a direção por uma regra só de preço, sem indicadores, como fazem os serviços de
            sinais. De 2023 a 2026, começando com US$ 1.000:
          </p>
          <Table
            head={['Direção', 'Nasdaq: por trade', 'Nasdaq: saldo final', 'Ouro: por trade', 'Ouro: saldo final']}
            rows={['aleatorio', 'acompanha_24h', 'contra_1h'].map((rule) => {
              const n = d.replay!.find((x) => x.key === 'NAS100' && x.rule === rule);
              const g = d.replay!.find((x) => x.key === 'XAUUSD' && x.rule === rule);
              const cell = (x?: typeof n) => [x?.mean_r != null ? r3(x.mean_r) : '—', x?.final_balance != null ? `US$ ${formatNumber(x.final_balance, 0)}` : '—'];
              return [n?.rule_label ?? g?.rule_label ?? rule, ...cell(n), ...cell(g)];
            })}
          />
          <p className={styles.callout}>
            Nenhuma regra de direção superou o cara ou coroa no teste registrado antes do resultado (o ganho do ouro acompanhando 24 h coincide com a alta
            histórica do metal e não se repetiu em 2019–2022). Por isso a IA do OneB não diz "compre" ou "venda": diz quanto arriscar, onde fica o stop e
            a chance real de cada alvo.
          </p>
        </Section>
      )}

      {d.ai_reliability && <AiReliability r={d.ai_reliability} />}

      <Section title="O que o OneB não promete — e por quê">
        <ul className={styles.checklist}>
          {d.not_promised.map((n) => (
            <li key={n.title}>
              <XCircle {...ICON} aria-hidden className={styles.no} />
              <div>
                <strong>{n.title}</strong>
                <p className={styles.meta}>{n.detail}</p>
              </div>
            </li>
          ))}
          <li>
            <CheckCircle2 {...ICON} aria-hidden className={styles.yes} />
            <div>
              <strong>O que entregamos no lugar</strong>
              <p className={styles.meta}>Quanto o mercado deve mexer, quando o risco sobe, quanto custa, quanto operar e a chance real do seu plano — tudo medido e verificável, com dados gratuitos.</p>
            </div>
          </li>
        </ul>
      </Section>
    </div>
  );
}

function PlanLiveProof({ d }: { d: Proof }) {
  const rows = d.plan_live ?? [];
  const live = rows.filter((r) => r.part === 'live' && r.closed > 0);
  const part = live.length > 0 ? 'live' : 'retro';
  const shown = rows.filter((r) => r.part === part && r.closed > 0);
  const inside = shown.filter((r) => r.consistent).length;
  const cell = (key: string, dir: 'long' | 'short', t: number) => {
    const r = shown.find((x) => x.key === key && x.direction === dir && x.target_r === t);
    return r ? `${r.hits} de ${r.closed} (anunciado ${r.announced != null ? pct(r.announced) : '—'}) ${r.consistent ? '✓' : '✗'}` : '—';
  };
  return (
    <Section
      title="Placar ao vivo: a chance anunciada se confirma?"
      meta={<Badge tone={inside === shown.length ? 'positive' : 'negative'}>{`${inside} de ${shown.length} alvos dentro da faixa`}</Badge>}
    >
      <p className={styles.reading}>
        Todo dia útil às 10:30 de Brasília, o OneB registra por regra fixa um plano de compra e um de venda e confere depois se cada alvo veio antes do stop.
        Ninguém escolhe dia, direção ou resultado, e o plano encerrado fica gravado sem poder ser alterado.{' '}
        {part === 'live'
          ? `Placar ao vivo desde ${day(d.plan_live_start ?? '2026-10-15')}.`
          : `O placar ao vivo começa em ${day(d.plan_live_start ?? '2026-10-15')}; abaixo, a conferência dos dias anteriores (desde ${day(d.plan_live_retro_from ?? '2026-08-05')}), que não conta no placar.`}{' '}
        ✓ = a taxa anunciada cabe na faixa de 95% do que foi medido.
      </p>
      <Table
        head={['Alvo', 'Nasdaq (compra)', 'Nasdaq (venda)', 'Ouro (compra)', 'Ouro (venda)']}
        rows={[1, 2, 3].map((t) => [`${t}R`, cell('NAS100', 'long', t), cell('NAS100', 'short', t), cell('XAUUSD', 'long', t), cell('XAUUSD', 'short', t)])}
      />
    </Section>
  );
}

const DIARY_RESULT: Record<string, string> = { hit: 'alvo', stop: 'stop', expired: 'expirou', open: 'em andamento' };

/** Diário: por dia, o que o OneB disse (faixa prevista, plano das 10:30) e o que aconteceu. Nada escolhido depois. */
function Diary({ diary }: { diary: NonNullable<Proof['diary']> }) {
  const rows = diary.flatMap((day) =>
    day.assets.map((a) => {
      const r = a.range;
      const plan = (dir: 'long' | 'short') => {
        const res = a.plans?.[dir];
        return res ? `${DIARY_RESULT[res['1']]} / ${DIARY_RESULT[res['2']]}` : '—';
      };
      return [
        `${day.date.split('-').reverse().slice(0, 2).join('/')}`,
        a.label,
        r ? `${formatNumber(r.expected_pct, 2)}% (${formatNumber(r.low80_pct, 2)}–${formatNumber(r.high80_pct, 2)}%)${r.event ? ' · evento' : ''}` : '—',
        r ? `${formatNumber(r.realized_pct, 2)}% ${r.inside80 ? '✓' : '✗'}` : 'pregão em andamento',
        plan('long'),
        plan('short'),
      ];
    }),
  );
  return (
    <Section title="Diário: o que o OneB disse e o que aconteceu" meta={<span className={styles.meta}>últimos dias, sem filtro</span>}>
      <p className={styles.reading}>
        Cada linha junta o que foi registrado antes (a faixa prevista na véspera e os planos das 10:30) com o resultado. ✓ = o pregão ficou dentro da
        faixa de 80%; nos planos, o resultado do TP1 e do TP2. Dias ruins aparecem igual aos bons.
      </p>
      <DiaryTable rows={rows} />
    </Section>
  );
}

function DiaryTable({ rows }: { rows: string[][] }) {
  return (
    <div className={styles.tableWrap}>
      <table className={styles.table}>
        <thead>
          <tr>
            {['Dia', 'Ativo', 'Previsto (faixa de 80%)', 'Realizado', 'Plano de compra (TP1 / TP2)', 'Plano de venda (TP1 / TP2)'].map((h) => (
              <th key={h} scope="col">
                {h}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {rows.map((r) => (
            <tr key={r[0] + r[1]}>
              {r.map((c, i) => (
                <td key={i}>{c}</td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function AiReliability({ r }: { r: NonNullable<Proof['ai_reliability']> }) {
  const t = r.tests;
  const total = t ? t.golden.cases + t.routing.cases : 0;
  const passed = t ? t.golden.passed + t.routing.passed : 0;
  const live = r.live;
  return (
    <Section
      title="A IA também é auditada"
      meta={t ? <Badge tone={passed === total ? 'positive' : 'negative'}>{`${passed} de ${total} perguntas de teste certas`}</Badge> : undefined}
    >
      <p className={styles.reading}>
        A IA do OneB só fala o que as ferramentas mediram. Antes de cada resposta chegar até você, um verificador confere cada número contra a fonte e
        bloqueia frases de ordem ("compre", "venda agora"). Se algo não bate, a resposta é refeita a partir dos dados, sem narrativa. Quando não entende a
        pergunta, ela diz que não entendeu, em vez de responder outra coisa.
      </p>
      {t && (
        <Table
          head={['Teste', 'Resultado', 'O que verifica']}
          rows={[
            ['Perguntas com resposta esperada', `${t.golden.passed} de ${t.golden.cases}`, 'risco, plano, recusa de dar direção, estado dos setups, glossário'],
            ['Mesma pergunta de vários jeitos', `${t.routing.passed} de ${t.routing.cases}`, `gíria, erro de digitação e abreviação em ${t.routing.routes} assuntos`],
            ['Número sem fonte', `${t.golden.ungrounded_number_cases} casos`, 'todo número citado existe nos dados consultados'],
            ['Linguagem de ordem', `${t.golden.order_language_cases} casos`, 'a IA nunca manda comprar ou vender'],
          ]}
        />
      )}
      <p className={styles.meta}>
        {live.answers > 0
          ? `Em produção, últimos ${live.days} dias: ${formatNumber(live.answers, 0)} respostas, ${pct(live.verified / live.answers)} com todos os números conferidos${
              live.rated ? `; ${pct(live.useful / live.rated)} avaliadas como úteis por quem perguntou (${formatNumber(live.rated, 0)} avaliações)` : ''
            }.`
          : 'Em produção: ainda sem respostas registradas.'}
      </p>
    </Section>
  );
}

function Tile({ value, label, sub }: { value: string; label: string; sub: string }) {
  return (
    <div className={styles.tile}>
      <p className={styles.tileValue}>{value}</p>
      <p className={styles.tileLabel}>{label}</p>
      <p className={styles.tileSub}>{sub}</p>
    </div>
  );
}

function Table({ head, rows }: { head: string[]; rows: string[][] }) {
  return (
    <div className={styles.tableWrap}>
      <table className={styles.table}>
        <thead>
          <tr>
            {head.map((h) => (
              <th key={h} scope="col">
                {h}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {rows.map((r) => (
            <tr key={r[0]}>
              {r.map((c, i) => (
                <td key={i}>{c}</td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
