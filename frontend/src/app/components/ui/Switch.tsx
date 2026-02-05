import { InputHTMLAttributes, forwardRef } from 'react'
import { cn } from '../../utils/cn'

export interface SwitchProps extends Omit<InputHTMLAttributes<HTMLInputElement>, 'type'> {
  label?: string
}

export const Switch = forwardRef<HTMLInputElement, SwitchProps>(
  ({ className, label, id, ...props }, ref) => {
    const switchId = id || `switch-${Math.random().toString(36).substr(2, 9)}`

    return (
      <label htmlFor={switchId} className="flex items-center gap-2 cursor-pointer">
        <div className="relative inline-flex items-center">
          <input
            ref={ref}
            type="checkbox"
            id={switchId}
            className="sr-only"
            {...props}
          />
          <div
            className={cn(
              'w-11 h-6 rounded-full transition-colors duration-200 ease-in-out',
              props.checked
                ? 'bg-primary'
                : 'bg-slate-300',
              'relative',
              className
            )}
          >
            <div
              className={cn(
                'absolute top-0.5 left-0.5 w-5 h-5 bg-white rounded-full transition-transform duration-200 ease-in-out',
                props.checked ? 'translate-x-5' : 'translate-x-0'
              )}
            />
          </div>
        </div>
        {label && (
          <span className="text-sm text-slate-700">{label}</span>
        )}
      </label>
    )
  }
)

Switch.displayName = 'Switch'


