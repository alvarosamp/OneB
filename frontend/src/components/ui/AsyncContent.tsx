import type { ReactNode } from 'react';
import type { ApiState } from '../../hooks/useApi';
import { SkeletonLines } from './Skeleton';
import { EmptyState, ErrorState } from './States';

interface AsyncContentProps<T> {
  state: Pick<ApiState<T>, 'data' | 'status' | 'error' | 'retry'>;
  children: (data: T) => ReactNode;
  /** Skeleton específico do bloco; padrão: linhas. */
  loading?: ReactNode;
  /** Estado vazio: sempre diz o que fazer. */
  empty: ReactNode;
  errorTitle?: string;
}

/**
 * Renderiza os quatro estados de um bloco de dados de forma consistente:
 * skeleton, erro com "Tentar de novo", vazio com próxima ação, e conteúdo.
 */
export function AsyncContent<T>({ state, children, loading, empty, errorTitle }: AsyncContentProps<T>) {
  switch (state.status) {
    case 'loading':
      return <>{loading ?? <SkeletonLines />}</>;
    case 'error':
      return <ErrorState title={errorTitle} error={state.error} onRetry={state.retry} />;
    case 'empty':
      return <>{empty}</>;
    default:
      return <>{children(state.data as T)}</>;
  }
}

export { EmptyState };
