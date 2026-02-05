import { HTMLAttributes } from 'react'
import { cn } from '../../utils/cn'

type Color = 'default' | 'primary' | 'secondary' | 'success' | 'warning' | 'error' | 'info'

export interface ChipProps extends HTMLAttributes<HTMLSpanElement> {
  label: string
  color?: Color
  size?: 'small' | 'medium'
}

const colorStyles: Record<Color, string> = {
  default: 'bg-slate-100 text-slate-800',
  primary: 'bg-primary/10 text-primary-dark',
  secondary: 'bg-secondary/10 text-secondary-dark',
  success: 'bg-success/10 text-success-dark',
  warning: 'bg-warning/10 text-warning-dark',
  error: 'bg-error/10 text-error-dark',
  info: 'bg-info/10 text-info-dark',
}

export const Chip = ({
  label,
  color = 'default',
  size = 'medium',
  className,
  ...props
}: ChipProps) => {
  return (
    <span
      className={cn(
        'inline-flex items-center font-medium rounded-lg',
        colorStyles[color],
        size === 'small' ? 'px-2 py-0.5 text-xs' : 'px-3 py-1 text-sm',
        className
      )}
      {...props}
    >
      {label}
    </span>
  )
}


