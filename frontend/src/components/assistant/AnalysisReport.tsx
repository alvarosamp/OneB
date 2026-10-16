import { useState } from 'react';
import { Sparkles } from 'lucide-react';
import { useApi } from '../../hooks/useApi';
import { useToast } from '../../context/ToastContext';
import { AsyncContent, Button, EmptyState, ICON, Modal, SkeletonLines } from '../ui';
import styles from './AnalysisReport.module.css';

interface Report {
  key: string;
  label: string;
  generated_at: string;
  sections: { title: string; bullets: string[] }[];
  disclaimer: string;
  text: string;
}

/** "Análise em 30 segundos": relatório do ativo só com números medidos, pronto para copiar. */
export function AnalysisReportButton({ assetKey, label }: { assetKey: string; label: string }) {
  const [open, setOpen] = useState(false);
  return (
    <>
      <Button variant="primary" icon={<Sparkles {...ICON} />} onClick={() => setOpen(true)}>
        Gerar análise
      </Button>
      {open && <ReportModal assetKey={assetKey} label={label} onClose={() => setOpen(false)} />}
    </>
  );
}

function ReportModal({ assetKey, label, onClose }: { assetKey: string; label: string; onClose: () => void }) {
  const report = useApi<Report>(`/api/analysis/report/${assetKey}`);
  const toast = useToast();
  async function copy(text: string) {
    try {
      await navigator.clipboard.writeText(text);
      toast('Análise copiada. Cole onde quiser compartilhar.', 'success');
    } catch {
      toast('Não foi possível copiar. Selecione o texto manualmente.', 'error');
    }
  }
  return (
    <Modal
      open
      wide
      onClose={onClose}
      title={`Análise OneB — ${label}`}
      footer={
        report.data && (
          <Button variant="secondary" onClick={() => void copy(report.data!.text)}>
            Copiar texto
          </Button>
        )
      }
    >
      <AsyncContent state={report} loading={<SkeletonLines lines={12} />} empty={<EmptyState title="Sem dados para a análise agora" />} errorTitle="Análise indisponível">
        {(r) => (
          <div className={styles.report}>
            {r.sections.map((s) => (
              <section key={s.title} className={styles.section}>
                <h3 className={styles.title}>{s.title}</h3>
                <ul className={styles.list}>
                  {s.bullets.map((b) => (
                    <li key={b}>{b}</li>
                  ))}
                </ul>
              </section>
            ))}
            <p className={styles.disclaimer}>{r.disclaimer}</p>
          </div>
        )}
      </AsyncContent>
    </Modal>
  );
}
