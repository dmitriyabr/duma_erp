import { HTMLAttributes, ReactNode } from 'react'
import { ArrowUpDown, ArrowUp, ArrowDown } from 'lucide-react'
import { cn } from '../../utils/cn'

export interface TableSortLabelProps extends HTMLAttributes<HTMLButtonElement> {
  active?: boolean
  direction?: 'asc' | 'desc'
  children: ReactNode
  onClick?: () => void
}

export const TableSortLabel = ({
  active = false,
  direction = 'asc',
  children,
  onClick,
  className,
  ...props
}: TableSortLabelProps) => {
  return (
    <button
      onClick={onClick}
      className={cn(
        'flex items-center gap-1 font-semibold hover:opacity-80 transition-opacity',
        className
      )}
      {...props}
    >
      {children}
      {active ? (
        direction === 'asc' ? (
          <ArrowUp className="w-4 h-4" />
        ) : (
          <ArrowDown className="w-4 h-4" />
        )
      ) : (
        <ArrowUpDown className="w-4 h-4 opacity-40" />
      )}
    </button>
  )
}

