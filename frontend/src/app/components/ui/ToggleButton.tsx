import type { ButtonHTMLAttributes, ReactNode, MouseEvent } from 'react'
import { Children, isValidElement, cloneElement } from 'react'
import { cn } from '../../utils/cn'

export interface ToggleButtonProps extends ButtonHTMLAttributes<HTMLButtonElement> {
  value: string
  selected?: boolean
  children: ReactNode
}

export const ToggleButton = ({ className, selected, children, ...props }: ToggleButtonProps) => {
  return (
    <button
      type="button"
      className={cn(
        'px-4 py-2 text-sm font-medium rounded-md border transition-colors',
        selected
          ? 'bg-primary text-white border-primary'
          : 'bg-white text-slate-700 border-slate-300 hover:bg-slate-50',
        className
      )}
      {...props}
    >
      {children}
    </button>
  )
}

export interface ToggleButtonGroupProps {
  value: string
  exclusive?: boolean
  onChange?: (event: MouseEvent<HTMLElement>, value: string | null) => void
  children: ReactNode
  className?: string
  size?: 'small' | 'medium' | 'large'
}

export const ToggleButtonGroup = ({
  value,
  exclusive = true,
  onChange,
  children,
  className,
  size = 'medium',
}: ToggleButtonGroupProps) => {
  const sizeClasses = {
    small: 'px-2 py-1 text-xs',
    medium: 'px-4 py-2 text-sm',
    large: 'px-6 py-3 text-base',
  }

  return (
    <div className={cn('inline-flex gap-0 rounded-md border border-slate-300 overflow-hidden', className)}>
      {Children.map(children, (child) => {
        if (isValidElement<ToggleButtonProps>(child) && child.type === ToggleButton) {
          const childValue = child.props.value
          const isSelected = childValue === value
          return cloneElement(child, {
            selected: isSelected,
            onClick: (e: MouseEvent<HTMLButtonElement>) => {
              if (onChange) {
                if (exclusive) {
                  onChange(e, isSelected ? null : childValue)
                } else {
                  onChange(e, childValue)
                }
              }
              child.props.onClick?.(e)
            },
            className: cn(
              sizeClasses[size],
              'border-0 rounded-none first:rounded-l-md last:rounded-r-md',
              isSelected && 'bg-primary text-white',
              !isSelected && 'bg-white text-slate-700 hover:bg-slate-50',
              child.props.className
            ),
          })
        }
        return child
      })}
    </div>
  )
}

