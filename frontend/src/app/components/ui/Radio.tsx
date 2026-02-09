import type { InputHTMLAttributes, ReactNode, ChangeEvent } from 'react'
import { forwardRef, Children, isValidElement, cloneElement, useId } from 'react'
import { cn } from '../../utils/cn'

export interface RadioProps extends InputHTMLAttributes<HTMLInputElement> {
  label?: string
}

export const Radio = forwardRef<HTMLInputElement, RadioProps>(
  ({ className, label, id, ...props }, ref) => {
    const autoId = useId()
    const radioId = id || `radio-${autoId}`

    return (
      <label htmlFor={radioId} className="inline-flex items-center gap-2 cursor-pointer select-none whitespace-nowrap">
        <input
          ref={ref}
          type="radio"
          id={radioId}
          className={cn('sr-only peer', className)}
          {...props}
        />
        <span
          aria-hidden="true"
          className={cn(
            'relative inline-flex items-center justify-center',
            'h-5 w-5 rounded-full border-2 border-slate-300 bg-white',
            'transition-colors',
            'peer-checked:border-primary peer-checked:bg-primary/10',
            // inner dot (uses pseudo-element so peer-checked works)
            "after:content-[''] after:h-2.5 after:w-2.5 after:rounded-full after:bg-primary after:transition-transform after:duration-150 after:scale-0",
            'peer-checked:after:scale-100',
            'peer-focus-visible:outline-none peer-focus-visible:ring-2 peer-focus-visible:ring-primary peer-focus-visible:ring-offset-2'
          )}
        >
        </span>
        {label && (
          <span className="text-sm text-slate-700">{label}</span>
        )}
      </label>
    )
  }
)

Radio.displayName = 'Radio'

export interface RadioGroupProps {
  value: string
  onChange: (value: string) => void
  children: ReactNode
  className?: string
  row?: boolean
  name?: string
}

export const RadioGroup = ({ value, onChange, children, className, row = false, name }: RadioGroupProps) => {
  const autoId = useId()
  const groupName = name || `radio-group-${autoId}`

  return (
    <div
      className={cn(
        row ? 'flex flex-row flex-wrap items-center gap-4' : 'flex flex-col gap-2',
        className
      )}
      role="radiogroup"
    >
      {Children.map(children, (child) => {
        if (isValidElement<RadioProps>(child) && child.type === Radio) {
          return cloneElement(child, {
            name: child.props.name || groupName,
            checked: child.props.value === value,
            onChange: (e: ChangeEvent<HTMLInputElement>) => {
              if (e.target.checked) {
                onChange(child.props.value as string)
              }
            },
          })
        }
        return child
      })}
    </div>
  )
}

