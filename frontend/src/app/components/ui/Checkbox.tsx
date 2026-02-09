import type { InputHTMLAttributes } from 'react'
import { forwardRef, useId } from 'react'
import { cn } from '../../utils/cn'
import { Check } from 'lucide-react'

export interface CheckboxProps extends Omit<InputHTMLAttributes<HTMLInputElement>, 'type'> {
  label?: string
}

export const Checkbox = forwardRef<HTMLInputElement, CheckboxProps>(
  ({ className, label, id, ...props }, ref) => {
    const autoId = useId()
    const checkboxId = id || `checkbox-${autoId}`

    return (
      <label htmlFor={checkboxId} className="inline-flex items-center gap-2 cursor-pointer select-none">
        <input
          ref={ref}
          type="checkbox"
          id={checkboxId}
          className={cn('sr-only peer', className)}
          {...props}
        />
        <span
          aria-hidden="true"
          className={cn(
            'w-5 h-5 rounded border-2 transition-all duration-200 flex items-center justify-center',
            'peer-checked:bg-primary peer-checked:border-primary',
            'peer-focus-visible:outline-none peer-focus-visible:ring-2 peer-focus-visible:ring-primary peer-focus-visible:ring-offset-2',
            props.disabled ? 'opacity-50 cursor-not-allowed' : 'bg-white border-slate-300 hover:border-primary'
          )}
        >
          {props.checked && <Check className="w-3.5 h-3.5 text-white" strokeWidth={3} />}
        </span>
        {label && <span className="text-sm text-slate-700">{label}</span>}
      </label>
    )
  }
)

Checkbox.displayName = 'Checkbox'


