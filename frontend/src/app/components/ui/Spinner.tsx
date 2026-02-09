import type { HTMLAttributes } from 'react'
import { cn } from '../../utils/cn'
import { Loader2 } from 'lucide-react'

export interface SpinnerProps extends HTMLAttributes<HTMLDivElement> {
  size?: 'small' | 'medium' | 'large'
}

const sizeStyles = {
  small: 'w-4 h-4',
  medium: 'w-6 h-6',
  large: 'w-8 h-8',
}

export const Spinner = ({ className, size = 'medium', ...props }: SpinnerProps) => {
  return (
    <div className={cn('flex items-center justify-center', className)} {...props}>
      <Loader2 className={cn('animate-spin text-primary', sizeStyles[size])} />
    </div>
  )
}


