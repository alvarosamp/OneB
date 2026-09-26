import { Link } from 'react-router-dom';
import { LineChart } from 'lucide-react';
import { useApi } from '../../hooks/useApi';
import { formatDateTime } from '../../lib/format';
import { ptBR } from '../../lib/text';
import { ruleTypeLabel } from '../../lib/rules';
import type { AlertLog, MovementExplanation } from '../../types';
import { AsyncContent, Button, EmptyState, ICON, SkeletonLines } from '../ui';
import { buttonClass } from '../ui/buttonClass';
import { AnswerCard } from './AnswerCard';
import styles from './Assistant.module.css';

interface AlertExplainProps {
  alertId: number | null;
  onSelect: (id: number) => void;
  onAsk: (question: string) => void;
}

/** Modo "Explicar alerta": o que disparou, o que se sabe e o que ainda não se sabe. */
export function AlertExplain({ alertId, onSelect, onAsk }: AlertExplainProps) {
  const alerts = useApi<AlertLog[]>('/api/alerts?limit=15');
  const selected = alerts.data?.find((a) => a.id === alertId) ?? alerts.data?.[0] ?? null;

  return (
    <div className={styles.mode}>
      <AsyncContent
        state={alerts}
        loading={<SkeletonLines lines={5} />}
        empty={
          <EmptyState
            title="Nenhum alerta disparado ainda"
            description="Crie regras na watchlist; quando um alerta disparar, ele pode ser explicado aqui."
            action={
              <Link to="/watchlist" className={buttonClass({ size: 'sm' })}>
                Criar alerta
              </Link>
            }
          />
        }
        errorTitle="Não foi possível carregar os alertas"
      >
        {(list) => (
          <>
            <div className={styles.alertList} role="group" aria-label="Alertas recentes">
              {list.map((a) => (
                <button key={a.id} type="button" className={styles.alertOption} aria-pressed={selected?.id === a.id} onClick={() => onSelect(a.id)}>
                  <strong>{a.symbol}</strong>
                  <span>{ptBR(a.message)}</span>
                  <time dateTime={a.triggered_at}>{formatDateTime(a.triggered_at)}</time>
                </button>
              ))}
            </div>
            {selected && <Explanation alert={selected} onAsk={onAsk} />}
          </>
        )}
      </AsyncContent>
    </div>
  );
}

function Explanation({ alert, onAsk }: { alert: AlertLog; onAsk: (q: string) => void }) {
  const explain = useApi<MovementExplanation>(`/api/intelligence/explain/${encodeURIComponent(alert.symbol)}`);
  return (
    <AsyncContent state={explain} loading={<SkeletonLines lines={5} label="Explicando alerta" />} empty={<EmptyState title="Sem dados para explicar" description={explain.error ?? undefined} />}>
      {(data) => (
        <AnswerCard
          subject={`Alerta de ${alert.symbol}`}
          subtitle={`${ruleTypeLabel(alert.rule_type)}, disparado em ${formatDateTime(alert.triggered_at)}`}
          conclusion={ptBR(data.hypotheses[0] ?? alert.message)}
          evidences={[ptBR(alert.message), ...data.facts.map(ptBR)]}
          counterpoints={data.hypotheses.slice(1).map(ptBR)}
          actions={
            <>
              <Link to={`/ativo/${encodeURIComponent(alert.symbol)}`} className={buttonClass({ size: 'sm' })}>
                <LineChart {...ICON} aria-hidden="true" />
                Ver gráfico
              </Link>
              <Button size="sm" variant="ghost" onClick={() => onAsk(`Explique o alerta de ${alert.symbol}: "${alert.message}". O que os dados coletados mostram e o que ainda falta confirmar?`)}>
                Perguntar sobre este alerta
              </Button>
            </>
          }
          details={
            data.related_events.length > 0 ? (
              <div className={styles.vote}>
                <strong>Eventos relacionados</strong>
                <ul>
                  {data.related_events.map((e) => (
                    <li key={e}>{ptBR(e)}</li>
                  ))}
                </ul>
              </div>
            ) : undefined
          }
        />
      )}
    </AsyncContent>
  );
}
