import { forwardRef } from 'react';
import type { ButtonHTMLAttributes, ReactNode } from 'react';

export type ButtonVariant = 'primary' | 'secondary' | 'quiet';

export interface ButtonProps extends ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: ButtonVariant;
  children?: ReactNode;
}

export const Button = forwardRef<HTMLButtonElement, ButtonProps>(function Button(
  { variant = 'primary', className = '', children, type = 'button', ...props },
  ref
) {
  return (
    <button
      ref={ref}
      type={type}
      className={`btn btn-${variant} ${className}`}
      {...props}
    >
      {children}
    </button>
  );
});

export default Button;
