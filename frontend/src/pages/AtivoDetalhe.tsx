import { useEffect, useState } from 'react';
import { useParams } from 'react-router-dom';
import { api } from '../api/client';
import { CandlestickChart } from '../components/CandlestickChart';
import { RiskPanelCard } from '../components/RiskPanelCard';
import type { ChartData } from '../types';

export function AtivoDetalhe() {
  const { symbol = '' } = useParams();
  const [period, setPeriod] = useState('5d');
  const [interval, setInterval_] = useState('15m');
  const [data, setData] = useState<ChartData | null>(null);
  const [status, setStatus] = useState('Carregando dados...');

  useEffect(() => {
    let cancelled = false;

    async function load() {
      try {
        const chart = await api.get<ChartData>(`/api/chart/${symbol}?period=${period}&interval=${interval}`);
        if (cancelled) return;
        setData(chart);
        setStatus(`${chart.timestamps.length} pontos — atualizado ${new Date().toLocaleTimeString('pt-BR')}`);
      } catch {
        if (!cancelled) setStatus('Erro ao carregar dados históricos.');
      }
    }

    load();
    const timer = setInterval(load, 30000);
    return () => {
      cancelled = true;
      clearInterval(timer);
    };
  }, [symbol, period, interval]);

  return (
    <div className="container">
      <h1>
        {symbol.toUpperCase()} <span className="muted">{status}</span>
      </h1>

      <div className="chart-controls">
        <label className="field-label">
          Período
          <select value={period} onChange={(e) => setPeriod(e.target.value)}>
            <option value="1d">1 dia</option>
            <option value="5d">5 dias</option>
            <option value="1mo">1 mês</option>
            <option value="3mo">3 meses</option>
          </select>
        </label>
        <label className="field-label">
          Intervalo
          <select value={interval} onChange={(e) => setInterval_(e.target.value)}>
            <option value="5m">5 min</option>
            <option value="15m">15 min</option>
            <option value="1h">1 hora</option>
            <option value="1d">1 dia</option>
          </select>
        </label>
      </div>

      {data && <CandlestickChart data={data} symbol={symbol.toUpperCase()} />}

      <RiskPanelCard symbol={symbol.toUpperCase()} />
    </div>
  );
}
