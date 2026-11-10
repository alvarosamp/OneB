import { useState, type FormEvent } from 'react';
import { Trash2 } from 'lucide-react';
import { api } from '../api/client';
import { useApi } from '../hooks/useApi';
import { useToast } from '../context/ToastContext';
import { useConfirm } from '../components/ConfirmModal';
import { AsyncContent, Badge, Button, EmptyState, ICON, Input, Section, Select, SkeletonLines } from '../components/ui';
import type { NotificationChannelType, SaasOverview, SubscriptionPlan } from '../types';
import styles from './Configuracoes.module.css';

const PLAN: Record<SubscriptionPlan, { label: string; text: string }> = {
  FREE: { label: 'Free', text: 'Uso individual e validação.' },
  PRO: { label: 'Pro', text: 'Investidores ativos: mais ativos, regras e perguntas.' },
  ADVISOR: { label: 'Advisor', text: 'Assessores, criadores e grupos: segmentos e relatórios.' },
};

const USAGE: Record<string, string> = {
  watchlist_items: 'Ativos na watchlist',
  alert_rules: 'Regras de alerta',
  notification_channels: 'Canais de entrega',
  report_templates: 'Modelos de relatório',
  client_segments: 'Segmentos',
  ai_questions_per_month: 'Perguntas ao Assistente por mês',
};

const CHANNEL: Record<NotificationChannelType, { label: string; placeholder: string }> = {
  TELEGRAM: { label: 'Telegram', placeholder: '@usuario ou ID do chat' },
  EMAIL: { label: 'E-mail', placeholder: 'nome@exemplo.com' },
  WEBHOOK: { label: 'Webhook', placeholder: 'https://…' },
};

/** Configurações › Workspace e canais (antiga página SaaS). */
export function Saas() {
  const overview = useApi<SaasOverview>('/api/saas/overview');
  return (
    <AsyncContent state={overview} loading={<SkeletonLines lines={10} />} empty={<EmptyState title="Workspace não encontrado" />} errorTitle="Não foi possível carregar o workspace">
      {(o) => <Workspace o={o} set={overview.mutate} reload={overview.retry} />}
    </AsyncContent>
  );
}

function Workspace({ o, set, reload }: { o: SaasOverview; set: (o: SaasOverview) => void; reload: () => void }) {
  const toast = useToast();
  const confirm = useConfirm();
  const [ws, setWs] = useState({ name: o.workspace.name, brand_name: o.workspace.brand_name });
  const [channel, setChannel] = useState<{ type: NotificationChannelType; destination: string }>({ type: 'TELEGRAM', destination: '' });
  const [template, setTemplate] = useState({ title: '', audience: '', include_ai_summary: true, include_backtest: false });
  const [segment, setSegment] = useState({ name: '', description: '' });

  async function run(fn: () => Promise<unknown>, ok: string, fail: string) {
    try {
      await fn();
      toast(ok, 'success');
      reload();
      return true;
    } catch (err) {
      toast(err instanceof Error ? `${fail}: ${err.message}` : fail, 'error');
      return false;
    }
  }

  async function changePlan(plan: SubscriptionPlan) {
    try {
      set(await api.put<SaasOverview>('/api/saas/plan', { plan }));
      toast(`Plano alterado para ${PLAN[plan].label}`, 'success');
    } catch (err) {
      toast(err instanceof Error ? `Não foi possível alterar o plano: ${err.message}` : 'Não foi possível alterar o plano', 'error');
    }
  }

  return (
    <div className={styles.stack}>
      <Section title="Plano e uso" meta={`plano atual: ${PLAN[o.workspace.plan].label}`}>
        <div className={styles.plans} role="radiogroup" aria-label="Plano">
          {(Object.keys(PLAN) as SubscriptionPlan[]).map((p) => (
            <button key={p} type="button" role="radio" aria-checked={o.workspace.plan === p} className={styles.plan} onClick={() => changePlan(p)}>
              <strong>{PLAN[p].label}</strong>
              <span>{PLAN[p].text}</span>
            </button>
          ))}
        </div>
        <dl className={styles.usage}>
          {Object.entries(o.limits).map(([k, limit]) => {
            const used = o.usage[k] ?? 0;
            return (
              <div key={k}>
                <dt>{USAGE[k] ?? k}</dt>
                <dd className="num">
                  {used} de {limit} {used >= limit && <Badge tone="warning">no limite</Badge>}
                </dd>
              </div>
            );
          })}
        </dl>
      </Section>

      <Section title="Marca" divided>
        <form
          className={styles.form}
          onSubmit={(e: FormEvent) => {
            e.preventDefault();
            void run(() => api.put('/api/saas/workspace', ws), 'Workspace atualizado', 'Não foi possível salvar');
          }}
        >
          <Input label="Nome do workspace" value={ws.name} onChange={(e) => setWs((w) => ({ ...w, name: e.target.value }))} className={styles.w260} />
          <Input label="Marca exibida nos relatórios" value={ws.brand_name} onChange={(e) => setWs((w) => ({ ...w, brand_name: e.target.value }))} className={styles.w260} />
          <Button type="submit">Salvar marca</Button>
        </form>
      </Section>

      <Section title="Canais de entrega de alertas" divided>
        <form
          className={styles.form}
          onSubmit={async (e: FormEvent) => {
            e.preventDefault();
            if (!channel.destination.trim()) return;
            if (await run(() => api.post('/api/saas/channels', { channel_type: channel.type, destination: channel.destination }), 'Canal adicionado', 'Não foi possível adicionar o canal'))
              setChannel((c) => ({ ...c, destination: '' }));
          }}
        >
          <Select label="Tipo" value={channel.type} onChange={(e) => setChannel((c) => ({ ...c, type: e.target.value as NotificationChannelType }))} className={styles.w180}>
            {(Object.keys(CHANNEL) as NotificationChannelType[]).map((t) => (
              <option key={t} value={t}>
                {CHANNEL[t].label}
              </option>
            ))}
          </Select>
          <Input label="Destino" value={channel.destination} onChange={(e) => setChannel((c) => ({ ...c, destination: e.target.value }))} placeholder={CHANNEL[channel.type].placeholder} className={styles.w260} />
          <Button type="submit">Adicionar canal</Button>
        </form>
        {o.channels.length ? (
          <ul className={styles.items}>
            {o.channels.map((c) => (
              <li key={c.id}>
                <span>
                  <strong>{CHANNEL[c.channel_type]?.label ?? c.channel_type}</strong> <span className="muted">{c.destination}</span>
                </span>
                <Button
                  size="sm"
                  variant="ghost"
                  iconOnly
                  icon={<Trash2 {...ICON} />}
                  aria-label={`Remover canal ${c.destination}`}
                  onClick={async () => {
                    if (await confirm(`Remover o canal ${c.destination}?`)) void run(() => api.delete(`/api/saas/channels/${c.id}`), 'Canal removido', 'Não foi possível remover o canal');
                  }}
                />
              </li>
            ))}
          </ul>
        ) : (
          <p className="muted">Nenhum canal configurado. Sem canal, os alertas aparecem só no OneB.</p>
        )}
      </Section>

      <Section title="Modelos de relatório" divided>
        <form
          className={styles.form}
          onSubmit={async (e: FormEvent) => {
            e.preventDefault();
            if (!template.title.trim()) return;
            if (await run(() => api.post('/api/saas/report-templates', template), 'Modelo criado', 'Não foi possível criar o modelo'))
              setTemplate({ title: '', audience: '', include_ai_summary: true, include_backtest: false });
          }}
        >
          <Input label="Título" value={template.title} onChange={(e) => setTemplate((t) => ({ ...t, title: e.target.value }))} placeholder="Resumo semanal Nasdaq" className={styles.w260} />
          <Input label="Público" value={template.audience} onChange={(e) => setTemplate((t) => ({ ...t, audience: e.target.value }))} placeholder="Investidores iniciantes" className={styles.w260} />
          <label className={styles.check}>
            <input type="checkbox" checked={template.include_ai_summary} onChange={(e) => setTemplate((t) => ({ ...t, include_ai_summary: e.target.checked }))} />
            Incluir resumo do Assistente
          </label>
          <label className={styles.check}>
            <input type="checkbox" checked={template.include_backtest} onChange={(e) => setTemplate((t) => ({ ...t, include_backtest: e.target.checked }))} />
            Incluir backtest
          </label>
          <Button type="submit">Criar modelo</Button>
        </form>
        {o.report_templates.length ? (
          <ul className={styles.items}>
            {o.report_templates.map((t) => (
              <li key={t.id}>
                <span>
                  <strong>{t.title}</strong> <span className="muted">{t.audience}</span>
                </span>
              </li>
            ))}
          </ul>
        ) : (
          <p className="muted">Nenhum modelo criado.</p>
        )}
      </Section>

      <Section title="Segmentos" divided>
        <form
          className={styles.form}
          onSubmit={async (e: FormEvent) => {
            e.preventDefault();
            if (!segment.name.trim()) return;
            if (await run(() => api.post('/api/saas/segments', segment), 'Segmento criado', 'Não foi possível criar o segmento')) setSegment({ name: '', description: '' });
          }}
        >
          <Input label="Nome" value={segment.name} onChange={(e) => setSegment((s) => ({ ...s, name: e.target.value }))} placeholder="Swing trade" className={styles.w260} />
          <Input label="Descrição" value={segment.description} onChange={(e) => setSegment((s) => ({ ...s, description: e.target.value }))} placeholder="Perfil, objetivo ou lista modelo" className={styles.w260} />
          <Button type="submit">Criar segmento</Button>
        </form>
        {o.segments.length ? (
          <ul className={styles.items}>
            {o.segments.map((s) => (
              <li key={s.id}>
                <span>
                  <strong>{s.name}</strong> <span className="muted">{s.description}</span>
                </span>
              </li>
            ))}
          </ul>
        ) : (
          <p className="muted">Nenhum segmento criado.</p>
        )}
      </Section>
    </div>
  );
}
