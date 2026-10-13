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
  CategoryScale,
  Tooltip,
  Legend,
} from 'chart.js';
import styles from './ReliabilityChart.module.css';
import type { ReliabilityScoreboard } from '../types';

Chart.register(
  BarController,
  BarElement,
  LineController,
  LineElement,
  PointElement,
  LinearScale,
  CategoryScale,
  Tooltip,
  Legend,
);

interface ReliabilityChartProps {
  data: ReliabilityScoreboard;
}

export function ReliabilityChart({ data }: ReliabilityChartProps) {
  const { theme } = useTheme();
  const calibrationRef = useRef<HTMLCanvasElement>(null);
  const trendRef = useRef<HTMLCanvasElement>(null);
  const chartsRef = useRef<{ calibration?: Chart; trend?: Chart }>({});

  useEffect(() => {
    const charts = chartsRef.current;
    // Cores dos tokens (--chart-*, --series-*); acompanham o tema.
    const css = getComputedStyle(document.documentElement);
    const token = (name: string) => css.getPropertyValue(name).trim();
    const gridColor = token('--chart-grid');
    const textColor = token('--chart-text');
    const predictedColor = token('--series-1');
    const actualColor = token('--series-3');

    const calibrated = data.calibration.filter((bucket) => bucket.samples > 0);

    if (calibrationRef.current) {
      charts.calibration?.destroy();
      charts.calibration = new Chart(calibrationRef.current, {
        type: 'bar',
        data: {
          labels: calibrated.map((bucket) => `${bucket.label} (n=${bucket.samples})`),
          datasets: [
            {
              label: 'Confiança prevista',
              data: calibrated.map((bucket) => bucket.midpoint_confidence),
              backgroundColor: predictedColor,
            },
            {
              label: 'Acerto real',
              data: calibrated.map((bucket) => bucket.actual_win_rate_pct ?? 0),
              backgroundColor: actualColor,
            },
          ],
        },
        options: {
          animation: false,
          maintainAspectRatio: false,
          scales: {
            x: { grid: { display: false }, ticks: { color: textColor } },
            y: { min: 0, max: 100, grid: { color: gridColor }, ticks: { color: textColor } },
          },
          plugins: { legend: { labels: { color: textColor } } },
        },
      });
    }

    if (trendRef.current) {
      charts.trend?.destroy();
      charts.trend = new Chart(trendRef.current, {
        type: 'line',
        data: {
          labels: data.trend.map((point) => point.period_label),
          datasets: [
            {
              label: 'Taxa de acerto por lote',
              data: data.trend.map((point) => point.win_rate_pct),
              borderColor: actualColor,
              backgroundColor: actualColor,
              tension: 0.25,
              pointRadius: 3,
            },
          ],
        },
        options: {
          animation: false,
          maintainAspectRatio: false,
          scales: {
            x: { grid: { display: false }, ticks: { color: textColor } },
            y: { min: 0, max: 100, grid: { color: gridColor }, ticks: { color: textColor } },
          },
          plugins: { legend: { labels: { color: textColor } } },
        },
      });
    }

    return () => {
      charts.calibration?.destroy();
      charts.trend?.destroy();
    };
  }, [data, theme]);

  if (!data.total_samples) {
    return <p className="muted">Registre algumas leituras e aguarde a checagem de resultado (5 pregões) para o placar aparecer.</p>;
  }

  return (
    <div className={styles.board}>
      <div className={styles.summary}>
        <span>Amostras checadas</span>
        <strong className="num">{data.total_samples}</strong>
        <span>Acerto geral</span>
        <strong className="num">
          {String(data.overall_win_rate_pct).replace('.', ',')}%
          {data.overall_ci_low_pct != null && data.overall_ci_high_pct != null && (
            <small className="muted"> (IC95% {data.overall_ci_low_pct}–{data.overall_ci_high_pct}%)</small>
          )}
        </strong>
        {data.confidence_brier_score != null && (
          <>
            <span>Brier da confiança</span>
            <strong className="num">{String(data.confidence_brier_score).replace('.', ',')}</strong>
          </>
        )}
      </div>
      {!!data.by_reliability_grade?.length && (
        <div>
          <h3 className={styles.subtitle}>A confiabilidade se confirma? Acerto real por nota</h3>
          <table className={styles.gradeTable}>
            <thead>
              <tr>
                <th>Nota</th>
                <th>Leituras</th>
                <th>Acerto real</th>
                <th>IC95%</th>
              </tr>
            </thead>
            <tbody>
              {data.by_reliability_grade.map((row) => (
                <tr key={row.grade}>
                  <td>{row.grade}</td>
                  <td className="num">{row.samples}</td>
                  <td className="num">{row.actual_win_rate_pct}%</td>
                  <td className="num">{row.ci_low_pct}–{row.ci_high_pct}%</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
      <div className={styles.charts}>
        <div>
          <h3>Calibração: confiança declarada contra acerto real</h3>
          <div className={styles.canvas}>
            <canvas ref={calibrationRef} role="img" aria-label="Calibração: confiança declarada contra acerto real" />
          </div>
        </div>
        <div>
          <h3>Evolução do acerto por lote de leituras</h3>
          <div className={styles.canvas}>
            <canvas ref={trendRef} role="img" aria-label="Evolução do acerto por lote de leituras" />
          </div>
        </div>
      </div>
    </div>
  );
}
