import styles from './Button.module.css';

export type ButtonVariant = 'primary' | 'secondary' | 'ghost' | 'danger';
export type ButtonSize = 'sm' | 'md' | 'lg';

interface ClassOptions {
  variant?: ButtonVariant;
  size?: ButtonSize;
  iconOnly?: boolean;
  block?: boolean;
}
/** Classes do botão, para links que precisam parecer botão (<Link className={buttonClass(...)}>). */
export function buttonClass({ variant = 'secondary', size = 'md', iconOnly, block }: ClassOptions, extra?: string) {
  return [
    styles.button,
    styles[variant],
    size !== 'md' ? styles[size] : '',
    iconOnly ? styles.iconOnly : '',
    block ? styles.block : '',
    extra ?? '',
  ]
    .filter(Boolean)
    .join(' ');
}
