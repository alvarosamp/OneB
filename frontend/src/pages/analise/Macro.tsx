import { useState, type CSSProperties } from 'react';
import { useNavigate } from 'react-router-dom';
import { useApi } from '../../hooks/useApi';
import { DataAge } from '../../components/terminal/DataAge';
import { AsyncContent, Badge, ChangeText, EmptyState, Section, SkeletonLines, Table, Tabs, type Column } from '../../components/ui';
import { formatNumber, formatPrice, formatSigned, isNum } from '../../lib/format';
import { ptBR } from '../../lib/text';
import { formatTrendChange, themeLabel } from '../../lib/macro';
import type { MacroInstrument, MacroOverview, RelationshipDynamic, TrendAnalysis } from '../../types';
import { crossAssetColumns } from './crossAsset';
import styles from './Analise.module.css';
import m from './Macro.module.css';

const YIELDS = ['US2Y', 'US5Y', 'US10Y', 'US30Y'];

const DIRECTION_LABEL: Record<TrendAnalysis['direction'], string> = {
  'ALTA FORTE': 'Alta forte',
  ALTA: 'Alta',
  LATERAL: 'Lateral',
  BAIXA: 'Baixa',
  'BAIXA FORTE': 'Baixa forte',
};

const STRENGTH_LABEL: Record<TrendAnalysis['strength'], string> = {
  FORTE: 'Forte',
  MODERADA: 'Moderada',
  FRACA: 'Fraca',
  INDEFINIDA: 'Indefinida',
};

const RELATION_LABEL: Record<RelationshipDynamic['status'], string> = {
  INVERSAO: 'Inversão',
  FORTALECENDO: 'Fortalecendo',
  ENFRAQUECENDO: 'Enfraquecendo',
  ESTAVEL: 'Estável',
};

type WindowKey = '20' | '60' | '3m' | '6m' | '12m';
type NewsWindowKey = '3m' | '6m' | '12m';

function trendTone(direction: TrendAnalysis['direction']): 'up' | 'down' | '' {
  if (direction.startsWith('ALTA')) return 'up';
  if (direction.startsWith('BAIXA')) return 'down';
  return '';
}

function changeTone(value: number | null | undefined): string {
  if (!isNum(value)) return 'num muted';
  return value > 0 ? 'num up' : value < 0 ? 'num down' : 'num';
}

function cellStyle(value: number | null): CSSProperties | undefined {
  if (value === null) return undefined;
  return { '--w': `${Math.round(8 + Math.abs(value) * 36)}%` } as CSSProperties;
}

/** Análise › Macro: tendências, correlações entre ativos e contexto de notícias. */
export function Macro() {
  const navigate = useNavigate();
  const [win, setWin] = useState<WindowKey>('60');
  const [newsWin, setNewsWin] = useState<NewsWindowKey>('3m');
  const macro = useApi<MacroOverview>('/api/regime/macro', {
    pollMs: 60_000,
    isEmpty: (d) => d.instruments.length === 0 && (d.trend_watchlist ?? []).length === 0,
  });

  const trendColumns: Column<MacroInstrument>[] = [
    {
      key: 'nome',
      header: 'Instrumento',
      render: (i) => (
        <span className={m.name}>
          <strong>{ptBR(i.name)}</strong>
          <span className={m.sub}>
            {i.symbol}
            {i.context ? `, ${ptBR(i.context)}` : ''}
          </span>
        </span>
      ),
    },
    {
      key: 'tend',
      header: 'Tendência',
      sortValue: (i) => i.trend?.score ?? null,
      render: (i) =>
        i.trend ? (
          <span className={trendTone(i.trend.direction)}>
            {DIRECTION_LABEL[i.trend.direction] ?? i.trend.direction} <span className="num">({i.trend.score})</span>
          </span>
        ) : (
          <span className="muted">—</span>
        ),
    },
    {
      key: 'forca',
      header: 'Força',
      sortValue: (i) => i.trend?.adx14 ?? null,
      render: (i) =>
        i.trend ? (
          <span>
            {STRENGTH_LABEL[i.trend.strength] ?? i.trend.strength}
            {isNum(i.trend.adx14) ? <span className="num muted">, ADX {formatNumber(i.trend.adx14, 1)}</span> : null}
          </span>
        ) : (
          <span className="muted">—</span>
        ),
    },
    ...(['change_5d', 'change_20d', 'change_60d'] as const).map<Column<MacroInstrument>>((k) => ({
      key: k,
      header: `${k.replace('change_', '').replace('d', '')} sessões`,
      align: 'right',
      sortValue: (i) => i.trend?.[k] ?? null,
      render: (i) => <span className={changeTone(i.trend?.[k])}>{i.trend ? formatTrendChange(i.trend[k], i.trend.change_unit) : '—'}</span>,
    })),
    {
      key: 'idade',
      header: 'Dado',
      align: 'right',
      sortValue: (i) => i.trend?.age_days ?? null,
      render: (i) =>
        i.trend ? (
          <span className={i.trend.age_days > 3 ? m.stale : 'num muted'}>{i.trend.age_days === 0 ? 'hoje' : `há ${i.trend.age_days} d`}</span>
        ) : (
          <span className="muted">—</span>
        ),
    },
  ];

  const columns: Column<MacroInstrument>[] = [
    { key: 'nome', header: 'Instrumento', render: (i) => ptBR(i.name) },
    { key: 'fonte', header: 'Série', render: (i) => <span className="muted">{i.symbol}</span> },
    { key: 'preco', header: 'Último', align: 'right', render: (i) => <span className="num">{YIELDS.includes(i.key) ? (isNum(i.price) ? `${formatNumber(i.price, 2)}%` : '—') : formatPrice(i.price, i.key === 'GOLD' ? 'GC=F' : i.key)}</span> },
    { key: 'var', header: 'Variação', align: 'right', sortValue: (i) => i.change_pct, render: (i) => (i.price === null ? <span className="muted">sem cotação</span> : <ChangeText value={i.change_pct} />) },
    { key: 'idade', header: 'Dados', align: 'right', render: (i) => <DataAge at={i.taken_at} staleAfterMin={YIELDS.includes(i.key) || ['DXY', 'VIX'].includes(i.key) ? 60 * 24 * 3 : 60} prefix="" /> },
  ];

  return (
    <AsyncContent state={macro} loading={<SkeletonLines lines={10} />} empty={<EmptyState title="Sem instrumentos macro" description="Ainda sem snapshots. Aguarde o próximo ciclo do coletor macro." />} errorTitle="Macro indisponível">
      {(d) => {
        const trends = d.trend_watchlist ?? [];
        const corr = d.correlation_windows?.[win];
        const goldCorrelations = {
          wti: corr?.matrix.find((row) => row.key === 'GOLD')?.values.WTI ?? null,
          brent: corr?.matrix.find((row) => row.key === 'GOLD')?.values.BRENT ?? null,
        };
        const changes = (d.relationship_dynamics ?? []).filter((r) => r.status !== 'ESTAVEL').slice(0, 5);
        const leads = (d.lead_lag_candidates ?? []).slice(0, 5);
        const hist = d.history_status;
        const news = hist?.latest_news_context;
        const nma = hist?.news_market_analysis?.windows?.[newsWin] ?? hist?.news_market_analysis;
        const themes = Object.entries(news?.theme_counts ?? {}).sort((a, b) => b[1] - a[1]).slice(0, 6);
        const recurring = (hist?.lead_lag_validation ?? []).filter((r) => r.status === 'RECORRENTE').length;

        return (
          <div className={styles.stack}>
            <Section title="Radar de tendências" meta="direção por EMA 20/50, força por ADX">
              {trends.length ? (
                <Table
                  caption="Radar de tendências"
                  columns={trendColumns}
                  rows={trends}
                  rowKey={(i) => i.key}
                  onRowClick={(i) => navigate(`/analise?tab=regime&symbol=${encodeURIComponent(i.key)}`)}
                  rowLabel={(i) => `Ver regime de ${ptBR(i.name)}`}
                  dense
                  stickyFirstColumn
                />
              ) : (
                <p className="muted">Ainda sem snapshots. Aguarde o próximo ciclo do coletor macro.</p>
              )}
              <p className={styles.note}>Juros em pontos-base; índices, commodities e moedas em percentual. Clique em uma linha para ver os fatores do regime.</p>
            </Section>

            <Section
              title="Correlação móvel"
              meta="retornos diários; para juros, a mudança do yield"
              actions={
                <Tabs
                  label="Janela de correlação"
                  variant="segmented"
                  value={win}
                  onChange={setWin}
                  items={[
                    { value: '20', label: '20 sessões' },
                    { value: '60', label: '60 sessões' },
                    { value: '3m', label: '3 meses' },
                    { value: '6m', label: '6 meses' },
                    { value: '12m', label: '12 meses' },
                  ]}
                />
              }
            >
              {!corr ? (
                <p className="muted">Ainda não há histórico comum suficiente para calcular as correlações.</p>
              ) : (
                <div className={styles.stack}>
                  <dl className={m.facts}>
                    <div>
                      <dt>Ouro × WTI</dt>
                      <dd className="num">{goldCorrelations.wti === null ? '—' : formatSigned(goldCorrelations.wti, 2)}</dd>
                      <dd className={m.small}>Janela de até {corr.sessions} sessões</dd>
                    </div>
                    <div>
                      <dt>Ouro × Brent</dt>
                      <dd className="num">{goldCorrelations.brent === null ? '—' : formatSigned(goldCorrelations.brent, 2)}</dd>
                      <dd className={m.small}>Valor negativo indica tendência inversa na janela</dd>
                    </div>
                  </dl>
                  <div className={m.cols}>
                    <div>
                      <h3 className={styles.h3}>Maiores convergências</h3>
                      <ul className={m.pairs}>
                        {corr.strongest_positive.slice(0, 3).map((p) => (
                          <li key={`${p.left}-${p.right}`}>
                            <span>{p.left} × {p.right}</span>
                            <span className="num">{formatSigned(p.correlation, 2)}</span>
                          </li>
                        ))}
                      </ul>
                    </div>
                    <div>
                      <h3 className={styles.h3}>Maiores divergências</h3>
                      <ul className={m.pairs}>
                        {corr.strongest_negative.slice(0, 3).map((p) => (
                          <li key={`${p.left}-${p.right}`}>
                            <span>{p.left} × {p.right}</span>
                            <span className="num">{formatSigned(p.correlation, 2)}</span>
                          </li>
                        ))}
                      </ul>
                    </div>
                  </div>

                  <div className={m.matrixWrap}>
                    <table className={m.matrix}>
                      <caption className="sr-only">Matriz de correlação em {corr.sessions} sessões</caption>
                      <thead>
                        <tr>
                          <th scope="col">Ativo</th>
                          {corr.matrix.map((c) => (
                            <th key={c.key} scope="col">{c.key}</th>
                          ))}
                        </tr>
                      </thead>
                      <tbody>
                        {corr.matrix.map((row) => (
                          <tr key={row.key}>
                            <th scope="row">{row.key}</th>
                            {corr.matrix.map((c) => {
                              const v = row.values[c.key] ?? null;
                              return (
                                <td
                                  key={c.key}
                                  className={v === null ? m.na : v >= 0 ? m.pos : m.neg}
                                  style={cellStyle(v)}
                                  title={`${row.key} × ${c.key}: ${v === null ? 'dados insuficientes' : formatSigned(v, 2)}`}
                                >
                                  {v === null ? '—' : formatNumber(v, 2)}
                                </td>
                              );
                            })}
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                  <p className={m.legend}>
                    <span className={m.swatchPos} aria-hidden="true" /> movimento conjunto
                    <span className={m.swatchNeg} aria-hidden="true" /> movimento inverso
                  </p>

                  <div className={m.cols}>
                    <div>
                      <h3 className={styles.h3}>Mudanças de relação</h3>
                      <p className={styles.note}>Comparação entre as janelas de 20 e 60 sessões.</p>
                      {changes.length ? (
                        <ul className={m.pairs}>
                          {changes.map((r) => (
                            <li key={`${r.left}-${r.right}`}>
                              <span>{r.left} × {r.right}</span>
                              <Badge tone={r.status === 'INVERSAO' ? 'warning' : 'neutral'}>{RELATION_LABEL[r.status]}</Badge>
                              <span className="num muted">
                                de {formatSigned(r.correlation_60d, 2)} para {formatSigned(r.correlation_20d, 2)}
                              </span>
                            </li>
                          ))}
                        </ul>
                      ) : (
                        <p className="muted">Nenhuma mudança relevante detectada.</p>
                      )}
                    </div>
                    <div>
                      <h3 className={styles.h3}>Antecedências exploratórias</h3>
                      <p className={styles.note}>Relações defasadas que superam a correlação simultânea.</p>
                      {leads.length ? (
                        <ul className={m.pairs}>
                          {leads.map((r) => (
                            <li key={`${r.leader}-${r.follower}-${r.lag_sessions}`}>
                              <span>
                                {r.leader} antecede {r.follower}
                              </span>
                              <span className="num">{r.lag_sessions} {r.lag_sessions === 1 ? 'sessão' : 'sessões'}</span>
                              <span className="num muted">
                                corr. {formatSigned(r.correlation, 2)}, ganho {formatNumber(r.improvement, 2)}
                              </span>
                            </li>
                          ))}
                        </ul>
                      ) : (
                        <p className="muted">Nenhuma antecedência consistente nesta janela.</p>
                      )}
                    </div>
                  </div>

                  <dl className={m.facts}>
                    <div>
                      <dt>Histórico gravado</dt>
                      <dd className="num">{hist?.days_recorded ?? 0} pregões</dd>
                    </div>
                    <div>
                      <dt>Cobertura mais recente</dt>
                      <dd className="num">{hist?.latest ? `${formatNumber(hist.latest.coverage_pct, 1)}%` : 'aguardando coleta'}</dd>
                      {hist?.latest ? (
                        <dd className={m.small}>
                          {hist.latest.fresh_count} em dia, {hist.latest.stale_count} atrasados, {hist.latest.missing_count} ausentes
                        </dd>
                      ) : null}
                    </div>
                    <div>
                      <dt>Antecedências recorrentes</dt>
                      <dd className="num">{recurring}</dd>
                      <dd className={m.small}>Exige 5 ou mais dias e presença em pelo menos 30% das coletas.</dd>
                    </div>
                  </dl>
                </div>
              )}
              <p className={styles.note}>
                Janela selecionada: {corr?.sessions ?? '—'} sessões, com pelo menos {corr?.minimum_observations ?? '—'} observações comuns por par.
                Correlação não implica causalidade e muda entre regimes. Antecedências são hipóteses exploratórias, sujeitas a múltiplos testes e validação fora da amostra.
              </p>
            </Section>

            <Section
              title="Notícias e mercado"
              meta={<Badge tone={nma?.status === 'PRONTO' ? 'info' : 'neutral'}>{nma?.status === 'PRONTO' ? 'Amostra disponível' : 'Coletando histórico'}</Badge>}
              actions={
                <Tabs
                  label="Período de notícias"
                  variant="segmented"
                  value={newsWin}
                  onChange={setNewsWin}
                  items={[
                    { value: '3m', label: '3 meses' },
                    { value: '6m', label: '6 meses' },
                    { value: '12m', label: '12 meses' },
                  ]}
                />
              }
            >
              <p className={styles.note}>
                {nma?.sessions_recorded ?? 0} pregões registrados de aproximadamente {nma?.expected_sessions_approx ?? 63} no período;
                {' '}{nma?.news_days ?? 0} com notícias e {nma?.available_forward_pairs ?? 0} pares com o pregão seguinte.
              </p>
              <dl className={m.facts}>
                <div>
                  <dt>Notícias na coleta recente</dt>
                  <dd className="num">{news?.article_count ?? 0}</dd>
                  <dd className={m.small}>{news?.high_impact_count ?? 0} de alto impacto</dd>
                </div>
                <div>
                  <dt>Impacto médio</dt>
                  <dd className="num">{isNum(news?.average_impact) ? formatNumber(news.average_impact, 1) : '—'}</dd>
                  <dd className={m.small}>Intensidade, não direção</dd>
                </div>
                <div>
                  <dt>Cobertura de sentimento</dt>
                  <dd className="num">{formatNumber(news?.sentiment_coverage_pct ?? 0, 1)}%</dd>
                  <dd className={m.small}>Direção só é testada quando há score</dd>
                </div>
              </dl>
              <div className={m.cols}>
                <div>
                  <h3 className={styles.h3}>Temas dominantes</h3>
                  {themes.length ? (
                    <ul className={m.pairs}>
                      {themes.map(([theme, count]) => (
                        <li key={theme}>
                          <span>{themeLabel(theme)}</span>
                          <span className="num muted">
                            {count} {count === 1 ? 'notícia' : 'notícias'}
                          </span>
                        </li>
                      ))}
                    </ul>
                  ) : (
                    <p className="muted">Nenhum tema classificado na coleta mais recente.</p>
                  )}
                </div>
                <div>
                  <h3 className={styles.h3}>Relações com o pregão seguinte</h3>
                  {(nma?.correlations ?? []).length ? (
                    <ul className={m.pairs}>
                      {(nma?.correlations ?? []).slice(0, 6).map((r) => (
                        <li key={`${r.factor_type}-${r.factor}-${r.asset}`}>
                          <span>
                            {themeLabel(r.factor)} e {r.asset}
                          </span>
                          <span className="num">{formatSigned(r.correlation, 2)}</span>
                          <span className="num muted">
                            {r.target === 'MAGNITUDE' ? 'magnitude' : 'direção'}, {r.observations} pares
                          </span>
                        </li>
                      ))}
                    </ul>
                  ) : (
                    <p className="muted">
                      <span className="num">
                        {nma?.available_forward_pairs ?? 0} de {nma?.minimum_observations ?? 20}
                      </span>{' '}
                      pares notícia e pregão seguinte coletados.
                    </p>
                  )}
                </div>
              </div>
              <p className={styles.note}>Notícias do dia são comparadas somente ao próximo pregão: impacto e temas com a magnitude do movimento; sentimento, quando disponível, com a direção.</p>
            </Section>

            <Section title="O que importa para a Nasdaq agora" meta="correlação de 30 dias com o NQ">
              {d.nasdaq_cross_asset_relevance.length ? (
                <Table caption="Relevância para a Nasdaq" columns={crossAssetColumns()} rows={d.nasdaq_cross_asset_relevance} rowKey={(r) => r.key} initialSort={{ key: 'corr', dir: 'desc' }} dense />
              ) : (
                <p className="muted">Sem histórico suficiente para correlações.</p>
              )}
            </Section>
            <Section title="Universo macro monitorado" meta="juros e VIX são séries diárias do FRED">
              {d.instruments.length ? (
                <Table caption="Universo macro" columns={columns} rows={d.instruments} rowKey={(i) => i.key} dense stickyFirstColumn />
              ) : (
                <p className="muted">Sem cotações macro gravadas.</p>
              )}
            </Section>
          </div>
        );
      }}
    </AsyncContent>
  );
}
