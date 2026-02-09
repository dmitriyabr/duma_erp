import type { HTMLAttributes, ReactNode } from 'react'
import { useEffect } from 'react'
import { createPortal } from 'react-dom'
import { X } from 'lucide-react'
import { cn } from '../../utils/cn'

export interface DialogProps {
  open: boolean
  onClose: () => void
  children: ReactNode
  maxWidth?: 'sm' | 'md' | 'lg' | 'xl'
  fullWidth?: boolean
}

const maxWidthStyles = {
  // Practical defaults for ERP dialogs (avoid overly wide dialogs by default)
  sm: 'max-w-lg',
  md: 'max-w-2xl',
  lg: 'max-w-4xl',
  xl: 'max-w-6xl',
}

export const Dialog = ({ open, onClose, children, maxWidth = 'md', fullWidth = false }: DialogProps) => {
  useEffect(() => {
    if (open) {
      document.body.style.overflow = 'hidden'
    } else {
      document.body.style.overflow = ''
    }
    return () => {
      document.body.style.overflow = ''
    }
  }, [open])

  if (!open) return null

  return createPortal(
    <div
      className="fixed inset-0 z-50 flex items-center justify-center"
      onClick={(e) => {
        if (e.target === e.currentTarget) {
          onClose()
        }
      }}
    >
      <div className="fixed inset-0 bg-black/50" />
      <div className={cn(
        // Always constrain by maxWidth; fullWidth in MUI means "use full width within maxWidth"
        'relative z-10 bg-white rounded-2xl shadow-2xl w-full mx-4 max-h-[90vh] overflow-hidden flex flex-col',
        maxWidthStyles[maxWidth],
        fullWidth && 'w-full'
      )}>
        {children}
      </div>
    </div>,
    document.body
  )
}

export interface DialogTitleProps extends HTMLAttributes<HTMLHeadingElement> {
  children: ReactNode
}

export const DialogTitle = ({ className, children, ...props }: DialogTitleProps) => {
  return (
    <h2
      className={cn('text-xl font-semibold px-6 pt-5 pb-3', className)}
      {...props}
    >
      {children}
    </h2>
  )
}

export interface DialogContentProps extends HTMLAttributes<HTMLDivElement> {
  children: ReactNode
}

export const DialogContent = ({ className, children, ...props }: DialogContentProps) => {
  return (
    <div className={cn('px-6 pt-3 pb-5 overflow-y-auto flex-1', className)} {...props}>
      {children}
    </div>
  )
}

export interface DialogActionsProps extends HTMLAttributes<HTMLDivElement> {
  children: ReactNode
}

export const DialogActions = ({ className, children, ...props }: DialogActionsProps) => {
  return (
    <div
      className={cn('px-6 pb-5 flex gap-2 justify-end', className)}
      {...props}
    >
      {children}
    </div>
  )
}

export interface DialogCloseButtonProps {
  onClose: () => void
  className?: string
}

export const DialogCloseButton = ({ onClose, className }: DialogCloseButtonProps) => {
  return (
    <button
      onClick={onClose}
      className={cn(
        'absolute top-4 right-4 p-1 rounded-lg hover:bg-slate-100 transition-colors',
        className
      )}
      aria-label="Close"
    >
      <X className="w-5 h-5 text-slate-500" />
    </button>
  )
}

