import { useEffect, useId, useMemo, useState, type KeyboardEvent } from 'react';
import { useNavigate } from 'react-router-dom';
import { ArrowLeft, Bell, CornerDownLeft, FileText, LineChart, MessagesSquare, Plus, Search } from 'lucide-react';
import { useApi } from '../../hooks/useApi';
import { useToast } from '../../context/ToastContext';
import { ALL_NAV_ITEMS } from '../../content/navigation';
import { actionsFor, searchPalette, type AssetAction, type PaletteEntry } from '../../lib/commandPalette';
import { addToWatchlist, analyzeHref, assetHref, createAlertHref } from '../../lib/watchlist';
import type { WatchlistItem } from '../../types';
import { Modal, ICON } from '../ui';
import styles from './CommandPalette.module.css';

type AssetEntry = Extract<PaletteEntry, { kind: 'asset' }>;

const ACTION_ICON: Record<AssetAction, typeof LineChart> = {
  chart: LineChart,
  analyze: MessagesSquare,
  alert: Bell,
  watchlist: Plus,
};

interface Option {
  id: string;
  group: string;
  label: string;
  hint?: string;
  icon: typeof LineChart;
  run: () => void;
}

/**
 * Command palette (Ctrl+K / Cmd+K): busca ativos da watchlist, qualquer
 * símbolo digitado e páginas; num ativo, abre ações contextuais.
 * Teclado: ↑ ↓ para navegar, Enter para escolher, Esc volta/fecha.
 */
export function CommandPalette({ open, onClose }: { open: boolean; onClose: () => void }) {
  const navigate = useNavigate();
  const toast = useToast();
  const watchlist = useApi<WatchlistItem[]>(open ? '/api/watchlist' : null);
  const [query, setQuery] = useState('');
  const [active, setActive] = useState(0);
  const [asset, setAsset] = useState<AssetEntry | null>(null);
  const listId = useId();

  useEffect(() => {
    if (open) {
      setQuery('');
      setActive(0);
      setAsset(null);
    }
  }, [open]);

  const options = useMemo<Option[]>(() => {
    const go = (to: string) => () => {
      onClose();
      navigate(to);
    };
    if (asset) {
      return actionsFor(asset)
        .filter((a) => !query || a.label.toLowerCase().includes(query.toLowerCase()))
        .map((a) => ({
          id: `action:${a.id}`,
          group: asset.symbol,
          label: a.label,
          icon: ACTION_ICON[a.id],
          run:
            a.id === 'chart'
              ? go(assetHref(asset.symbol))
              : a.id === 'analyze'
                ? go(analyzeHref(asset.symbol))
                : a.id === 'alert'
                  ? go(createAlertHref(asset.symbol))
                  : async () => {
                      onClose();
                      try {
                        const item = await addToWatchlist(asset.symbol);
                        watchlist.mutate((prev) => [...(prev ?? []), item]);
                        toast(`${asset.symbol} adicionado à watchlist`, 'success');
                      } catch (err) {
                        toast(err instanceof Error ? `Não foi possível adicionar: ${err.message}` : 'Não foi possível adicionar', 'error');
                      }
                    },
        }));
    }
    return searchPalette(query, watchlist.data ?? [], ALL_NAV_ITEMS).map((e) =>
      e.kind === 'asset'
        ? {
            id: e.id,
            group: 'Ativos',
            label: e.symbol,
            hint: e.inWatchlist ? e.label : 'fora da watchlist',
            icon: LineChart,
            run: () => {
              setAsset(e);
              setQuery('');
              setActive(0);
            },
          }
        : { id: e.id, group: 'Páginas', label: e.label, icon: FileText, run: go(e.to) },
    );
  }, [asset, query, watchlist, navigate, onClose, toast]);

  // Esc no nível de ações volta para a busca em vez de fechar.
  function back() {
    setAsset(null);
    setQuery('');
    setActive(0);
  }

  function onKeyDown(e: KeyboardEvent<HTMLInputElement>) {
    if (e.key === 'ArrowDown') {
      e.preventDefault();
      setActive((i) => (options.length ? (i + 1) % options.length : 0));
    } else if (e.key === 'ArrowUp') {
      e.preventDefault();
      setActive((i) => (options.length ? (i - 1 + options.length) % options.length : 0));
    } else if (e.key === 'Enter') {
      e.preventDefault();
      options[active]?.run();
    } else if (e.key === 'Backspace' && asset && query === '') {
      back();
    }
  }

  let lastGroup = '';
  const current = options[active];
  return (
    <Modal open={open} onClose={onClose} onEscape={asset ? back : onClose} title="Buscar ativo ou página" bare wide>
      <div className={styles.inputRow}>
        {asset ? (
          <button type="button" className={styles.back} onClick={back} aria-label={`Voltar da ${asset.symbol} para a busca`}>
            <ArrowLeft {...ICON} aria-hidden="true" />
            {asset.symbol}
          </button>
        ) : (
          <Search {...ICON} aria-hidden="true" />
        )}
        <input
          data-autofocus
          className={styles.input}
          value={query}
          onChange={(e) => {
            setQuery(e.target.value);
            setActive(0);
          }}
          onKeyDown={onKeyDown}
          placeholder={asset ? 'Escolha uma ação' : 'Símbolo (ex.: NVDA, GC=F) ou página'}
          role="combobox"
          aria-expanded="true"
          aria-controls={listId}
          aria-activedescendant={current ? `${listId}-${active}` : undefined}
          aria-autocomplete="list"
          aria-label={asset ? `Ações para ${asset.symbol}` : 'Buscar ativo ou página'}
          autoComplete="off"
          spellCheck={false}
        />
      </div>
      <ul className={styles.list} id={listId} role="listbox" aria-label="Resultados">
        {options.length === 0 && (
          <li className={styles.empty} role="presentation">
            {watchlist.status === 'loading' ? 'Carregando watchlist…' : `Nada encontrado para “${query}”. Digite um símbolo válido para abrir o gráfico.`}
          </li>
        )}
        {options.map((opt, i) => {
          const header = opt.group !== lastGroup ? opt.group : null;
          lastGroup = opt.group;
          const Icon = opt.icon;
          return (
            <li key={opt.id} role="presentation">
              {header && (
                <div className={styles.group} role="presentation">
                  {header}
                </div>
              )}
              <div
                id={`${listId}-${i}`}
                role="option"
                aria-selected={i === active}
                className={styles.option}
                onMouseMove={() => setActive(i)}
                onClick={opt.run}
              >
                <Icon {...ICON} aria-hidden="true" />
                <span className={styles.optionText}>
                  <span className={styles.optionLabel}>{opt.label}</span>
                  {opt.hint && <span className={styles.optionHint}>{opt.hint}</span>}
                </span>
                {i === active && <CornerDownLeft {...ICON} aria-hidden="true" />}
              </div>
            </li>
          );
        })}
      </ul>
      <div className={styles.footer} aria-hidden="true">
        <span>
          <kbd>↑</kbd> <kbd>↓</kbd> navegar
        </span>
        <span>
          <kbd>Enter</kbd> escolher
        </span>
        <span>
          <kbd>Esc</kbd> {asset ? 'voltar' : 'fechar'}
        </span>
      </div>
    </Modal>
  );
}
