import type { SelectHTMLAttributes, ReactNode } from 'react'
import React, { forwardRef, useState, useRef, useEffect, useId } from 'react'
import { createPortal } from 'react-dom'
import { cn } from '../../utils/cn'
import { ChevronDown, Check } from 'lucide-react'

export interface SelectProps extends SelectHTMLAttributes<HTMLSelectElement> {
  label?: string
  error?: string
  helperText?: string
  children: ReactNode
  containerClassName?: string
}

export const Select = forwardRef<HTMLSelectElement, SelectProps>(
  ({ className, containerClassName, label, error, helperText, id, value, onChange, children, ...props }, ref) => {
    const autoId = useId()
    const selectId = id || `select-${autoId}`
    const hasError = !!error
    const isRequired = Boolean(props.required)
    const [open, setOpen] = useState(false)
    const containerRef = useRef<HTMLDivElement>(null)
    const selectRef = useRef<HTMLSelectElement>(null)
    const dropdownRef = useRef<HTMLDivElement>(null)
    const [dropdownPos, setDropdownPos] = useState<{
      top: number
      left: number
      width: number
      openUp: boolean
    } | null>(null)

    // Sync refs
    useEffect(() => {
      if (ref) {
        if (typeof ref === 'function') {
          ref(selectRef.current)
        } else {
          ref.current = selectRef.current
        }
      }
    }, [ref])

    useEffect(() => {
      const handleClickOutside = (event: MouseEvent) => {
        const target = event.target as Node
        if (containerRef.current?.contains(target)) return
        if (dropdownRef.current?.contains(target)) return
        setOpen(false)
      }

      if (open) {
        document.addEventListener('mousedown', handleClickOutside)
        return () => document.removeEventListener('mousedown', handleClickOutside)
      }
    }, [open])

    useEffect(() => {
      if (!open) return
      const updatePos = () => {
        const el = containerRef.current
        if (!el) return
        const rect = el.getBoundingClientRect()
        const maxH = 240
        const margin = 6
        const openUp =
          rect.bottom + margin + maxH > window.innerHeight &&
          rect.top - margin - maxH > 0
        setDropdownPos({
          left: rect.left,
          width: rect.width,
          top: openUp ? rect.top - margin : rect.bottom + margin,
          openUp,
        })
      }
      updatePos()
      const handler = () => updatePos()
      window.addEventListener('resize', handler)
      window.addEventListener('scroll', handler, true)
      return () => {
        window.removeEventListener('resize', handler)
        window.removeEventListener('scroll', handler, true)
      }
    }, [open])

    // Extract options from children
    const options: Array<{ value: string; label: string }> = []
    if (children) {
      React.Children.forEach(children, (child) => {
        if (child && typeof child === 'object' && 'props' in child) {
          const props = child.props as { value?: string; children?: ReactNode }
          if (props.value !== undefined) {
            options.push({
              value: String(props.value),
              label: typeof props.children === 'string' ? props.children : String(props.children || props.value),
            })
          }
        }
      })
    }

    const selectedOption = options.find((opt) => String(opt.value) === String(value))
    const displayValue = selectedOption?.label || ''

    const handleSelect = (optionValue: string) => {
      if (selectRef.current && onChange) {
        selectRef.current.value = optionValue
        const syntheticEvent = {
          target: selectRef.current,
          currentTarget: selectRef.current,
        } as React.ChangeEvent<HTMLSelectElement>
        onChange(syntheticEvent)
      }
      setOpen(false)
    }

    return (
      <div className={cn(containerClassName)}>
        <div ref={containerRef} className="relative group">
          {label && (
            <label
              htmlFor={selectId}
              className={cn(
                'absolute left-3 top-0 -translate-y-1/2 px-0.5 text-xs z-[1]',
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
          {/* Hidden native select for form submission and accessibility */}
          <select
            ref={selectRef}
            id={selectId}
            className="sr-only"
            value={value}
            onChange={onChange}
            {...props}
          >
            {children}
          </select>

          {/* Custom select button */}
          <button
            type="button"
            onClick={() => {
              setOpen((v) => !v)
            }}
            disabled={props.disabled}
            className={cn(
              'w-full px-4 py-2 rounded-lg border-2 transition-all duration-200 bg-white',
              'focus:outline-none focus:ring-2 focus:ring-offset-2',
              'disabled:opacity-50 disabled:cursor-not-allowed',
              'bg-white text-left flex items-center justify-between',
              hasError  
                ? 'border-error focus:border-error focus:ring-error'
                : 'border-slate-200 hover:border-primary-light focus:border-primary focus:ring-primary',
              className
            )}
          >
            <span
              className={cn(
                'min-w-0 flex-1 truncate whitespace-nowrap',
                'text-slate-900',
                !displayValue && 'text-slate-400'
              )}
              title={displayValue || undefined}
            >
              {displayValue || 'Select...'}
            </span>
            <ChevronDown
              className={cn(
                'w-4 h-4 text-slate-500 transition-transform duration-200 flex-shrink-0 ml-2',
                open && 'rotate-180'
              )}
            />
          </button>

          {/* Custom dropdown */}
          {open && !props.disabled && dropdownPos && createPortal(
            <div
              ref={dropdownRef}
              className={cn(
                'fixed z-[9999] bg-white border border-slate-200 rounded-lg shadow-lg max-h-60 overflow-auto',
                dropdownPos.openUp ? '-translate-y-full' : ''
              )}
              style={{
                left: dropdownPos.left,
                top: dropdownPos.top,
                width: dropdownPos.width,
              }}
            >
              {options.map((option) => {
                const isSelected = String(option.value) === String(value)
                return (
                  <button
                    key={option.value}
                    type="button"
                    onClick={() => handleSelect(option.value)}
                    className={cn(
                      'w-full text-left px-4 py-2.5 text-sm transition-colors',
                      'hover:bg-slate-100 focus:bg-slate-100 focus:outline-none',
                      'border-b border-slate-100 last:border-b-0',
                      'flex items-center justify-between',
                      isSelected && 'bg-primary/10 text-primary font-medium hover:bg-primary/15'
                    )}
                  >
                    <span>{option.label}</span>
                    {isSelected && <Check className="w-4 h-4 flex-shrink-0 ml-2" />}
                  </button>
                )
              })}
            </div>,
            document.body
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

Select.displayName = 'Select'
