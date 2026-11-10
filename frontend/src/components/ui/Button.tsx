import { forwardRef, type ButtonHTMLAttributes, type ReactNode } from 'react';
import { Link, type LinkProps } from 'react-router-dom';
import { Loader2 } from 'lucide-react';
import { buttonClass, type ButtonSize, type ButtonVariant } from './buttonClass';
import { ICON } from './icon';

export type { ButtonSize, ButtonVariant };

interface CommonProps {
  variant?: ButtonVariant;
  size?: ButtonSize;
  icon?: ReactNode;
  iconOnly?: boolean;
  block?: boolean;
}

export interface ButtonProps extends ButtonHTMLAttributes<HTMLButtonElement>, CommonProps {
  loading?: boolean;
}

/** Botão padrão. O texto diz exatamente o que acontece ("Criar alerta"). */
export const Button = forwardRef<HTMLButtonElement, ButtonProps>(function Button(
  { variant, size, icon, iconOnly, block, loading, className, children, type = 'button', disabled, ...rest },
  ref,
) {
  return (
    <button
      ref={ref}
      type={type}
      className={buttonClass({ variant, size, iconOnly, block }, className)}
      disabled={disabled || loading}
      aria-busy={loading || undefined}
      {...rest}
    >
      {loading ? <Loader2 {...ICON} className="spin" aria-hidden="true" /> : icon}
      {children}
    </button>
  );
});

export interface ButtonLinkProps extends LinkProps, CommonProps {}

export function ButtonLink({ variant, size, icon, iconOnly, block, className, children, ...rest }: ButtonLinkProps) {
  return (
    <Link className={buttonClass({ variant, size, iconOnly, block }, className)} {...rest}>
      {icon}
      {children}
    </Link>
  );
}
