import { Component, type ErrorInfo, type ReactNode } from 'react'
import { Typography, Button } from './ui'

interface Props {
  children: ReactNode
  fallback?: ReactNode
}

interface State {
  hasError: boolean
  error: Error | null
}

/**
 * Catches unhandled errors in the tree and shows a fallback UI instead of a blank screen.
 * Wrap route/layout content so one failing component does not break the whole app.
 */
export class ErrorBoundary extends Component<Props, State> {
  constructor(props: Props) {
    super(props)
    this.state = { hasError: false, error: null }
  }

  static getDerivedStateFromError(error: Error): State {
    return { hasError: true, error }
  }

  componentDidCatch(error: Error, errorInfo: ErrorInfo) {
    console.error('ErrorBoundary caught:', error, errorInfo)
  }

  handleRetry = () => {
    this.setState({ hasError: false, error: null })
  }

  handleBack = () => {
    window.history.back()
  }

  render() {
    if (this.state.hasError && this.state.error) {
      if (this.props.fallback) {
        return this.props.fallback
      }
      return (
        <div className="flex flex-col items-center justify-center min-h-[280px] p-6 text-center">
          <Typography variant="h6" color="error" className="mb-2">
            Something went wrong
          </Typography>
          <Typography variant="body2" color="secondary" className="mb-4 max-w-[400px]">
            {this.state.error.message}
          </Typography>
          <div className="flex gap-2">
            <Button variant="outlined" onClick={this.handleBack}>
              Go back
            </Button>
            <Button variant="contained" onClick={this.handleRetry}>
              Try again
            </Button>
          </div>
        </div>
      )
    }
    return this.props.children
  }
}
