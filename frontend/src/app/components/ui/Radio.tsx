import type { InputHTMLAttributes, ReactNode } from 'react'
import { forwardRef, Children, isValidElement, cloneElement } from 'react'
import { cn } from '../../utils/cn'

export interface RadioProps extends InputHTMLAttributes<HTMLInputElement> {
  label?: string
}

export const Radio = forwardRef<HTMLInputElement, RadioProps>(
  ({ className, label, id, ...props }, ref) => {
    const radioId = id || `radio-${Math.random().toString(36).substr(2, 9)}`

    return (
      <label htmlFor={radioId} className="flex items-center gap-2 cursor-pointer">
        <input
          ref={ref}
          type="radio"
          id={radioId}
          className={cn(
            'w-4 h-4 text-primary border-2 border-slate-300 focus:ring-2 focus:ring-primary focus:ring-offset-2',
            'cursor-pointer',
            className
          )}
          {...props}
        />
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
}

export const RadioGroup = ({ value, onChange, children, className, row = false }: RadioGroupProps) => {
  return (
    <div className={cn(row ? 'flex flex-row gap-4' : 'flex flex-col gap-2', className)} role="radiogroup">
      {Children.map(children, (child) => {
        if (isValidElement<RadioProps>(child) && child.type === Radio) {
          return cloneElement(child, {
            checked: child.props.value === value,
            onChange: () => onChange(child.props.value as string),
          })
        }
        return child
      })}
    </div>
  )
}

