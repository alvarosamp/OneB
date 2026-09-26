import { Badge, ChangeText, type Column } from '../../components/ui';
import { formatSigned } from '../../lib/format';
import { ptBR } from '../../lib/text';
import type { CrossAssetRow } from '../../types';

export const RELEVANCE: Record<string, string> = { ALTA: 'alta', MEDIA: 'média', BAIXA: 'baixa' };
export const DIRECTION: Record<string, string> = { CONFIRMANDO: 'confirma', DIVERGINDO: 'diverge' };

export function crossAssetColumns(): Column<CrossAssetRow>[] {
  return [
    { key: 'ativo', header: 'Instrumento', render: (r) => ptBR(r.name) },
    { key: 'corr', header: 'Correlação 30d', align: 'right', sortValue: (r) => Math.abs(r.correlation_30d), render: (r) => <span className="num">{formatSigned(r.correlation_30d, 2)}</span> },
    { key: 'rel', header: 'Relevância', render: (r) => <Badge tone={r.relevance === 'ALTA' ? 'info' : 'neutral'}>{RELEVANCE[r.relevance] ?? r.relevance}</Badge> },
    { key: 'dir', header: 'Hoje', render: (r) => (r.direction ? <Badge tone={r.direction === 'DIVERGINDO' ? 'warning' : 'neutral'}>{DIRECTION[r.direction]}</Badge> : <span className="muted">—</span>) },
    { key: 'var', header: 'Variação', align: 'right', render: (r) => <ChangeText value={r.change_pct_latest} /> },
  ];
}
