import { Link } from 'react-router-dom';
import { CONCEPTS, conceptHref } from '../../content/concepts';
import { ptBR } from '../../lib/text';
import { Popover } from '../ui';

/** "Entenda": explicação curta do conceito com link para a aula correspondente. */
export function ConceptLink({ concept }: { concept: string }) {
  const c = CONCEPTS[concept];
  if (!c) return null;
  return (
    <Popover trigger="Entenda" triggerLabel={`Entenda: ${c.term}`} title={c.term} footer={<Link to={conceptHref(c)}>Ver aula: {ptBR(c.lesson)}</Link>}>
      {c.short}
    </Popover>
  );
}
