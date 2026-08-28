import { useEffect, useMemo, useState } from 'react';
import { useParams } from 'react-router-dom';
import { api } from '../api/client';
import { CandlestickChart } from '../components/CandlestickChart';
import type { ChartData } from '../types';

const PERIOD_OPTIONS = [
  { value: '1d', label: '1D' },
  { value: '5d', label: '5D' },
  { value: '1mo', label: '1M' },
  { value: '3mo', label: '3M' },
];

const INTERVAL_OPTIONS = [
  { value: '5m', label: '5m' },
  { value: '15m', label: '15m' },
  { value: '1h', label: '1h' },
  { value: '1d', label: '1D' },
];

function lastValid(values: (number | null)[]) {
  for (let i = values.length - 1; i >= 0; i -= 1) {
    if (values[i] !== null) return values[i];
  }
  return null;
}

function minutesSinceLastPoint(timestamps: string[]) {
  if (!timestamps.length) return null;
  const last = timestamps[timestamps.length - 1];
  return Math.round((Date.now() - new Date(last).getTime()) / 60000);
}

function dataConfidence(ageMinutes: number | null) {
  if (ageMinutes === null) return { cls: 'low', label: 'Sem dado' };
  if (ageMinutes <= 5) return { cls: 'high', label: 'Ao vivo' };
  if (ageMinutes <= 30) return { cls: 'mid', label: `${ageMinutes} min atrás` };
  return { cls: 'low', label: `${ageMinutes} min atrás` };
}

export function AtivoDetalhe() {
  const { symbol = '' } = useParams();
  const [period, setPeriod] = useState('5d');
  const [interval, setInterval_] = useState('15m');
  const [data, setData] = useState<ChartData | null>(null);
  const [status, setStatus] = useState('Carregando dados...');
  const [errored, setErrored] = useState(false);

  useEffect(() => {
    let cancelled = false;

    async function load() {
      try {
        const chart = await api.get<ChartData>(`/api/chart/${symbol}?period=${period}&interval=${interval}`);
        if (cancelled) return;
        setData(chart);
        setErrored(false);
        setStatus(`${chart.timestamps.length} pontos · atualizado ${new Date().toLocaleTimeString('pt-BR')}`);
      } catch {
        if (!cancelled) {
          setErrored(true);
          setStatus('Erro ao carregar dados históricos.');
        }
      }
    }

    load();
    const timer = setInterval(load, 30000);
    return () => {
      cancelled = true;
      clearInterval(timer);
    };
  }, [symbol, period, interval]);

  const lastPrice = useMemo(() => (data ? lastValid(data.close) : null), [data]);
  const prevClose = useMemo(() => {
    if (!data) return null;
    const validCloses = data.close.filter((value): value is number => value !== null);
    return validCloses.length > 1 ? validCloses[validCloses.length - 2] : null;
  }, [data]);
  const changePct = lastPrice !== null && prevClose ? ((lastPrice - prevClose) / prevClose) * 100 : null;
  const ageMinutes = useMemo(() => (data ? minutesSinceLastPoint(data.timestamps) : null), [data]);
  const confidence = dataConfidence(errored ? null : ageMinutes);

  return (
    <div className="container">
      <div className="page-header">
        <div>
          <p className="eyebrow">Ativo</p>
          <h1>{symbol.toUpperCase()}</h1>
          <p className="muted">{status}</p>
        </div>
      </div>

      <div className="technical-tape" style={{ marginBottom: '1rem' }}>
        <div>
          <span>Preço</span>
          <strong>{lastPrice !== null ? lastPrice.toFixed(2) : '-'}</strong>
        </div>
        <div>
          <span>Variação</span>
          <strong className={changePct !== null ? (changePct >= 0 ? 'up' : 'down') : undefined}>
            {changePct !== null ? `${changePct >= 0 ? '+' : ''}${changePct.toFixed(2)}%` : '-'}
          </strong>
        </div>
        <div>
          <span>Confiabilidade do dado</span>
          <strong>
            <span className={`confidence ${confidence.cls}`}>
              <i />
              {confidence.label}
            </span>
          </strong>
        </div>
      </div>

      <div className="technical-toolbar">
        <div>
          <h2>Gráfico e indicadores</h2>
          <span className="muted">EMA9 · EMA21 · RSI · MACD</span>
        </div>
        <div className="technical-controls">
          <div className="segmented-control" role="group" aria-label="Período">
            {PERIOD_OPTIONS.map((opt) => (
              <button
                key={opt.value}
                type="button"
                className={`segmented-option${period === opt.value ? ' active' : ''}`}
                onClick={() => setPeriod(opt.value)}
              >
                {opt.label}
              </button>
            ))}
          </div>
          <div className="segmented-control" role="group" aria-label="Intervalo">
            {INTERVAL_OPTIONS.map((opt) => (
              <button
                key={opt.value}
                type="button"
                className={`segmented-option${interval === opt.value ? ' active' : ''}`}
                onClick={() => setInterval_(opt.value)}
              >
                {opt.label}
              </button>
            ))}
          </div>
        </div>
      </div>

      <div className="technical-chart-panel">
        {data ? <CandlestickChart data={data} symbol={symbol.toUpperCase()} /> : <p className="muted">{status}</p>}
      </div>

      <p className="disclaimer" style={{ marginTop: '1rem' }}>
        Indicadores calculados a partir de dados históricos de preço. Apenas informativo — não constitui recomendação de investimento.
      </p>
    </div>
  );
}
