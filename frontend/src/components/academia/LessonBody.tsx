import { Fragment, type ReactNode } from 'react';
import { parseLessonBody } from '../../lib/lessonBody';
import styles from './Player.module.css';

/** **negrito** vira <strong>; nada de HTML cru. */
function inline(text: string): ReactNode {
  return text.split(/(\*\*[^*]+\*\*)/g).map((part, i) =>
    part.startsWith('**') && part.endsWith('**') ? <strong key={i}>{part.slice(2, -2)}</strong> : <Fragment key={i}>{part}</Fragment>,
  );
}

export function LessonBody({ source }: { source: string }) {
  return (
    <div className={styles.body}>
      {parseLessonBody(source).map((b, i) =>
        b.kind === 'h' ? (
          <h3 key={i} className={styles.bodyHeading}>
            {inline(b.text)}
          </h3>
        ) : b.kind === 'table' ? (
          <div key={i} className={styles.bodyTableWrap}>
            <table className={styles.bodyTable}>
              <thead>
                <tr>
                  {b.head.map((h, j) => (
                    <th key={j} scope="col">
                      {inline(h)}
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {b.rows.map((row, j) => (
                  <tr key={j}>
                    {row.map((c, k) => (
                      <td key={k}>{inline(c)}</td>
                    ))}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        ) : b.kind === 'ul' ? (
          <ul key={i} className={styles.bodyList}>
            {b.items.map((item, j) => (
              <li key={j}>{inline(item)}</li>
            ))}
          </ul>
        ) : (
          <p key={i} className={styles.reading}>
            {inline(b.text)}
          </p>
        ),
      )}
    </div>
  );
}
