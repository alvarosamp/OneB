import { forwardRef, useId, type InputHTMLAttributes, type ReactNode, type SelectHTMLAttributes, type TextareaHTMLAttributes } from 'react';
import styles from './Field.module.css';

interface FieldWrapProps {
  label: ReactNode;
  hint?: ReactNode;
  error?: ReactNode;
  className?: string;
  hideLabel?: boolean;
}

function Wrap({ id, label, hint, error, className, hideLabel, children }: FieldWrapProps & { id: string; children: ReactNode }) {
  return (
    <div className={[styles.field, className ?? ''].join(' ')}>
      <label htmlFor={id} className={hideLabel ? 'sr-only' : styles.label}>
        {label}
      </label>
      {children}
      {error ? <span className={styles.errorText}>{error}</span> : hint ? <span className={styles.hint}>{hint}</span> : null}
    </div>
  );
}

type InputProps = InputHTMLAttributes<HTMLInputElement> & FieldWrapProps;

export const Input = forwardRef<HTMLInputElement, InputProps>(function Input({ label, hint, error, className, hideLabel, id, ...rest }, ref) {
  const autoId = useId();
  const inputId = id ?? autoId;
  return (
    <Wrap id={inputId} label={label} hint={hint} error={error} className={className} hideLabel={hideLabel}>
      <input ref={ref} id={inputId} className={[styles.control, error ? styles.invalid : ''].join(' ')} aria-invalid={!!error || undefined} {...rest} />
    </Wrap>
  );
});

type SelectProps = SelectHTMLAttributes<HTMLSelectElement> & FieldWrapProps;

export function Select({ label, hint, error, className, hideLabel, id, children, ...rest }: SelectProps) {
  const autoId = useId();
  const selectId = id ?? autoId;
  return (
    <Wrap id={selectId} label={label} hint={hint} error={error} className={className} hideLabel={hideLabel}>
      <select id={selectId} className={styles.control} {...rest}>
        {children}
      </select>
    </Wrap>
  );
}

type TextareaProps = TextareaHTMLAttributes<HTMLTextAreaElement> & FieldWrapProps;

export function Textarea({ label, hint, error, className, hideLabel, id, ...rest }: TextareaProps) {
  const autoId = useId();
  const areaId = id ?? autoId;
  return (
    <Wrap id={areaId} label={label} hint={hint} error={error} className={className} hideLabel={hideLabel}>
      <textarea id={areaId} className={[styles.control, styles.textarea].join(' ')} {...rest} />
    </Wrap>
  );
}
