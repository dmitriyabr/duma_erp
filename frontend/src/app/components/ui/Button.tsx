import type { ButtonHTMLAttributes } from 'react'
import { forwardRef } from 'react'
import { cn } from '../../utils/cn'

export interface ButtonProps extends ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: 'contained' | 'outlined' | 'text'
  color?: 'primary' | 'secondary' | 'success' | 'warning' | 'error' | 'info'
  size?: 'small' | 'medium' | 'large'
  fullWidth?: boolean
}

export const Button = forwardRef<HTMLButtonElement, ButtonProps>(
  (
    {
      className,
      variant = 'contained',
      color = 'primary',
      size = 'medium',
      fullWidth = false,
      disabled,
      children,
      ...props
    },
    ref
  ) => {
    const baseStyles =
      'inline-flex items-center justify-center font-medium rounded-lg transition-all duration-200 focus:outline-none focus:ring-2 focus:ring-offset-2 disabled:opacity-50 disabled:cursor-not-allowed whitespace-nowrap'
    
    const variantStyles = {
      contained: {
        primary: 'bg-gradient-to-br from-primary to-primary-dark text-white hover:from-primary-light hover:to-primary shadow-none hover:shadow-md',
        secondary: 'bg-secondary text-white hover:bg-secondary-dark shadow-none hover:shadow-md',
        success: 'bg-success text-white hover:bg-success-dark shadow-none hover:shadow-md',
        warning: 'bg-warning text-white hover:bg-warning-dark shadow-none hover:shadow-md',
        error: 'bg-error text-white hover:bg-error-dark shadow-none hover:shadow-md',
        info: 'bg-info text-white hover:bg-info-dark shadow-none hover:shadow-md',
      },
      outlined: {
        // Use ring instead of border so outlined buttons don't become taller than contained/text.
        primary: 'ring-1 ring-inset ring-primary text-primary hover:bg-primary/10',
        secondary: 'ring-1 ring-inset ring-secondary text-secondary hover:bg-secondary/10',
        success: 'ring-1 ring-inset ring-success text-success hover:bg-success/10',
        warning: 'ring-1 ring-inset ring-warning text-warning hover:bg-warning/10',
        error: 'ring-1 ring-inset ring-error text-error hover:bg-error/10',
        info: 'ring-1 ring-inset ring-info text-info hover:bg-info/10',
      },
      text: {
        primary: 'text-primary hover:bg-primary/10',
        secondary: 'text-secondary hover:bg-secondary/10',
        success: 'text-success hover:bg-success/10',
        warning: 'text-warning hover:bg-warning/10',
        error: 'text-error hover:bg-error/10',
        info: 'text-info hover:bg-info/10',
      },
    }

    const sizeStyles = {
      small: 'px-3 py-1 text-sm',
      medium: 'px-4 py-2 text-base',
      large: 'px-6 py-3 text-base',
    }

    const focusRingStyles = {
      primary: 'focus:ring-primary',
      secondary: 'focus:ring-secondary',
      success: 'focus:ring-success',
      warning: 'focus:ring-warning',
      error: 'focus:ring-error',
      info: 'focus:ring-info',
    }

    return (
      <button
        ref={ref}
        className={cn(
          baseStyles,
          variantStyles[variant][color],
          sizeStyles[size],
          focusRingStyles[color],
          fullWidth && 'w-full',
          className
        )}
        disabled={disabled}
        {...props}
      >
        {children}
      </button>
    )
  }
)

Button.displayName = 'Button'


