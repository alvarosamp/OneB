import { useEffect, useMemo, useRef, type CSSProperties } from 'react';
import {
  BarController,
  BarElement,
  Chart,
  LinearScale,
  LineController,
  LineElement,
  PointElement,
  Tooltip,
  type ChartConfiguration,
  type Plugin,
  type ScriptableContext,
} from 'chart.js';
import { CandlestickController, CandlestickElement } from 'chartjs-chart-financial';
import { useTheme } from '../../context/ThemeContext';
import { lastValue, type Bar } from '../../lib/indicators';
import { prepareChart } from '../../lib/chartData';
import { type Timeframe } from '../../lib/timeframes';
import { formatNumber } from '../../lib/format';
import type { ChartData } from '../../types';
import styles from './ChartPanel.module.css';

Chart.register(BarController, BarElement, LineController, LineElement, PointElement, LinearScale, Tooltip, CandlestickController, CandlestickElement);

export interface PriceLevel {
  label: string;
  value: number;
  /** Nome de token CSS (ex.: '--chart-level-support'). */
  colorVar: string;
}

interface ChartPanelProps {
  data: ChartData;
  timeframe: Timeframe;
  /** Painéis de indicador abaixo do preço (eixo X sincronizado). */
  panels?: ('volume' | 'rsi' | 'macd')[];
  levels?: PriceLevel[];
  height?: number;
  /** Cor de série do ativo (ex.: ouro usa --series-gold) — só para a linha do preço no modo linha. */
  label?: string;
}

const AXIS_WIDTH = 64;

function cssVar(name: string): string {
  return getComputedStyle(document.documentElement).getPropertyValue(name).trim();
}

function tickFormatter(bars: Bar[], tf: Timeframe) {
  const fmt = new Intl.DateTimeFormat(
    'pt-BR',
    tf.id === '1D'
      ? { hour: '2-digit', minute: '2-digit', timeZone: 'America/New_York' }
      : tf.intraday
        ? { day: '2-digit', month: '2-digit', timeZone: 'America/New_York' }
        : { day: '2-digit', month: 'short', timeZone: 'America/New_York' },
  );
  return (value: number | string) => {
    const b = bars[Math.round(Number(value))];
    return b ? fmt.format(b.t).replace('.', '') : '';
  };
}

/** Linha vertical compartilhada entre os painéis (crosshair sincronizado). */
function crosshairPlugin(shared: { index: number | null; charts: Chart[] }, color: string): Plugin {
  return {
    id: 'onebCrosshair',
    afterDatasetsDraw(chart) {
      if (shared.index === null) return;
      const x = chart.scales.x.getPixelForValue(shared.index);
      const { top, bottom } = chart.chartArea;
      const ctx = chart.ctx;
      ctx.save();
      ctx.strokeStyle = color;
      ctx.lineWidth = 1;
      ctx.setLineDash([3, 3]);
      ctx.beginPath();
      ctx.moveTo(x, top);
      ctx.lineTo(x, bottom);
      ctx.stroke();
      ctx.restore();
    },
    afterEvent(chart, args) {
      const e = args.event;
      if (e.type === 'mouseout') {
        shared.index = null;
      } else if (e.type === 'mousemove' && e.x !== null) {
        const v = chart.scales.x.getValueForPixel(e.x);
        shared.index = v === undefined ? null : Math.round(v);
      } else {
        return;
      }
      shared.charts.forEach((c) => c !== chart && c.draw());
      args.changed = true;
    },
  };
}

export function ChartPanel({ data, timeframe, panels = ['volume'], levels = [], height = 360, label }: ChartPanelProps) {
  const { theme } = useTheme();
  const prepared = useMemo(() => prepareChart(data, timeframe), [data, timeframe]);
  const priceRef = useRef<HTMLCanvasElement>(null);
  const panelRefs = useRef<Record<string, HTMLCanvasElement | null>>({});

  useEffect(() => {
    const { bars } = prepared;
    if (bars.length === 0 || !priceRef.current) return;
    const c = {
      up: cssVar('--chart-up'),
      down: cssVar('--chart-down'),
      grid: cssVar('--chart-grid'),
      axis: cssVar('--chart-axis'),
      text: cssVar('--chart-text'),
      cross: cssVar('--chart-crosshair'),
      ema20: cssVar('--chart-ema-fast'),
      ema200: cssVar('--chart-ema-slow'),
      vwap: cssVar('--chart-vwap'),
      volume: cssVar('--chart-volume'),
      rsi: cssVar('--chart-rsi'),
      macd: cssVar('--chart-macd'),
      signal: cssVar('--chart-macd-signal'),
      histUp: cssVar('--chart-macd-hist-up'),
      histDown: cssVar('--chart-macd-hist-down'),
      band: cssVar('--chart-band'),
      tooltipBg: cssVar('--surface-raised'),
      tooltipText: cssVar('--text-primary'),
      tooltipBorder: cssVar('--border-strong'),
      font: cssVar('--font-sans'),
    };
    const shared: { index: number | null; charts: Chart[] } = { index: null, charts: [] };
    const crosshair = crosshairPlugin(shared, c.cross);
    const n = bars.length;
    const fmtTick = tickFormatter(bars, timeframe);
    const xs = bars.map((_, i) => i);
    const line = (values: (number | null)[]) => values.map((y, i) => ({ x: xs[i], y }));
    const baseFont = { family: c.font, size: 11 };

    const xScale = (showTicks: boolean) => ({
      type: 'linear' as const,
      min: -0.5,
      max: n - 0.5,
      offset: false,
      grid: { color: c.grid, drawTicks: false },
      border: { color: c.axis },
      ticks: { display: showTicks, color: c.text, font: baseFont, maxTicksLimit: 8, maxRotation: 0, callback: fmtTick },
    });
    const yScale = (extra: object = {}) => ({
      position: 'right' as const,
      grid: { color: c.grid, drawTicks: false },
      border: { color: c.axis },
      ticks: { color: c.text, font: baseFont, maxTicksLimit: 6, padding: 6, callback: (v: number | string) => formatNumber(Number(v), 2) },
      afterFit: (scale: { width: number }) => {
        scale.width = AXIS_WIDTH;
      },
      ...extra,
    });
    const tooltip = {
      mode: 'index' as const,
      intersect: false,
      backgroundColor: c.tooltipBg,
      titleColor: c.tooltipText,
      bodyColor: c.tooltipText,
      borderColor: c.tooltipBorder,
      borderWidth: 1,
      padding: 8,
      displayColors: false,
      titleFont: { ...baseFont, weight: 600 as const },
      bodyFont: baseFont,
      callbacks: {
        title: (items: { parsed: { x: number | null } }[]) => {
          const b = bars[items[0]?.parsed.x ?? 0];
          return b
            ? new Intl.DateTimeFormat('pt-BR', {
                day: '2-digit',
                month: '2-digit',
                hour: timeframe.intraday ? '2-digit' : undefined,
                minute: timeframe.intraday ? '2-digit' : undefined,
                timeZone: 'America/New_York',
              }).format(b.t) + (timeframe.intraday ? ' (NY)' : '')
            : '';
        },
      },
    };
    const common = {
      animation: false as const,
      maintainAspectRatio: false,
      responsive: true,
      interaction: { mode: 'index' as const, intersect: false },
      layout: { padding: { left: 0, right: 0 } },
    };

    const priceDatasets: ChartConfiguration['data']['datasets'] = [
      {
        type: 'candlestick',
        label: 'Preço',
        data: bars.map((b, i) => ({ x: xs[i], o: b.o, h: b.h, l: b.l, c: b.c })),
        backgroundColors: { up: c.up, down: c.down, unchanged: c.text },
        borderColors: { up: c.up, down: c.down, unchanged: c.text },
      } as never,
      { type: 'line', label: 'EMA 20', data: line(prepared.ema20), borderColor: c.ema20, borderWidth: 1.25, pointRadius: 0, spanGaps: true },
    ];
    if (prepared.hasEma200) {
      priceDatasets.push({ type: 'line', label: 'EMA 200', data: line(prepared.ema200), borderColor: c.ema200, borderWidth: 1.25, pointRadius: 0, spanGaps: true });
    }
    if (prepared.vwap) {
      priceDatasets.push({ type: 'line', label: 'VWAP', data: line(prepared.vwap), borderColor: c.vwap, borderWidth: 1, borderDash: [4, 3], pointRadius: 0, spanGaps: false });
    }
    for (const lvl of levels) {
      priceDatasets.push({
        type: 'line',
        label: lvl.label,
        data: [
          { x: 0, y: lvl.value },
          { x: n - 1, y: lvl.value },
        ],
        borderColor: cssVar(lvl.colorVar),
        borderWidth: 1,
        borderDash: [6, 4],
        pointRadius: 0,
      });
    }

    const price = new Chart(priceRef.current, {
      type: 'candlestick' as never,
      data: { datasets: priceDatasets },
      options: {
        ...common,
        scales: { x: xScale(panels.length === 0), y: yScale() },
        plugins: {
          legend: { display: false },
          tooltip: {
            ...tooltip,
            callbacks: {
              ...tooltip.callbacks,
              label: (item: { dataset: { label?: string }; raw: unknown }) => {
                const raw = item.raw as { o?: number; h?: number; l?: number; c?: number; y?: number | null };
                if (raw.o !== undefined) {
                  return [`Abertura ${formatNumber(raw.o)}`, `Máxima ${formatNumber(raw.h)}`, `Mínima ${formatNumber(raw.l)}`, `Fechamento ${formatNumber(raw.c)}`];
                }
                return raw.y === null || raw.y === undefined ? '' : `${item.dataset.label} ${formatNumber(raw.y)}`;
              },
            },
          },
        },
      } as never,
      plugins: [crosshair],
    });
    shared.charts.push(price);

    const made: Chart[] = [price];
    for (const panel of panels) {
      const canvas = panelRefs.current[panel];
      if (!canvas) continue;
      const isLast = panel === panels[panels.length - 1];
      let cfg: ChartConfiguration;
      if (panel === 'volume') {
        cfg = {
          type: 'bar',
          data: {
            datasets: [
              {
                label: 'Volume',
                data: bars.map((b, i) => ({ x: xs[i], y: b.v })),
                backgroundColor: c.volume,
                barPercentage: 1,
                categoryPercentage: 0.9,
              },
            ],
          },
          options: {
            ...common,
            scales: {
              x: xScale(isLast),
              y: yScale({ ticks: { color: c.text, font: baseFont, maxTicksLimit: 2, callback: (v: number | string) => compact(Number(v)) } }),
            },
            plugins: { legend: { display: false }, tooltip: { ...tooltip, callbacks: { ...tooltip.callbacks, label: (i: { raw: unknown }) => `Volume ${compact((i.raw as { y: number }).y)}` } } },
          } as never,
          plugins: [crosshair],
        };
      } else if (panel === 'rsi') {
        cfg = {
          type: 'line',
          data: {
            datasets: [
              { label: 'RSI 14', data: line(prepared.rsi), borderColor: c.rsi, borderWidth: 1.25, pointRadius: 0, spanGaps: true },
              { label: '70', data: [{ x: 0, y: 70 }, { x: n - 1, y: 70 }], borderColor: c.axis, borderWidth: 1, borderDash: [3, 3], pointRadius: 0 },
              { label: '30', data: [{ x: 0, y: 30 }, { x: n - 1, y: 30 }], borderColor: c.axis, borderWidth: 1, borderDash: [3, 3], pointRadius: 0 },
            ],
          },
          options: {
            ...common,
            scales: { x: xScale(isLast), y: yScale({ min: 0, max: 100, ticks: { color: c.text, font: baseFont, stepSize: 30, callback: (v: number | string) => String(v) } }) },
            plugins: {
              legend: { display: false },
              tooltip: { ...tooltip, filter: (i: { datasetIndex: number }) => i.datasetIndex === 0, callbacks: { ...tooltip.callbacks, label: (i: { raw: unknown }) => `RSI ${formatNumber((i.raw as { y: number }).y, 1)}` } },
            },
          } as never,
          plugins: [crosshair],
        };
      } else {
        const hist = prepared.macd.map((m, i) => (m === null || prepared.signal[i] === null ? null : m - (prepared.signal[i] as number)));
        cfg = {
          type: 'bar',
          data: {
            datasets: [
              {
                type: 'bar',
                label: 'Histograma',
                data: line(hist),
                backgroundColor: (ctx: ScriptableContext<'bar'>) => ((ctx.raw as { y: number | null })?.y ?? 0) >= 0 ? c.histUp : c.histDown,
                barPercentage: 1,
                categoryPercentage: 0.9,
              },
              { type: 'line', label: 'MACD', data: line(prepared.macd), borderColor: c.macd, borderWidth: 1.25, pointRadius: 0, spanGaps: true },
              { type: 'line', label: 'Sinal', data: line(prepared.signal), borderColor: c.signal, borderWidth: 1.25, pointRadius: 0, spanGaps: true },
            ],
          } as never,
          options: {
            ...common,
            scales: { x: xScale(isLast), y: yScale({ ticks: { color: c.text, font: baseFont, maxTicksLimit: 3, callback: (v: number | string) => formatNumber(Number(v), 1) } }) },
            plugins: {
              legend: { display: false },
              tooltip: {
                ...tooltip,
                callbacks: {
                  ...tooltip.callbacks,
                  label: (i: { dataset: { label?: string }; raw: unknown }) => {
                    const y = (i.raw as { y: number | null }).y;
                    return y === null ? '' : `${i.dataset.label} ${formatNumber(y, 2)}`;
                  },
                },
              },
            },
          } as never,
          plugins: [crosshair],
        };
      }
      const chart = new Chart(canvas, cfg);
      shared.charts.push(chart);
      made.push(chart);
    }
    return () => made.forEach((ch) => ch.destroy());
  }, [prepared, panels, levels, theme, timeframe]);

  const { bars } = prepared;
  const lastBar = bars[bars.length - 1];
  const ariaLabel = lastBar
    ? `Gráfico de candles${label ? ` de ${label}` : ''}, ${timeframe.label}, ${bars.length} candles. Último fechamento ${formatNumber(lastBar.c)}.`
    : 'Gráfico sem dados';

  return (
    <div className={styles.panel}>
      <div className={styles.legend} aria-hidden="true">
        <LegendItem colorVar="--chart-ema-fast" label="EMA 20" value={lastValue(prepared.ema20)} />
        {prepared.hasEma200 ? (
          <LegendItem colorVar="--chart-ema-slow" label="EMA 200" value={lastValue(prepared.ema200)} />
        ) : (
          <span className={styles.legendNote}>EMA 200 precisa de 200 candles</span>
        )}
        {prepared.vwap && <LegendItem colorVar="--chart-vwap" label="VWAP" value={lastValue(prepared.vwap)} dashed />}
        {levels.map((l) => (
          <LegendItem key={l.label} colorVar={l.colorVar} label={l.label} value={l.value} dashed />
        ))}
      </div>
      <div className={styles.price} style={{ '--chart-h': `${height}px` } as CSSProperties}>
        <canvas ref={priceRef} role="img" aria-label={ariaLabel} />
      </div>
      {panels.map((p) => (
        <div key={p} className={p === 'volume' ? styles.volume : styles.indicator}>
          {p !== 'volume' && (
            <span className={styles.panelLabel}>
              {p === 'rsi' ? `RSI 14 ${formatNumber(lastValue(prepared.rsi), 1)}` : `MACD ${formatNumber(lastValue(prepared.macd), 2)}`}
            </span>
          )}
          <canvas
            ref={(el) => {
              panelRefs.current[p] = el;
            }}
            role="img"
            aria-label={p === 'volume' ? 'Volume' : p === 'rsi' ? 'RSI de 14 períodos' : 'MACD e linha de sinal'}
          />
        </div>
      ))}
    </div>
  );
}

function LegendItem({ colorVar, label, value, dashed }: { colorVar: string; label: string; value: number | null; dashed?: boolean }) {
  return (
    <span className={styles.legendItem}>
      <i className={dashed ? styles.swatchDashed : styles.swatch} style={{ color: `var(${colorVar})` }} />
      {label}
      <span className="num">{formatNumber(value)}</span>
    </span>
  );
}

function compact(v: number): string {
  if (!Number.isFinite(v)) return '';
  return new Intl.NumberFormat('pt-BR', { notation: 'compact', maximumFractionDigits: 1 }).format(v);
}
