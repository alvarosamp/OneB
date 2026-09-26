import { Link } from 'react-router-dom';
import { ArrowUpRight, BellRing, BookOpenCheck, ShieldCheck } from 'lucide-react';
import type { applications } from '../../content/onebMarketing';

type Application = (typeof applications)[number];

export function ApplicationCard({ app, index }: { app: Application; index: number }) {
  const Icon = app.key === 'school' ? BookOpenCheck : app.key === 'terminal' ? BellRing : ShieldCheck;
  return (
    <article className={`oneb-app-card app-${app.key}`}>
      <div className="oneb-app-icon" aria-hidden="true"><Icon size={30} /></div>
      <div className="oneb-app-content">
        <div className="oneb-app-card-top"><span className="oneb-app-category">{app.category}</span><b>{String(index + 1).padStart(2, '0')}</b></div>
        <h3>{app.title}</h3>
        <p>{app.description}</p>
        <div className="oneb-app-metrics">
          {app.metrics.map((metric) => (
            <small key={metric}>{metric}</small>
          ))}
        </div>
        <Link to={app.href}>Conhecer <ArrowUpRight size={17} /></Link>
      </div>
    </article>
  );
}
