import { useEffect, useRef } from 'react';
import { useTheme } from '../context/ThemeContext';
import {
  Chart,
  BarController,
  BarElement,
  LineController,
  LineElement,
  PointElement,
  LinearScale,
  TimeScale,
  Tooltip,
  Legend,
  type ChartTypeRegistry,
} from 'chart.js';
import 'chartjs-adapter-date-fns';
import { CandlestickController, CandlestickElement } from 'chartjs-chart-financial';
import type { ChartData } from '../types';

Chart.register(
  BarController,
  BarElement,
  LineController,
  LineElement,
  PointElement,
  LinearScale,
  TimeScale,
  Tooltip,
  Legend,
  CandlestickController,
  CandlestickElement,
);

function buildCandles(data: ChartData) {
  return data.timestamps
    .map((ts, i) => ({
      x: new Date(ts).getTime(),
      o: data.open[i],
      h: data.high[i],
      l: data.low[i],
      c: data.close[i],
    }))
    .filter((c) => c.o !== null && c.h !== null && c.l !== null && c.c !== null) as {
    x: number;
    o: number;
    h: number;
    l: number;
    c: number;
  }[];
}

function buildLinePoints(timestamps: string[], values: (number | null)[]) {
  return timestamps.map((ts, i) => ({ x: new Date(ts).getTime(), y: values[i] }));
}

function buildLevelPoints(timestamps: string[], level: number) {
  return timestamps.map((ts) => ({ x: new Date(ts).getTime(), y: level }));
}

function buildVolumePoints(timestamps: string[], values: (number | null)[]) {
  return timestamps.map((ts, i) => ({ x: new Date(ts).getTime(), y: values[i] ?? 0 }));
}

interface PriceLevel {
  label: string;
  value: number;
  color: string;
}

interface CandlestickChartProps {
  data: ChartData;
  symbol: string;
  levels?: PriceLevel[];
  compact?: boolean;
}

export function CandlestickChart({ data, symbol, levels = [], compact = false }: CandlestickChartProps) {
  const { theme } = useTheme();
  const priceRef = useRef<HTMLCanvasElement>(null);
  const volumeRef = useRef<HTMLCanvasElement>(null);
  const rsiRef = useRef<HTMLCanvasElement>(null);
  const macdRef = useRef<HTMLCanvasElement>(null);
  const chartsRef = useRef<{ price?: Chart; volume?: Chart; rsi?: Chart; macd?: Chart }>({});

  useEffect(() => {
    const charts = chartsRef.current;
    const candles = buildCandles(data);

    // Cores lidas das CSS vars do tema (--chart-*), para acompanhar o toggle claro/escuro
    const style = getComputedStyle(document.documentElement);
    const cssVar = (name: string) => style.getPropertyValue(name).trim();
    const gridColor = cssVar(compact ? '--chart-grid-compact' : '--chart-grid');
    const textColor = cssVar('--chart-text');
    const upColor = cssVar('--chart-up');
    const downColor = cssVar('--chart-down');
    const emaFastColor = cssVar('--chart-ema-fast');
    const emaSlowColor = cssVar('--chart-ema-slow');
    const volumeColor = cssVar('--chart-volume');
    const rsiColor = cssVar('--chart-rsi');
    const macdColor = cssVar('--chart-macd');
    const macdSignalColor = cssVar('--chart-macd-signal');

    if (priceRef.current) {
      charts.price?.destroy();
      charts.price = new Chart(priceRef.current, {
        type: 'candlestick' as keyof ChartTypeRegistry,
        data: {
          datasets: [
            { 
              label: symbol, 
              data: candles,
              color: { up: upColor, down: downColor, unchanged: textColor }
            } as never,
            {
              type: 'line',
              label: 'EMA9',
              data: buildLinePoints(data.timestamps, data.ema_fast),
              borderColor: emaFastColor,
              pointRadius: 0,
              borderWidth: 1,
            },
            {
              type: 'line',
              label: 'EMA21',
              data: buildLinePoints(data.timestamps, data.ema_slow),
              borderColor: emaSlowColor,
              pointRadius: 0,
              borderWidth: 1,
            },
            ...levels.map((level) => ({
              type: 'line' as const,
              label: level.label,
              data: buildLevelPoints(data.timestamps, level.value),
              borderColor: level.color,
              pointRadius: 0,
              borderWidth: 1,
              borderDash: [6, 6],
            })),
          ],
        },
        options: {
          animation: false,
          maintainAspectRatio: false,
          scales: {
            x: { type: 'time', grid: { color: gridColor }, ticks: { color: textColor } },
            y: { grid: { color: gridColor }, ticks: { color: textColor } },
          },
          plugins: { legend: { labels: { color: textColor } } },
        },
      });
    }

    if (volumeRef.current) {
      charts.volume?.destroy();
      charts.volume = new Chart(volumeRef.current, {
        type: 'bar',
        data: {
          datasets: [
            {
              label: 'Volume',
              data: buildVolumePoints(data.timestamps, data.volume),
              backgroundColor: volumeColor,
              borderWidth: 0,
            },
          ],
        },
        options: {
          animation: false,
          maintainAspectRatio: false,
          scales: {
            x: { type: 'time', grid: { color: gridColor }, ticks: { display: false } },
            y: { grid: { color: gridColor }, ticks: { color: textColor, maxTicksLimit: 3 } },
          },
          plugins: { legend: { display: false } },
        },
      });
    }

    if (rsiRef.current) {
      charts.rsi?.destroy();
      charts.rsi = new Chart(rsiRef.current, {
        type: 'line',
        data: {
          datasets: [
            { label: 'RSI', data: buildLinePoints(data.timestamps, data.rsi), borderColor: rsiColor, pointRadius: 0 },
          ],
        },
        options: {
          animation: false,
          maintainAspectRatio: false,
          scales: {
            x: { type: 'time', grid: { color: gridColor }, ticks: { color: textColor } },
            y: { min: 0, max: 100, grid: { color: gridColor }, ticks: { color: textColor } },
          },
          plugins: { legend: { labels: { color: textColor } } },
        },
      });
    }

    if (macdRef.current) {
      charts.macd?.destroy();
      charts.macd = new Chart(macdRef.current, {
        type: 'line',
        data: {
          datasets: [
            { label: 'MACD', data: buildLinePoints(data.timestamps, data.macd), borderColor: macdColor, pointRadius: 0 },
            {
              label: 'Signal',
              data: buildLinePoints(data.timestamps, data.macd_signal),
              borderColor: macdSignalColor,
              pointRadius: 0,
            },
          ],
        },
        options: {
          animation: false,
          maintainAspectRatio: false,
          scales: {
            x: { type: 'time', grid: { color: gridColor }, ticks: { color: textColor } },
            y: { grid: { color: gridColor }, ticks: { color: textColor } },
          },
          plugins: { legend: { labels: { color: textColor } } },
        },
      });
    }

    return () => {
      charts.price?.destroy();
      charts.volume?.destroy();
      charts.rsi?.destroy();
      charts.macd?.destroy();
    };
  }, [compact, data, levels, symbol, theme]);

  return (
    <div className={compact ? 'technical-chart-stack' : 'full-chart-stack'}>
      <div className={compact ? 'technical-price-chart' : 'full-price-chart'}>
        <canvas ref={priceRef} height={140} />
      </div>
      <div className={compact ? 'technical-volume-chart' : 'full-volume-chart'}>
        <canvas ref={volumeRef} height={compact ? 54 : 80} />
      </div>
      <div className={compact ? 'technical-indicator-chart' : 'full-indicator-chart'}>
        <canvas ref={rsiRef} height={80} />
      </div>
      <div className={compact ? 'technical-indicator-chart' : 'full-indicator-chart'}>
        <canvas ref={macdRef} height={80} />
      </div>
    </div>
  );
}
