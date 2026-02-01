import { HTMLAttributes, ReactNode } from 'react'
import { cn } from '../../utils/cn'

type Variant = 'h1' | 'h2' | 'h3' | 'h4' | 'h5' | 'h6' | 'body1' | 'body2' | 'subtitle1' | 'subtitle2' | 'caption'
type Color = 'primary' | 'secondary' | 'text' | 'error' | 'success' | 'warning' | 'info'

export interface TypographyProps extends HTMLAttributes<HTMLElement> {
  variant?: Variant
  color?: Color
  children: ReactNode
  component?: keyof JSX.IntrinsicElements
}

const variantStyles: Record<Variant, string> = {
  h1: 'text-4xl font-bold tracking-tight',
  h2: 'text-3xl font-bold tracking-tight',
  h3: 'text-2xl font-semibold tracking-tight',
  h4: 'text-xl font-semibold tracking-tight',
  h5: 'text-lg font-semibold',
  h6: 'text-base font-semibold',
  subtitle1: 'text-base font-medium',
  subtitle2: 'text-xs font-medium uppercase tracking-wide',
  body1: 'text-base',
  body2: 'text-sm',
  caption: 'text-xs',
}

const colorStyles: Record<Color, string> = {
  primary: 'text-primary',
  secondary: 'text-secondary',
  text: 'text-slate-800',
  error: 'text-error',
  success: 'text-success',
  warning: 'text-warning',
  info: 'text-info',
}

const defaultComponents: Record<Variant, keyof JSX.IntrinsicElements> = {
  h1: 'h1',
  h2: 'h2',
  h3: 'h3',
  h4: 'h4',
  h5: 'h5',
  h6: 'h6',
  subtitle1: 'p',
  subtitle2: 'p',
  body1: 'p',
  body2: 'p',
  caption: 'span',
}

export const Typography = ({
  variant = 'body1',
  color = 'text',
  component,
  className,
  children,
  ...props
}: TypographyProps) => {
  const Component = component || defaultComponents[variant]
  const colorClass = color === 'secondary' ? 'text-slate-500' : colorStyles[color]

  return (
    <Component
      className={cn(variantStyles[variant], colorClass, className)}
      {...props}
    >
      {children}
    </Component>
  )
}

