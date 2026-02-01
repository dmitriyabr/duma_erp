import { HTMLAttributes, ReactNode } from 'react'
import { cn } from '../../utils/cn'

export interface CardProps extends HTMLAttributes<HTMLDivElement> {
  children: ReactNode
  elevation?: 0 | 1 | 2 | 3
}

export const Card = ({ className, children, elevation = 1, ...props }: CardProps) => {
  const elevationStyles = {
    0: '',
    1: 'shadow-sm border border-slate-200',
    2: 'shadow-md border border-slate-200',
    3: 'shadow-lg border border-slate-200',
  }

  return (
    <div
      className={cn(
        'bg-white rounded-2xl',
        elevationStyles[elevation],
        className
      )}
      {...props}
    >
      {children}
    </div>
  )
}

export interface CardContentProps extends HTMLAttributes<HTMLDivElement> {
  children: ReactNode
}

export const CardContent = ({ className, children, ...props }: CardContentProps) => {
  return (
    <div className={cn('p-6', className)} {...props}>
      {children}
    </div>
  )
}

