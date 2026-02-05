import React, { ReactNode, useEffect, useRef } from 'react'
import { cn } from '../../utils/cn'

export interface MenuProps {
  anchorEl: HTMLElement | null
  open: boolean
  onClose: () => void
  children: ReactNode
  className?: string
}

export const Menu = ({ anchorEl, open, onClose, children, className }: MenuProps) => {
  const menuRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    if (!open || !anchorEl) return

    const handleClickOutside = (event: MouseEvent) => {
      if (menuRef.current && !menuRef.current.contains(event.target as Node) && !anchorEl.contains(event.target as Node)) {
        onClose()
      }
    }

    const handleEscape = (event: KeyboardEvent) => {
      if (event.key === 'Escape') {
        onClose()
      }
    }

    document.addEventListener('mousedown', handleClickOutside)
    document.addEventListener('keydown', handleEscape)

    return () => {
      document.removeEventListener('mousedown', handleClickOutside)
      document.removeEventListener('keydown', handleEscape)
    }
  }, [open, anchorEl, onClose])

  useEffect(() => {
    if (!open || !anchorEl || !menuRef.current) return

    const anchorRect = anchorEl.getBoundingClientRect()
    const menuRect = menuRef.current.getBoundingClientRect()
    
    let top = anchorRect.bottom + window.scrollY
    let left = anchorRect.left + window.scrollX

    // Adjust if menu would go off screen
    if (left + menuRect.width > window.innerWidth) {
      left = window.innerWidth - menuRect.width - 8
    }
    if (top + menuRect.height > window.innerHeight + window.scrollY) {
      top = anchorRect.top + window.scrollY - menuRect.height
    }

    menuRef.current.style.top = `${top}px`
    menuRef.current.style.left = `${left}px`
  }, [open, anchorEl])

  if (!open || !anchorEl) return null

  return (
    <div
      ref={menuRef}
      className={cn(
        'fixed z-50 min-w-[160px] bg-white rounded-lg shadow-lg border border-slate-200 py-1',
        className
      )}
      role="menu"
    >
      {children}
    </div>
  )
}

export interface MenuItemProps {
  onClick?: () => void
  children: ReactNode
  className?: string
}

export const MenuItem = ({ onClick, children, className }: MenuItemProps) => {
  return (
    <div
      className={cn(
        'px-4 py-2 text-sm text-slate-700 cursor-pointer hover:bg-slate-100',
        className
      )}
      onClick={onClick}
      role="menuitem"
    >
      {children}
    </div>
  )
}


