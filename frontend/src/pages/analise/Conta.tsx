import { useState } from 'react';
import { CheckCircle2, Wallet, XCircle } from 'lucide-react';
import { useApi } from '../../hooks/useApi';
import { useDebounced } from '../../hooks/useDebounced';
import { AsyncContent, ChipGroup, EmptyState, ICON, Input, Section, SkeletonLines } from '../../components/ui';
import { formatNumber } from '../../lib/format';
import styles from './Conta.module.css';

interface SizingRow {
  key: string;
  label: string;
  symbol: string;
  available: boolean;
  stop_distance?: number;
  volume_min?: number;
  lots?: number;
  below_minimum?: boolean;
  risk_money?: number;
  actual_risk?: number;
  actual_risk_pct?: number | null;
  min_lot_risk?: number;
  min_lot_risk_pct?: number | null;
  min_balance?: number;
  spread_cost?: number | null;
  spread_share?: number | null;
}

interface Sizing {
  balance: number;
  risk_pct: number;
  stop_atr: number;
  rows: SizingRow[];
  note: string;
}

const RISKS = [
  { value: '0.5', label: '0,5%' },
  { value: '1', label: '1%' },
  { value: '2', label: '2%' },
];

const STOPS = [
  { value: '1', label: '1x ATR 1h' },
  { value: '1.5', label: '1,5x' },
  { value: '2', label: '2x' },
];

/** Spread a partir de 10% do stop: o custo come boa parte de cada 1R. */
const HIGH_COST = 0.1;

const usd = (x: number | null | undefined, d = 2) => (x == null ? '—' : `US$ ${formatNumber(x, d)}`);

/** Análise › Quanto operar: com o saldo e o risco do usuário, o lote de cada ativo e se o menor lote cabe. */
export function Conta() {
  const [balance, setBalance] = useState('1000');
  const [risk, setRisk] = useState('1');
  const [stop, setStop] = useState('1.5');
  const typed = useDebounced(balance);
  const value = Number(typed.replace(/\./g, '').replace(',', '.'));
  const valid = Number.isFinite(value) && value > 0;
  const data = useApi<Sizing>(valid ? `/api/analysis/sizing?balance=${value}&risk_pct=${risk}&stop_atr=${stop}` : null, {
    isEmpty: (d) => d.rows.length === 0,
  });
  return (
    <div className={styles.page}>
      <Section
        title="Quanto operar com a minha conta"
        meta={<span className={styles.meta}>lote calculado pelo seu risco, no stop do plano do OneB</span>}
      >
        <div className={styles.controls}>
          <Input label="Saldo da conta no MT5 (US$)" inputMode="decimal" value={balance} onChange={(e) => setBalance(e.target.value)} />
          <ChipGroup label="Risco por operação" value={risk} onChange={setRisk} items={RISKS} />
          <ChipGroup label="Distância do stop" value={stop} onChange={setStop} items={STOPS} />
        </div>
        {!valid ? (
          <p className={styles.meta}>Informe o saldo da conta em dólar.</p>
        ) : (
          <AsyncContent state={data} loading={<SkeletonLines lines={6} />} empty={<EmptyState title="Sem dados de mercado agora" />} errorTitle="Cálculo indisponível">
            {(d) => <SizingTable d={d} />}
          </AsyncContent>
        )}
      </Section>
    </div>
  );
}

function SizingTable({ d }: { d: Sizing }) {
  const fits = d.rows.filter((r) => r.available && !r.below_minimum);
  const riskWord = `${formatNumber(d.risk_pct, d.risk_pct < 1 ? 1 : 0)}%`;
  return (
    <>
      <p className={styles.summary}>
        <Wallet {...ICON} aria-hidden />{' '}
        {fits.length === 0
          ? `Com ${usd(d.balance, 0)} e ${riskWord} de risco, nenhum ativo cabe: o menor lote de cada um arrisca mais do que o seu limite.`
          : `Com ${usd(d.balance, 0)} e ${riskWord} de risco (${usd(d.balance * d.risk_pct / 100)} por operação), cabe${fits.length > 1 ? 'm' : ''}: ${fits
              .map((r) => r.label)
              .join(', ')}.`}
      </p>
      <div className={styles.tableWrap}>
        <table className={styles.table}>
          <thead>
            <tr>
              <th scope="col">Ativo</th>
              <th scope="col">Cabe?</th>
              <th scope="col">Lote</th>
              <th scope="col">Risco real</th>
              <th scope="col">Stop (distância)</th>
              <th scope="col">Spread / stop</th>
              <th scope="col">Saldo mínimo para {riskWord}</th>
            </tr>
          </thead>
          <tbody>
            {d.rows.map((r) =>
              !r.available ? (
                <tr key={r.key}>
                  <td>{r.label}</td>
                  <td colSpan={6} className={styles.meta}>
                    sem dados de mercado agora
                  </td>
                </tr>
              ) : (
                <tr key={r.key}>
                  <td>
                    {r.label}
                    <span className={styles.meta}> · {r.symbol}</span>
                  </td>
                  <td>
                    {r.below_minimum ? (
                      <span className={styles.no}>
                        <XCircle {...ICON} aria-hidden /> não
                      </span>
                    ) : (
                      <span className={styles.yes}>
                        <CheckCircle2 {...ICON} aria-hidden /> sim
                      </span>
                    )}
                  </td>
                  <td>{r.below_minimum ? `mínimo ${formatNumber(r.volume_min ?? 0, 2)}` : formatNumber(r.lots ?? 0, 2)}</td>
                  <td>
                    {r.below_minimum ? (
                      <span className={styles.no}>
                        {usd(r.min_lot_risk)} ({formatNumber(r.min_lot_risk_pct ?? 0, 1)}% da conta) no lote mínimo
                      </span>
                    ) : (
                      `${usd(r.actual_risk)} (${formatNumber(r.actual_risk_pct ?? 0, 1)}%)`
                    )}
                  </td>
                  <td>{formatNumber(r.stop_distance ?? 0, (r.stop_distance ?? 0) < 0.1 ? 5 : 2)}</td>
                  <td>
                    {r.spread_share == null ? (
                      '—'
                    ) : (
                      <span className={r.spread_share >= HIGH_COST ? styles.no : undefined}>
                        {formatNumber(r.spread_share * 100, 1)}%{r.spread_share >= HIGH_COST ? ' · custo alto' : ''}
                      </span>
                    )}
                  </td>
                  <td>{usd(r.min_balance, 0)}</td>
                </tr>
              ),
            )}
          </tbody>
        </table>
      </div>
      {fits.some((r) => (r.spread_share ?? 0) >= HIGH_COST) && (
        <p className={styles.warn}>
          Cuidado: {fits.filter((r) => (r.spread_share ?? 0) >= HIGH_COST).map((r) => r.label).join(', ')} cabe na conta, mas o spread consome{' '}
          {fits
            .filter((r) => (r.spread_share ?? 0) >= HIGH_COST)
            .map((r) => `${formatNumber((r.spread_share ?? 0) * 100, 0)}%`)
            .join(', ')}{' '}
          do stop em cada operação. Com stop maior o custo pesa menos, mas o lote diminui.
        </p>
      )}
      <p className={styles.meta}>{d.note}</p>
    </>
  );
}
