import { useMemo, useState } from 'react';
import { useApi } from '../../hooks/useApi';
import { AsyncContent, Button, ChipGroup, EmptyState, Section, SkeletonLines } from '../../components/ui';
import { formatNumber } from '../../lib/format';
import { brasiliaHour, CELL_BINS, binOf, nowBrasilia, nyFromBrasilia, WEEKDAYS, type HeatMetric } from '../../lib/heatmap';
import type { HeatCell, HourHeatmap } from '../../types';
import styles from './Horarios.module.css';

const METRICS: { value: HeatMetric; label: string }[] = [
  { value: 'ratio', label: 'Movimento' },
  { value: 'cost_share', label: 'Custo do spread' },
];

/** Análise › Horários: volatilidade e custo por dia e hora, medidos em 2 anos de M5. */
export function Horarios() {
  const data = useApi<HourHeatmap>('/api/analysis/hour-heatmap', { isEmpty: (d) => Object.keys(d.assets).length === 0 });
  const [asset, setAsset] = useState('NAS100');
  const [metric, setMetric] = useState<HeatMetric>('ratio');
  const [table, setTable] = useState(false);
  return (
    <AsyncContent state={data} loading={<SkeletonLines lines={10} />} empty={<EmptyState title="Mapa ainda não gerado" description="Rode scripts/build_hour_heatmap.py." />}>
      {(d) => {
        const a = d.assets[asset] ?? Object.values(d.assets)[0];
        return (
          <div className={styles.page}>
            <Section
              title="Quando o mercado se mexe — e quanto custa entrar"
              meta={<span className={styles.meta}>Medido de {fmtDate(a.period.from)} a {fmtDate(a.period.to)}</span>}
            >
              <p className={styles.reading}>
                Cada quadrado é uma hora de um dia útil. <strong>Movimento</strong> compara a amplitude típica daquela hora com a hora média do ativo (1,0x = normal).{' '}
                <strong>Custo do spread</strong> mostra quanto do movimento típico da hora o spread da corretora consome na entrada e saída. Isto descreve o
                mercado; não diz para onde o preço vai.
              </p>
              <div className={styles.controls}>
                <ChipGroup label="Ativo" value={asset} onChange={setAsset} items={Object.entries(d.assets).map(([k, v]) => ({ value: k, label: v.label }))} />
                <ChipGroup label="Métrica" value={metric} onChange={setMetric} items={METRICS} />
                <Button variant="ghost" size="sm" onClick={() => setTable((t) => !t)} aria-pressed={table}>
                  {table ? 'Ver mapa' : 'Ver tabela'}
                </Button>
              </div>
              <QuickGuide assetKey={asset} />
              {table ? <HeatTable cells={a.cells} /> : <HeatGrid key={asset} cells={a.cells} metric={metric} />}
              <Legend metric={metric} />
              <Summary cells={a.cells} label={a.label} brokerSymbol={a.broker_symbol} costSource={a.cost_source} />
            </Section>
          </div>
        );
      }}
    </AsyncContent>
  );
}

interface HoursGuide {
  assets: Record<string, { label: string; bullets: string[]; criteria: string; direction_test: { status: string; summary: string } } | null>;
}

/** Guia rápido: as conclusões do mapa em frases prontas (horário de Brasília de hoje). */
function QuickGuide({ assetKey }: { assetKey: string }) {
  const guide = useApi<HoursGuide>('/api/analysis/hours-guide');
  const g = guide.data?.assets[assetKey];
  if (!g) return null;
  return (
    <div className={styles.guide}>
      <p className={styles.guideTitle}>Guia rápido — {g.label}</p>
      <ul className={styles.guideList}>
        {g.bullets.map((b) => (
          <li key={b}>{b}</li>
        ))}
      </ul>
      <details className={styles.meta}>
        <summary>Como classificamos as horas</summary>
        <p className={styles.criteria}>{g.criteria}</p>
      </details>
    </div>
  );
}

function HeatGrid({ cells, metric }: { cells: HeatCell[]; metric: HeatMetric }) {
  const byKey = useMemo(() => new Map(cells.map((c) => [`${c.weekday}-${c.hour}`, c])), [cells]);
  const now = nowBrasilia();
  const at = (brWeekday: number, brHour: number) => {
    const ny = nyFromBrasilia(brWeekday, brHour);
    return byKey.get(`${ny.weekday}-${ny.hour}`);
  };
  const nowCell = now.weekday < 5 ? at(now.weekday, now.hour) : undefined;
  const [picked, setPicked] = useState<HeatCell | null>(nowCell ?? null);
  const hours = Array.from({ length: 24 }, (_, h) => h);
  return (
    <div className={styles.gridWrap}>
      <div className={styles.grid} role="grid" aria-label="Mapa de horários: linhas são horas de Brasília, colunas são dias úteis">
        <div className={styles.corner} aria-hidden>
          Brasília
        </div>
        {WEEKDAYS.map((w) => (
          <div key={w} className={styles.colHead} role="columnheader">
            {w}
          </div>
        ))}
        {hours.map((h) => (
          <div key={h} className={styles.row} role="row">
            <div className={styles.rowHead} role="rowheader">
              {String(h).padStart(2, '0')}h
            </div>
            {WEEKDAYS.map((w, wd) => {
              const c = at(wd, h);
              const isNow = now.weekday === wd && now.hour === h;
              if (!c) return <div key={w} className={styles.empty} role="gridcell" aria-label={`${w} ${h}h: fechado ou sem amostra`} />;
              const bin = binOf(metric, c[metric]);
              return (
                <button
                  key={w}
                  type="button"
                  role="gridcell"
                  className={[styles.cell, isNow ? styles.now : '', picked === c ? styles.picked : ''].join(' ')}
                  style={{ background: `var(--heat-${metric === 'ratio' ? 'vol' : 'cost'}-${bin + 1})` }}
                  aria-label={describe(c)}
                  onMouseEnter={() => setPicked(c)}
                  onFocus={() => setPicked(c)}
                  onClick={() => setPicked(c)}
                />
              );
            })}
          </div>
        ))}
      </div>
      <aside className={styles.readout} aria-live="polite">
        {picked ? (
          <>
            <p className={styles.readoutTitle}>
              {brLabel(picked)} (Brasília)
              {picked === nowCell ? ' · agora' : ''}
            </p>
            <dl className={styles.facts}>
              <dt>Movimento</dt>
              <dd>
                {formatNumber(picked.ratio, 1)}x a hora típica <span className={styles.meta}>({formatNumber(picked.range_bps / 100, 2)}% de amplitude)</span>
              </dd>
              <dt>Custo do spread</dt>
              <dd>
                {formatNumber(picked.cost_share * 100, 1)}% do movimento da hora
              </dd>
              <dt>Amostra</dt>
              <dd>{picked.hours} horas</dd>
            </dl>
          </>
        ) : (
          <p className={styles.meta}>Passe o mouse ou toque num quadrado para ver os números.</p>
        )}
      </aside>
    </div>
  );
}

function describe(c: HeatCell) {
  return `${brLabel(c)}: movimento ${formatNumber(c.ratio, 1)}x o típico; spread consome ${formatNumber(c.cost_share * 100, 1)}% do movimento`;
}

function Legend({ metric }: { metric: HeatMetric }) {
  return (
    <ul className={styles.legend} aria-label="Legenda">
      {CELL_BINS[metric].map((b, i) => (
        <li key={b.label}>
          <span className={styles.swatch} style={{ background: `var(--heat-${metric === 'ratio' ? 'vol' : 'cost'}-${i + 1})` }} aria-hidden />
          {b.label}
        </li>
      ))}
      <li>
        <span className={[styles.swatch, styles.nowSwatch].join(' ')} aria-hidden />
        hora atual
      </li>
    </ul>
  );
}

function HeatTable({ cells }: { cells: HeatCell[] }) {
  const sorted = [...cells].sort((a, b) => a.weekday - b.weekday || a.hour - b.hour);
  return (
    <div className={styles.tableWrap}>
      <table className={styles.table}>
        <thead>
          <tr>
            <th scope="col" colSpan={2}>Dia e hora (Brasília)</th>
            <th scope="col">Movimento</th>
            <th scope="col">Amplitude</th>
            <th scope="col">Custo do spread</th>
          </tr>
        </thead>
        <tbody>
          {sorted.map((c) => (
            <tr key={`${c.weekday}-${c.hour}`}>
              <td colSpan={2}>{brLabel(c)}</td>
              <td>{formatNumber(c.ratio, 1)}x</td>
              <td>{formatNumber(c.range_bps / 100, 2)}%</td>
              <td>{formatNumber(c.cost_share * 100, 1)}%</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function Summary({ cells, label, brokerSymbol, costSource }: { cells: HeatCell[]; label: string; brokerSymbol: string | null; costSource: string }) {
  const busiest = [...cells].sort((a, b) => b.ratio - a.ratio).slice(0, 3);
  const quiet = [...cells].sort((a, b) => a.ratio - b.ratio).slice(0, 3);
  const cheapest = [...cells].sort((a, b) => a.cost_share - b.cost_share)[0];
  const priciest = [...cells].sort((a, b) => b.cost_share - a.cost_share)[0];
  const at = (c: HeatCell) => brLabel(c).split('–')[0].toLowerCase();
  return (
    <ul className={styles.summary}>
      <li>
        <strong>Mais movimento em {label}:</strong> {busiest.map((c) => `${at(c)} (${formatNumber(c.ratio, 1)}x)`).join(', ')}.
      </li>
      <li>
        <strong>Mais parado:</strong> {quiet.map((c) => `${at(c)} (${formatNumber(c.ratio, 1)}x)`).join(', ')}. Hora parada não é hora segura: o spread pesa mais.
      </li>
      <li>
        <strong>Custo{brokerSymbol ? ` no ${brokerSymbol}` : ''}:</strong> de {formatNumber(cheapest.cost_share * 100, 1)}% ({at(cheapest)}) a{' '}
        {formatNumber(priciest.cost_share * 100, 1)}% ({at(priciest)}) do movimento da hora. Fonte do spread: {costSource}.
      </li>
      <li className={styles.meta}>
        Horas em Brasília pelo horário de verão americano em vigor hoje; quando ele muda, a abertura de Nova York anda 1 hora no relógio de Brasília.
      </li>
    </ul>
  );
}

function fmtDate(iso: string) {
  return iso.split('-').reverse().join('/');
}

/** Rótulo em Brasília de uma célula guardada em hora de NY (23h de NY pode ser 00h do dia seguinte). */
function brLabel(c: HeatCell) {
  const h = brasiliaHour(c.hour);
  const day = WEEKDAYS[h < c.hour ? c.weekday + 1 : c.weekday] ?? 'Sáb';
  return `${day} ${String(h).padStart(2, '0')}h–${String((h + 1) % 24).padStart(2, '0')}h`;
}
