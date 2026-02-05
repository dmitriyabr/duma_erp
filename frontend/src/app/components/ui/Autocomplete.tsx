import { useState, useRef, useEffect, ReactNode } from 'react'
import { cn } from '../../utils/cn'
import { Input } from './Input'
import { ChevronDown, X } from 'lucide-react'

export interface AutocompleteProps<T> {
  options: T[]
  getOptionLabel: (option: T) => string
  value: T | null
  onChange: (value: T | null) => void
  onInputChange?: (value: string) => void
  loading?: boolean
  label?: string
  placeholder?: string
  className?: string
  isOptionEqualToValue?: (option: T, value: T) => boolean
  disabled?: boolean
}

export function Autocomplete<T>({
  options,
  getOptionLabel,
  value,
  onChange,
  onInputChange,
  loading = false,
  label,
  placeholder,
  className,
  isOptionEqualToValue,
  disabled = false,
}: AutocompleteProps<T>) {
  const [open, setOpen] = useState(false)
  const [inputValue, setInputValue] = useState('')
  const containerRef = useRef<HTMLDivElement>(null)
  const inputRef = useRef<HTMLInputElement>(null)

  useEffect(() => {
    if (value) {
      setInputValue(getOptionLabel(value))
    } else {
      setInputValue('')
    }
  }, [value, getOptionLabel])

  useEffect(() => {
    const handleClickOutside = (event: MouseEvent) => {
      if (containerRef.current && !containerRef.current.contains(event.target as Node)) {
        setOpen(false)
      }
    }

    if (open) {
      document.addEventListener('mousedown', handleClickOutside)
      return () => document.removeEventListener('mousedown', handleClickOutside)
    }
  }, [open])

  const filteredOptions = options.filter((option) => {
    const label = getOptionLabel(option).toLowerCase()
    return label.includes(inputValue.toLowerCase())
  })

  const handleInputChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const newValue = e.target.value
    setInputValue(newValue)
    setOpen(true)
    onInputChange?.(newValue)
  }

  const handleSelect = (option: T) => {
    onChange(option)
    setInputValue(getOptionLabel(option))
    setOpen(false)
  }

  const handleClear = () => {
    onChange(null)
    setInputValue('')
    setOpen(false)
  }

  const isEqual = isOptionEqualToValue || ((a: T, b: T) => a === b)

  return (
    <div ref={containerRef} className={cn('relative w-full', className)}>
      <div className="relative">
        <Input
          ref={inputRef}
          label={label}
          placeholder={placeholder}
          value={inputValue}
          onChange={handleInputChange}
          onFocus={() => setOpen(true)}
          disabled={disabled}
          className="pr-10"
        />
        <div className="absolute right-3 top-1/2 -translate-y-1/2 flex items-center gap-1">
          {value && !disabled && (
            <button
              type="button"
              onClick={handleClear}
              className="p-0.5 hover:bg-slate-100 rounded transition-colors"
            >
              <X className="w-4 h-4 text-slate-500" />
            </button>
          )}
          <ChevronDown className={cn('w-4 h-4 text-slate-500 transition-transform', open && 'rotate-180')} />
        </div>
      </div>
      {open && !disabled && (
        <div className="absolute z-50 w-full mt-1 bg-white border-2 border-slate-200 rounded-lg shadow-lg max-h-60 overflow-auto">
          {loading ? (
            <div className="px-4 py-2 text-sm text-slate-500">Loading...</div>
          ) : filteredOptions.length === 0 ? (
            <div className="px-4 py-2 text-sm text-slate-500">No options</div>
          ) : (
            filteredOptions.map((option, index) => (
              <button
                key={index}
                type="button"
                onClick={() => handleSelect(option)}
                className={cn(
                  'w-full text-left px-4 py-2 text-sm hover:bg-slate-50 transition-colors',
                  value && isEqual(option, value) && 'bg-primary/10 text-primary'
                )}
              >
                {getOptionLabel(option)}
              </button>
            ))
          )}
        </div>
      )}
    </div>
  )
}


