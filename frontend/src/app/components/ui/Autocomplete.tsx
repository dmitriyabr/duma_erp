import { useState, useRef, useEffect, useCallback, useId } from 'react'
import type { ReactNode } from 'react'
import { createPortal } from 'react-dom'
import { cn } from '../../utils/cn'
import { Input } from './Input'
import { X, Search } from 'lucide-react'

export interface AutocompleteProps<T> {
  options: T[]
  getOptionLabel: (option: T) => string
  getOptionValue?: (option: T) => string | number
  value: T | null
  onChange: (value: T | null) => void
  onInputChange?: (value: string) => void
  loading?: boolean
  label?: string
  placeholder?: string
  className?: string
  isOptionEqualToValue?: (option: T, value: T) => boolean
  disabled?: boolean
  renderOption?: (option: T) => ReactNode
  filterOptions?: (options: T[], inputValue: string) => T[]
}

export function Autocomplete<T>({
  options,
  getOptionLabel,
  getOptionValue,
  value,
  onChange,
  onInputChange,
  loading = false,
  label,
  placeholder = 'Type to search...',
  className,
  isOptionEqualToValue,
  disabled = false,
  renderOption,
  filterOptions,
}: AutocompleteProps<T>) {
  const [open, setOpen] = useState(false)
  const [inputValue, setInputValue] = useState('')
  const containerRef = useRef<HTMLDivElement>(null)
  const inputRef = useRef<HTMLInputElement>(null)
  const listRef = useRef<HTMLDivElement>(null)
  const inputIdRef = useRef(`ac-${useId()}`)
  const [dropdownPos, setDropdownPos] = useState<{
    top: number
    left: number
    width: number
    openUp: boolean
  } | null>(null)

  useEffect(() => {
    if (value) {
      setInputValue(getOptionLabel(value))
    } else {
      setInputValue('')
    }
  }, [value, getOptionLabel])

  const updateDropdownPos = useCallback(() => {
    const el = containerRef.current
    if (!el) return
    const rect = el.getBoundingClientRect()
    const maxH = 240 // 60 * 4px (max-h-60)
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
  }, [])

  useEffect(() => {
    const handleClickOutside = (event: MouseEvent) => {
      const target = event.target as Node
      if (containerRef.current?.contains(target)) return
      if (listRef.current?.contains(target)) return
      setOpen(false)
    }

    if (open) {
      document.addEventListener('mousedown', handleClickOutside)
      return () => document.removeEventListener('mousedown', handleClickOutside)
    }
  }, [open])

  useEffect(() => {
    if (!open) return
    updateDropdownPos()
    const handler = () => updateDropdownPos()
    window.addEventListener('resize', handler)
    // capture=true so we also catch scroll inside dialogs/containers
    window.addEventListener('scroll', handler, true)
    return () => {
      window.removeEventListener('resize', handler)
      window.removeEventListener('scroll', handler, true)
    }
  }, [open, updateDropdownPos])

  useEffect(() => {
    if (open && listRef.current) {
      // Scroll to selected option
      const selected = listRef.current.querySelector('[data-selected="true"]')
      if (selected) {
        selected.scrollIntoView({ block: 'nearest' })
      }
    }
  }, [open, value])

  const defaultFilterOptions = (opts: T[], searchValue: string) => {
    if (!searchValue.trim()) return opts
    const lowerSearch = searchValue.toLowerCase()
    return opts.filter((option) => {
      const label = getOptionLabel(option).toLowerCase()
      return label.includes(lowerSearch)
    })
  }

  const filteredOptions = filterOptions
    ? filterOptions(options, inputValue)
    : defaultFilterOptions(options, inputValue)

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
    inputRef.current?.blur()
  }

  const handleClear = (e: React.MouseEvent) => {
    e.stopPropagation()
    onChange(null)
    setInputValue('')
    setOpen(false)
    inputRef.current?.focus()
  }

  const handleFocus = () => {
    setOpen(true)
    // Compute immediately so dropdown appears without a "jump"
    updateDropdownPos()
  }

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Escape') {
      setOpen(false)
      inputRef.current?.blur()
    } else if (e.key === 'ArrowDown') {
      e.preventDefault()
      setOpen(true)
      const firstOption = listRef.current?.querySelector('[role="option"]') as HTMLElement
      firstOption?.focus()
    }
  }

  const isEqual = isOptionEqualToValue || ((a: T, b: T) => a === b)

  return (
    <div className={cn('w-full', className)}>
      <div ref={containerRef} className="relative">
        <div className="relative">
          <Input
            ref={inputRef}
            id={inputIdRef.current}
            label={label}
            placeholder={placeholder}
            value={inputValue}
            onChange={handleInputChange}
            onFocus={handleFocus}
            onKeyDown={handleKeyDown}
            disabled={disabled}
            className={value && !disabled ? 'pr-10' : undefined}
          />
          {value && !disabled && (
            <div className="absolute right-3 top-1/2 -translate-y-1/2">
              <button
                type="button"
                onClick={handleClear}
                className="p-1 hover:bg-slate-100 rounded transition-colors"
                aria-label="Clear selection"
              >
                <X className="w-4 h-4 text-slate-500" />
              </button>
            </div>
          )}
        </div>
        {open && !disabled && dropdownPos && createPortal(
          <div
            ref={listRef}
            className={cn(
              'fixed z-[9999] bg-white border border-slate-200 rounded-lg shadow-lg max-h-60 overflow-auto',
              dropdownPos.openUp ? '-translate-y-full' : ''
            )}
            style={{
              left: dropdownPos.left,
              top: dropdownPos.top,
              width: dropdownPos.width,
            }}
            role="listbox"
          >
            {loading ? (
              <div className="px-4 py-3 text-sm text-slate-500 flex items-center gap-2">
                <div className="w-4 h-4 border-2 border-primary border-t-transparent rounded-full animate-spin" />
                Loading...
              </div>
            ) : filteredOptions.length === 0 ? (
              <div className="px-4 py-3 text-sm text-slate-500 flex items-center gap-2">
                <Search className="w-4 h-4" />
                No options found
              </div>
            ) : (
              filteredOptions.map((option, index) => {
                const isSelected = value && isEqual(option, value)
                return (
                  <button
                    key={getOptionValue ? getOptionValue(option) : index}
                    type="button"
                    role="option"
                    aria-selected={isSelected || undefined}
                    data-selected={isSelected || undefined}
                    onClick={() => handleSelect(option)}
                    onKeyDown={(e) => {
                      if (e.key === 'Enter' || e.key === ' ') {
                        e.preventDefault()
                        handleSelect(option)
                      } else if (e.key === 'ArrowDown') {
                        e.preventDefault()
                        const next = e.currentTarget.nextElementSibling as HTMLElement
                        next?.focus()
                      } else if (e.key === 'ArrowUp') {
                        e.preventDefault()
                        const prev = e.currentTarget.previousElementSibling as HTMLElement
                        prev?.focus()
                      }
                    }}
                    className={cn(
                      'w-full text-left px-4 py-2.5 text-sm transition-colors',
                      'hover:bg-slate-100 focus:bg-slate-100 focus:outline-none',
                      'border-b border-slate-100 last:border-b-0',
                      isSelected && 'bg-primary/10 text-primary font-medium hover:bg-primary/15'
                    )}
                  >
                    {renderOption ? renderOption(option) : getOptionLabel(option)}
                  </button>
                )
              })
            )}
          </div>,
          document.body
        )}
      </div>
    </div>
  )
}
