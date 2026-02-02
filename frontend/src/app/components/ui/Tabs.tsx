import { HTMLAttributes, ReactNode, useState, createContext, useContext } from 'react'
import { cn } from '../../utils/cn'

interface TabsContextValue {
  value: string
  onChange: (value: string) => void
}

const TabsContext = createContext<TabsContextValue | null>(null)

const useTabsContext = () => {
  const context = useContext(TabsContext)
  if (!context) {
    throw new Error('Tabs components must be used within Tabs')
  }
  return context
}

export interface TabsProps extends HTMLAttributes<HTMLDivElement> {
  value: string
  onChange: (value: string) => void
  children: ReactNode
}

export const Tabs = ({ value, onChange, className, children, ...props }: TabsProps) => {
  return (
    <TabsContext.Provider value={{ value, onChange }}>
      <div className={cn('w-full', className)} {...props}>
        {children}
      </div>
    </TabsContext.Provider>
  )
}

export interface TabsListProps extends HTMLAttributes<HTMLDivElement> {
  children: ReactNode
}

export const TabsList = ({ className, children, ...props }: TabsListProps) => {
  return (
    <div
      className={cn(
        'flex border-b border-slate-200 min-h-[44px]',
        className
      )}
      {...props}
    >
      {children}
    </div>
  )
}

export interface TabProps extends HTMLAttributes<HTMLButtonElement> {
  value: string
  label?: string
  children?: ReactNode
}

export const Tab = ({ value, label, children, className, ...props }: TabProps) => {
  const { value: selectedValue, onChange } = useTabsContext()
  const isSelected = selectedValue === value

  return (
    <button
      onClick={() => onChange(value)}
      className={cn(
        'px-4 py-3 text-sm font-medium transition-colors relative',
        'min-h-[44px]',
        isSelected
          ? 'text-primary'
          : 'text-slate-600 hover:text-slate-900',
        className
      )}
      {...props}
    >
      {label || children}
      {isSelected && (
        <span className="absolute bottom-0 left-0 right-0 h-0.5 bg-primary rounded-t" />
      )}
    </button>
  )
}

export interface TabPanelProps extends HTMLAttributes<HTMLDivElement> {
  value: string
  children: ReactNode
}

export const TabPanel = ({ value, children, className, ...props }: TabPanelProps) => {
  const { value: selectedValue } = useTabsContext()
  if (selectedValue !== value) return null

  return (
    <div className={cn('py-4', className)} {...props}>
      {children}
    </div>
  )
}

