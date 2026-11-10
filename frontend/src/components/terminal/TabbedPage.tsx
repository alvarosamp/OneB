import { useId, type ReactNode } from 'react';
import { PageHeader, TabPanel, Tabs, type TabItem } from '../ui';
import { useQueryTab } from '../../hooks/useQueryTab';
import styles from './TabbedPage.module.css';

interface TabbedPageProps<V extends string> {
  title: string;
  description?: ReactNode;
  actions?: ReactNode;
  tabs: (TabItem<V> & { render: () => ReactNode })[];
  fallback: V;
  queryKey?: string;
  variant?: 'underline' | 'segmented';
}

/** Página com abas sincronizadas à URL (`?tab=`). */
export function TabbedPage<V extends string>({ title, description, actions, tabs, fallback, queryKey = 'tab', variant }: TabbedPageProps<V>) {
  const values = tabs.map((t) => t.value);
  const [tab, setTab] = useQueryTab<V>(values, fallback, queryKey);
  const idBase = useId();
  const current = tabs.find((t) => t.value === tab) ?? tabs[0];
  return (
    <div className={styles.page}>
      <PageHeader title={title} description={description} actions={actions} />
      <Tabs items={tabs} value={tab} onChange={setTab} label={title} idBase={idBase} variant={variant} className={styles.tabs} />
      <TabPanel idBase={idBase} value={current.value}>
        {current.render()}
      </TabPanel>
    </div>
  );
}
