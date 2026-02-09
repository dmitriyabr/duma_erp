import type { TextareaHTMLAttributes } from 'react'
import { forwardRef, useId } from 'react'
import { cn } from '../../utils/cn'

export interface TextareaProps extends TextareaHTMLAttributes<HTMLTextAreaElement> {
  label?: string
  error?: string
  helperText?: string
  containerClassName?: string
}

export const Textarea = forwardRef<HTMLTextAreaElement, TextareaProps>(
  ({ className, containerClassName, label, error, helperText, id, ...props }, ref) => {
    const autoId = useId()
    const textareaId = id || `textarea-${autoId}`
    const hasError = !!error
    const isRequired = Boolean(props.required)

    return (
      <div className={cn('w-full', containerClassName)}>
        <div className="relative group">
          <textarea
            ref={ref}
            id={textareaId}
            className={cn(
              'peer w-full px-4 py-2 rounded-lg border-2 transition-all duration-200 bg-white',
              'focus:outline-none focus:ring-2 focus:ring-offset-2',
              'disabled:opacity-50 disabled:cursor-not-allowed',
              'resize-y min-h-[80px]',
              hasError
                ? 'border-error focus:border-error focus:ring-error'
                : 'border-slate-200 hover:border-primary-light focus:border-primary focus:ring-primary',
              className
            )}
            {...props}
          />
          {label && (
            <label
              htmlFor={textareaId}
              className={cn(
                'absolute left-3 top-0 -translate-y-1/2 bg-white px-1 text-xs',
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

Textarea.displayName = 'Textarea'


