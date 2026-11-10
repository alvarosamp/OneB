import { ArrowUpRight } from 'lucide-react';
import { Link } from 'react-router-dom';
import type { strategies } from '../../content/onebMarketing';

type Strategy = (typeof strategies)[number];

export function StrategyCard({ strategy, index }: { strategy: Strategy; index: number }) {
  return (
    <article className="oneb-strategy-card">
      <div className="oneb-strategy-card-top"><p>{strategy.category}</p><span>{String(index + 1).padStart(2, '0')}</span></div>
      <h3>{strategy.title}</h3>
      <div className="oneb-strategy-description">{strategy.description}</div>
      <footer>
        <small>{strategy.level}</small>
        <Link to="/cadastro" aria-label={`Conhecer ${strategy.title}`}><ArrowUpRight size={17} /></Link>
      </footer>
    </article>
  );
}
