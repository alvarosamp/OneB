import { useState } from 'react';
import { ClipboardCheck, Trash2 } from 'lucide-react';
import { api } from '../../api/client';
import { useApi } from '../../hooks/useApi';
import { AsyncContent, Badge, Button, ChipGroup, EmptyState, ICON, Input, Section, SkeletonLines, Textarea } from '../../components/ui';
import { formatNumber } from '../../lib/format';
import styles from './Sinal.module.css';

interface TargetEval {
  price: number;
  distance: number;
  target_r: number;
  p_target: number | null;
  ci95: [number, number] | null;
  p_stop: number;
  p_open_24h: number;
  mean_r: number;
  breakeven_p: number;
  n: number;
}

export interface SignalEvaluation {
  ok: boolean;
  error?: string;
  asset?: string;
  label?: string;
  symbol?: string;
  signal?: { direction: 'long' | 'short'; entry: number; stop: number; targets: number[]; stop_distance: number };
  stop_atr?: number;
  targets?: TargetEval[];
  sample?: { n: number; from: string | null; to: string | null };
  spread_share?: number | null;
  warnings?: string[];
  sizing?: { risk_money: number; lots: number; below_minimum: boolean; min_lot_risk: number; actual_risk: number } | null;
  min_lot?: { volume_min: number; risk_usd: number; balance_1pct: number };
  verdict?: string;
  method?: string;
  tracked_id?: number;
}

interface SignalRow {
  id: number;
  source: string;
  label: string;
  direction: 'long' | 'short';
  entry: number;
  stop: number;
  targets: number[];
  target_r: number[];
  base_p: (number | null)[];
  created_at: string;
  results: ('hit' | 'stop' | 'expired' | 'open')[];
  result_r: (number | null)[];
}

interface SignalList {
  signals: SignalRow[];
  scoreboard: {
    source: string;
    signals: number;
    open: number;
    targets: { target: number; closed: number; hits: number; rate: number | null; ci95: [number, number] | null; expected_rate: number | null; mean_r: number | null }[];
  }[];
  note: string;
}

const RISKS = [
  { value: '0.5', label: '0,5%' },
  { value: '1', label: '1%' },
  { value: '2', label: '2%' },
];
const RESULT: Record<string, string> = { hit: 'alvo', stop: 'stop', expired: 'expirou', open: 'em andamento' };
const pct = (x: number | null | undefined) => (x == null ? '—' : `${formatNumber(x * 100, 0)}%`);
const sgnR = (x: number | null | undefined) => (x == null ? '—' : `${x >= 0 ? '+' : ''}${formatNumber(x, 2)}R`);
const px = (x: number) => formatNumber(x, x >= 100 ? 2 : x >= 1 ? 4 : 5);
const dist = (x: number) => formatNumber(x, x >= 1 ? 2 : 5);
const PLACEHOLDER = 'Cole o sinal como você recebeu. Ex.:\nOURO COMPRA 4180\nSL 4170\nTP1 4185  TP2 4190  TP3 4200';

/** Análise › Avaliar sinal: mede a chance real de cada alvo de um sinal recebido e acompanha a fonte num placar. */
export function Sinal() {
  const [text, setText] = useState('');
  const [source, setSource] = useState('');
  const [balance, setBalance] = useState('');
  const [risk, setRisk] = useState('1');
  const [track, setTrack] = useState(true);
  const [busy, setBusy] = useState(false);
  const [result, setResult] = useState<SignalEvaluation | null>(null);
  const [error, setError] = useState<string | null>(null);
  const list = useApi<SignalList>('/api/signals', { isEmpty: (d) => d.signals.length === 0 });

  async function evaluate() {
    setBusy(true);
    setError(null);
    try {
      const b = Number(balance.replace(/\./g, '').replace(',', '.'));
      const res = await api.post<SignalEvaluation>('/api/signals/evaluate', {
        text,
        source: source.trim(),
        balance: b > 0 ? b : null,
        risk_pct: b > 0 ? Number(risk) : null,
        track,
      });
      setResult(res);
      if (res.ok && res.tracked_id) list.retry();
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Não foi possível avaliar agora.');
    } finally {
      setBusy(false);
    }
  }

  async function remove(id: number) {
    await api.delete(`/api/signals/${id}`);
    list.retry();
  }

  return (
    <div className={styles.page}>
      <Section title="Avaliar um sinal" meta={<span className={styles.meta}>a chance real de cada alvo, medida — não prometida</span>}>
        <p className={styles.lead}>
          Cole o sinal que você recebeu (de qualquer serviço). O OneB lê ativo, compra ou venda, entrada, stop e alvos e mede, com esse stop e esses alvos, quantas
          vezes o alvo veio antes do stop nos últimos 60 dias, já com o spread. Não diz se o serviço acerta a direção: isso o placar mostra com o tempo.
        </p>
        <Textarea label="Sinal" rows={6} placeholder={PLACEHOLDER} value={text} onChange={(e) => setText(e.target.value)} />
        <div className={styles.controls}>
          <Input label="De onde veio (ex.: VTX)" value={source} onChange={(e) => setSource(e.target.value)} maxLength={64} />
          <Input label="Saldo no MT5 (US$, opcional)" inputMode="decimal" value={balance} onChange={(e) => setBalance(e.target.value)} />
          <ChipGroup label="Risco por operação" value={risk} onChange={setRisk} items={RISKS} />
        </div>
        <label className={styles.check}>
          <input type="checkbox" checked={track} onChange={(e) => setTrack(e.target.checked)} /> Acompanhar este sinal no placar da fonte
        </label>
        <div>
          <Button variant="primary" icon={<ClipboardCheck {...ICON} />} loading={busy} disabled={text.trim().length < 5} onClick={() => void evaluate()}>
            Avaliar
          </Button>
        </div>
        {error && <p className={styles.error}>{error}</p>}
        {result && (result.ok ? <EvaluationCard r={result} /> : <p className={styles.error}>{result.error}</p>)}
      </Section>

      <Section title="Placar das fontes" meta={<span className={styles.meta}>cada sinal conferido depois, sem filtro</span>}>
        <AsyncContent
          state={list}
          loading={<SkeletonLines lines={4} />}
          empty={<EmptyState title="Nenhum sinal acompanhado ainda" description="Avalie um sinal com 'Acompanhar' marcado para começar o placar da fonte." />}
          errorTitle="Placar indisponível"
        >
          {(d) => <Scoreboard d={d} onRemove={remove} />}
        </AsyncContent>
      </Section>
    </div>
  );
}

function EvaluationCard({ r }: { r: SignalEvaluation }) {
  const s = r.signal!;
  const side = s.direction === 'long' ? 'Compra' : 'Venda';
  return (
    <div className={styles.card}>
      <p className={styles.cardTitle}>
        {side} · {r.label} <span className={styles.meta}>({r.symbol})</span>
      </p>
      <p className={styles.meta}>
        Entrada {px(s.entry)} · stop {px(s.stop)} ({dist(s.stop_distance)} de distância, {formatNumber(r.stop_atr ?? 0, 2)} vez o movimento típico de 1 hora)
      </p>
      <div className={styles.tableWrap}>
        <table className={styles.table}>
          <thead>
            <tr>
              <th scope="col">Alvo</th>
              <th scope="col">Preço</th>
              <th scope="col">Ganho/risco</th>
              <th scope="col">Chance real antes do stop</th>
              <th scope="col">Precisa para empatar</th>
              <th scope="col">Resultado médio</th>
            </tr>
          </thead>
          <tbody>
            {r.targets!.map((t, i) => {
              const below = t.p_target != null && t.p_target < t.breakeven_p;
              return (
                <tr key={i}>
                  <td>TP{i + 1}</td>
                  <td>{px(t.price)}</td>
                  <td>{formatNumber(t.target_r, 2)}R</td>
                  <td>
                    <strong>{pct(t.p_target)}</strong>
                    {t.ci95 && <span className={styles.meta}> ({pct(t.ci95[0])}–{pct(t.ci95[1])})</span>}
                  </td>
                  <td className={below ? styles.no : styles.yes}>{pct(t.breakeven_p)}</td>
                  <td className={t.mean_r < 0 ? styles.no : styles.yes}>{sgnR(t.mean_r)}</td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
      <p className={styles.verdict}>{r.verdict}</p>
      {r.sizing ? (
        <p className={styles.meta}>
          {r.sizing.below_minimum
            ? `Com o seu saldo e risco, nem o lote mínimo cabe: ele arriscaria US$ ${formatNumber(r.sizing.min_lot_risk, 2)}, acima dos US$ ${formatNumber(r.sizing.risk_money, 2)} do seu limite. Não opere este sinal com esse saldo.`
            : `Lote para o seu risco: ${formatNumber(r.sizing.lots, 2)} (arrisca US$ ${formatNumber(r.sizing.actual_risk, 2)}).`}
        </p>
      ) : (
        r.min_lot && (
          <p className={styles.meta}>
            O menor lote ({formatNumber(r.min_lot.volume_min, 2)}) arrisca US$ {formatNumber(r.min_lot.risk_usd, 2)} neste stop: para isso ser 1% da conta, o saldo precisa
            ser de US$ {formatNumber(r.min_lot.balance_1pct, 0)}.
          </p>
        )
      )}
      {r.warnings && r.warnings.length > 0 && (
        <ul className={styles.warnings}>
          {r.warnings.map((w) => (
            <li key={w}>{w}</li>
          ))}
        </ul>
      )}
      <p className={styles.meta}>
        {r.method} {r.sample ? `Amostra: ${formatNumber(r.sample.n, 0)} entradas, cada uma contada como compra e como venda.` : ''}
        {r.tracked_id ? ' Sinal gravado: o resultado aparece no placar abaixo em até 24 h.' : ''}
      </p>
    </div>
  );
}

function Scoreboard({ d, onRemove }: { d: SignalList; onRemove: (id: number) => void }) {
  return (
    <>
      {d.scoreboard.map((s) => {
        const tp1 = s.targets[0];
        const better = tp1 && tp1.rate != null && tp1.ci95 && tp1.expected_rate != null && tp1.ci95[0] > tp1.expected_rate;
        return (
          <div key={s.source} className={styles.source}>
            <p className={styles.cardTitle}>
              {s.source}{' '}
              <Badge tone={better ? 'positive' : 'neutral'}>
                {tp1 && tp1.closed ? `TP1: ${tp1.hits} de ${tp1.closed} (${pct(tp1.rate)}) · esperado ${pct(tp1.expected_rate)}` : 'aguardando resultados'}
              </Badge>
            </p>
            <p className={styles.meta}>
              {s.signals} {s.signals === 1 ? 'sinal' : 'sinais'}, {s.open} em andamento.
              {tp1 && tp1.mean_r != null ? ` Saindo no TP1: ${sgnR(tp1.mean_r)} por trade.` : ''}
              {tp1 && tp1.closed >= 30
                ? better
                  ? ' Acima da taxa-base com margem: sinal de vantagem real (continue acompanhando).'
                  : ' Dentro ou abaixo da taxa-base: até agora, nada que uma entrada qualquer não fizesse.'
                : ' Com menos de 30 sinais encerrados, ainda é cedo para concluir.'}
            </p>
          </div>
        );
      })}
      <div className={styles.tableWrap}>
        <table className={styles.table}>
          <thead>
            <tr>
              <th scope="col">Quando</th>
              <th scope="col">Fonte</th>
              <th scope="col">Sinal</th>
              <th scope="col">Alvos</th>
              <th scope="col" aria-label="Remover" />
            </tr>
          </thead>
          <tbody>
            {d.signals.map((r) => (
              <tr key={r.id}>
                <td>{new Date(r.created_at).toLocaleString('pt-BR', { day: '2-digit', month: '2-digit', hour: '2-digit', minute: '2-digit', timeZone: 'America/Sao_Paulo' })}</td>
                <td>{r.source}</td>
                <td>
                  {r.direction === 'long' ? 'Compra' : 'Venda'} {r.label} {px(r.entry)} · stop {px(r.stop)}
                </td>
                <td>{r.results.map((x, i) => `TP${i + 1} ${RESULT[x]}`).join(' · ')}</td>
                <td>
                  <Button variant="ghost" size="sm" iconOnly icon={<Trash2 {...ICON} />} aria-label="Remover do placar" onClick={() => void onRemove(r.id)} />
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <p className={styles.meta}>{d.note}</p>
    </>
  );
}
