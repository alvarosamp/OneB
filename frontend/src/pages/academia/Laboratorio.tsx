import { Link, useSearchParams } from 'react-router-dom';
import { TradingLab } from '../../components/academia/TradingLab';
import styles from './Academia.module.css';

/** /academia/laboratorio: o simulador da Academia em tela cheia. */
export function Laboratorio() {
  const [params] = useSearchParams();
  const mode = params.get('modo') === 'ao-vivo' ? 'live' : 'replay';
  return (
    <div className={styles.page}>
      <header>
        <h1 className={styles.title}>Laboratório</h1>
        <p className={styles.lead}>
          Conta fictícia de US$ 10.000 para treinar: replays de dias reais que param na hora de decidir, ou o mercado ao vivo. Antes de abrir conta numa corretora, veja a aula{' '}
          <Link to="/aulas/fundamentos?aula=Abrindo uma conta demo no MetaTrader 5">Abrindo uma conta demo no MetaTrader 5</Link>.
        </p>
      </header>
      <TradingLab initialMode={mode} replaySlug={params.get('replay') ?? undefined} />
    </div>
  );
}
