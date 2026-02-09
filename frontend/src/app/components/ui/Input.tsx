import type { InputHTMLAttributes } from 'react'
import { forwardRef, useId } from 'react'
import { cn } from '../../utils/cn'

export interface InputProps extends InputHTMLAttributes<HTMLInputElement> {
  label?: string
  error?: string
  helperText?: string
  containerClassName?: string
}

export const Input = forwardRef<HTMLInputElement, InputProps>(
  ({ className, containerClassName, label, error, helperText, id, ...props }, ref) => {
    const autoId = useId()
    const inputId = id || `input-${autoId}`
    const hasError = !!error
    const isRequired = Boolean(props.required)

    return (
      <div className={cn(containerClassName)}>
        <div className="relative group">
          <input
            ref={ref}
            id={inputId}
            className={cn(
              'peer w-full px-4 py-2 rounded-lg border-2 transition-all duration-200 bg-white',
              'focus:outline-none focus:ring-2 focus:ring-offset-2',
              'disabled:opacity-50 disabled:cursor-not-allowed',
              hasError
                ? 'border-error focus:border-error focus:ring-error'
                : 'border-slate-200 hover:border-primary-light focus:border-primary focus:ring-primary',
              className
            )}
            {...props}
          />
          {label && (
            <label
              htmlFor={inputId}
              className={cn(
                'absolute left-3 top-0 -translate-y-1/2 px-0.5 text-xs',
                'before:absolute before:inset-x-0 before:top-[7px] before:h-1',
                'before:-z-10 before:bg-white',
                'after:h-1 after:top-[3px]',
                'after:absolute after:inset-x-0',
                'after:-z-10 after:transition-all after:duration-200',
                'group-focus-within:after:bg-white',
                hasError ? 'text-error' : 'text-slate-500',
                !hasError && 'group-focus-within:text-primary'
              )}
            >
              {label}
              {isRequired && <span className="ml-0.5">*</span>}
            </label>
          )}
        </div>
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

Input.displayName = 'Input'


