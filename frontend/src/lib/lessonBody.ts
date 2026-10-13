/** Markdown mínimo do texto de aula vindo do backend (app/lms_content.py). */
export type Block =
  | { kind: 'h'; text: string }
  | { kind: 'p'; text: string }
  | { kind: 'ul'; items: string[] }
  | { kind: 'table'; head: string[]; rows: string[][] };

const cells = (line: string) => line.replace(/^\|/, '').replace(/\|$/, '').split('|').map((c) => c.trim());

/** "## " subtítulo, "- " item de lista, "| a | b |" tabela (2ª linha "|---|"), linha em branco separa parágrafos. */
export function parseLessonBody(source: string): Block[] {
  const blocks: Block[] = [];
  let paragraph: string[] = [];
  const flush = () => {
    if (paragraph.length) blocks.push({ kind: 'p', text: paragraph.join(' ') });
    paragraph = [];
  };
  for (const raw of source.split('\n')) {
    const line = raw.trim();
    if (!line) {
      flush();
    } else if (line.startsWith('## ')) {
      flush();
      blocks.push({ kind: 'h', text: line.slice(3) });
    } else if (line.startsWith('|')) {
      flush();
      const last = blocks[blocks.length - 1];
      if (/^\|[\s:|-]+\|$/.test(line)) continue; // linha separadora do cabeçalho
      if (last?.kind === 'table') last.rows.push(cells(line));
      else blocks.push({ kind: 'table', head: cells(line), rows: [] });
    } else if (line.startsWith('- ')) {
      flush();
      const last = blocks[blocks.length - 1];
      if (last?.kind === 'ul') last.items.push(line.slice(2));
      else blocks.push({ kind: 'ul', items: [line.slice(2)] });
    } else {
      paragraph.push(line);
    }
  }
  flush();
  return blocks;
}
