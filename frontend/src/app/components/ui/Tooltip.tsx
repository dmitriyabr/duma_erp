import type { HTMLAttributes, ReactNode } from 'react'
import { useState } from 'react'
import { cn } from '../../utils/cn'

export interface TooltipProps extends HTMLAttributes<HTMLDivElement> {
  title: string
  children: ReactNode
}

export const Tooltip = ({ title, children, className, ...props }: TooltipProps) => {
  const [show, setShow] = useState(false)

  return (
    <div
      className="relative inline-block"
      onMouseEnter={() => setShow(true)}
      onMouseLeave={() => setShow(false)}
      {...props}
    >
      {children}
      {show && (
        <div
          className={cn(
            'absolute z-50 px-3 py-1.5 text-xs text-white bg-slate-800 rounded-md whitespace-nowrap',
            'bottom-full left-1/2 -translate-x-1/2 mb-2',
            'after:content-[""] after:absolute after:top-full after:left-1/2 after:-translate-x-1/2',
            'after:border-4 after:border-transparent after:border-t-slate-800',
            className
          )}
        >
          {title}
        </div>
      )}
    </div>
  )
}


