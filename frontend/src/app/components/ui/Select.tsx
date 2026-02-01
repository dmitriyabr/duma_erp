import { SelectHTMLAttributes, forwardRef, ReactNode } from 'react'
import { cn } from '../../utils/cn'

export interface SelectProps extends SelectHTMLAttributes<HTMLSelectElement> {
  label?: string
  error?: string
  helperText?: string
  children: ReactNode
}

export const Select = forwardRef<HTMLSelectElement, SelectProps>(
  ({ className, label, error, helperText, id, children, ...props }, ref) => {
    const selectId = id || `select-${Math.random().toString(36).substr(2, 9)}`
    const hasError = !!error

    return (
      <div className="w-full">
        {label && (
          <label
            htmlFor={selectId}
            className="block text-sm font-medium text-slate-700 mb-1.5"
          >
            {label}
          </label>
        )}
        <select
          ref={ref}
          id={selectId}
          className={cn(
            'w-full px-4 py-2.5 rounded-lg border-2 transition-all duration-200',
            'focus:outline-none focus:ring-2 focus:ring-offset-2',
            'disabled:opacity-50 disabled:cursor-not-allowed',
            'bg-white appearance-none cursor-pointer',
            hasError
              ? 'border-error focus:border-error focus:ring-error'
              : 'border-slate-200 hover:border-primary-light focus:border-primary focus:ring-primary',
            className
          )}
          {...props}
        >
          {children}
        </select>
        {(error || helperText) && (
          <p
            className={cn(
              'mt-1.5 text-sm',
              hasError ? 'text-error' : 'text-slate-500'
            )}
          >
            {error || helperText}
          </p>
        )}
      </div>
    )
  }
)

Select.displayName = 'Select'

