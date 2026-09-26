/**
 * Score de atenção do Radar. Extraído sem mudança de regra do antigo
 * Dashboard (scoreRow), agora puro e explicável: devolve o total e a
 * contribuição de cada componente.
 *
 * TODO(backend): mover este cálculo para a API (ex.: /api/intelligence/radar)
 * para que todas as telas e o bot usem a mesma regra.
 *
 * Observação herdada: o componente de movimento é assimétrico (alta soma,
 * queda subtrai), então uma queda forte reduz a atenção. Mantido por
 * fidelidade; ver relatório.
 */
import { isNum, minutesSince } from './format';

export type AttentionLevel = 'alta' | 'media' | 'baixa';

export interface AttentionComponent {
  key: 'base' | 'movimento' | 'noticias' | 'alertas' | 'eventos' | 'dados';
  label: string;
  value: number;
  detail: string;
}

export interface AttentionScore {
  total: number;
  level: AttentionLevel;
  components: AttentionComponent[];
}

export interface AttentionInput {
  symbol: string;
  price: number | null;
  changePct: number | null;
  takenAt: string | null;
  newsCount: number;
  alertCount: number;
  hasEarnings: boolean;
  now?: Date;
}

export const BASE_SCORE = 50;
const STALE_MINUTES = 30;

function clamp(v: number, min: number, max: number) {
  return Math.max(min, Math.min(max, v));
}

export function attentionLevel(total: number): AttentionLevel {
  if (total >= 75) return 'alta';
  if (total >= 60) return 'media';
  return 'baixa';
}

export const LEVEL_LABEL: Record<AttentionLevel, string> = {
  alta: 'Atenção alta',
  media: 'Atenção média',
  baixa: 'Atenção baixa',
};

export function attentionScore(input: AttentionInput): AttentionScore {
  const components: AttentionComponent[] = [];
  const change = isNum(input.changePct) ? input.changePct : 0;
  const movement = clamp(change * 3, -18, 18);
  components.push({
    key: 'movimento',
    label: 'Movimento do dia',
    value: movement,
    detail: isNum(input.changePct) ? `variação de ${input.changePct.toFixed(2).replace('.', ',')}% × 3, limitado a ±18` : 'sem variação disponível',
  });

  const news = Math.min(12, input.newsCount * 3);
  components.push({ key: 'noticias', label: 'Notícias', value: news, detail: `${input.newsCount} notícia(s) recente(s), +3 cada, máx. 12` });

  const alerts = Math.min(12, input.alertCount * 4);
  components.push({ key: 'alertas', label: 'Alertas', value: alerts, detail: `${input.alertCount} alerta(s) recente(s), +4 cada, máx. 12` });

  const events = input.hasEarnings ? -8 : 0;
  components.push({
    key: 'eventos',
    label: 'Eventos',
    value: events,
    detail: input.hasEarnings ? 'earnings nos próximos 7 dias (risco de gap)' : 'sem earnings próximos',
  });

  let dataPenalty = 0;
  const age = minutesSince(input.takenAt, input.now ?? new Date());
  const missing = !input.price || !input.takenAt;
  if (missing) dataPenalty -= 25;
  if (age !== null && age > STALE_MINUTES) dataPenalty -= 10;
  components.push({
    key: 'dados',
    label: 'Qualidade do dado',
    value: dataPenalty,
    detail: missing ? 'sem cotação' : age !== null && age > STALE_MINUTES ? `cotação com ${age} min de atraso` : 'cotação recente',
  });

  const raw = BASE_SCORE + components.reduce((sum, c) => sum + c.value, 0);
  const total = clamp(Math.round(raw), 0, 100);
  return { total, level: attentionLevel(total), components };
}
