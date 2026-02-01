import { InputHTMLAttributes, forwardRef } from 'react'
import { cn } from '../../utils/cn'
import { Check } from 'lucide-react'

export interface CheckboxProps extends Omit<InputHTMLAttributes<HTMLInputElement>, 'type'> {
  label?: string
}

export const Checkbox = forwardRef<HTMLInputElement, CheckboxProps>(
  ({ className, label, id, ...props }, ref) => {
    const checkboxId = id || `checkbox-${Math.random().toString(36).substr(2, 9)}`

    return (
      <div className="flex items-center gap-2">
        <div className="relative">
          <input
            ref={ref}
            type="checkbox"
            id={checkboxId}
            className="sr-only"
            {...props}
          />
          <label
            htmlFor={checkboxId}
            className={cn(
              'w-5 h-5 rounded border-2 cursor-pointer transition-all duration-200',
              'flex items-center justify-center',
              props.checked
                ? 'bg-primary border-primary'
                : 'bg-white border-slate-300 hover:border-primary',
              props.disabled && 'opacity-50 cursor-not-allowed',
              className
            )}
          >
            {props.checked && (
              <Check className="w-3.5 h-3.5 text-white" strokeWidth={3} />
            )}
          </label>
        </div>
        {label && (
          <label
            htmlFor={checkboxId}
            className="text-sm text-slate-700 cursor-pointer select-none"
          >
            {label}
          </label>
        )}
      </div>
    )
  }
)

Checkbox.displayName = 'Checkbox'

