import type { HTMLAttributes, ReactNode } from 'react'
import { useState } from 'react'
import { cn } from '../../utils/cn'
import { AlertCircle, CheckCircle, Info, AlertTriangle, X } from 'lucide-react'

type Severity = 'success' | 'error' | 'warning' | 'info'

export interface AlertProps extends HTMLAttributes<HTMLDivElement> {
  severity: Severity
  children: ReactNode
  onClose?: () => void
}

const severityStyles: Record<Severity, string> = {
  success: 'bg-success/10 text-success-dark border-success/20',
  error: 'bg-error/10 text-error-dark border-error/20',
  warning: 'bg-warning/10 text-warning-dark border-warning/20',
  info: 'bg-info/10 text-info-dark border-info/20',
}

const icons: Record<Severity, typeof AlertCircle> = {
  success: CheckCircle,
  error: AlertCircle,
  warning: AlertTriangle,
  info: Info,
}

export const Alert = ({
  severity,
  children,
  onClose,
  className,
  ...props
}: AlertProps) => {
  const Icon = icons[severity]
  const [visible, setVisible] = useState(true)

  if (!visible) {
    return null
  }

  return (
    <div
      className={cn(
        'rounded-lg border p-4 flex items-start gap-3 text-sm leading-snug',
        severityStyles[severity],
        className
      )}
      {...props}
    >
      <Icon className="w-5 h-5 flex-shrink-0 mt-0.5" />
      <div className="flex-1">{children}</div>
      {onClose && (
        <button
          onClick={() => {
            setVisible(false)
            onClose()
          }}
          className="flex-shrink-0 text-current opacity-70 hover:opacity-100 transition-opacity"
          aria-label="Close"
        >
          <X className="w-4 h-4" />
        </button>
      )}
    </div>
  )
}


