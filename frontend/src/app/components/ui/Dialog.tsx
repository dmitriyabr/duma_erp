import { HTMLAttributes, ReactNode, useEffect } from 'react'
import { createPortal } from 'react-dom'
import { X } from 'lucide-react'
import { cn } from '../../utils/cn'
import { Button } from './Button'

export interface DialogProps {
  open: boolean
  onClose: () => void
  children: ReactNode
  maxWidth?: 'sm' | 'md' | 'lg' | 'xl'
  fullWidth?: boolean
}

const maxWidthStyles = {
  sm: 'max-w-sm',
  md: 'max-w-md',
  lg: 'max-w-lg',
  xl: 'max-w-xl',
}

export const Dialog = ({ open, onClose, children, maxWidth = 'lg', fullWidth = false }: DialogProps) => {
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
        'relative z-10 bg-white rounded-2xl shadow-2xl w-full mx-4 max-h-[90vh] overflow-hidden flex flex-col',
        !fullWidth && maxWidthStyles[maxWidth]
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
    <div className={cn('px-6 pb-5 overflow-y-auto flex-1', className)} {...props}>
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

