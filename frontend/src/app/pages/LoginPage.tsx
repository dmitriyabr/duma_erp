import { School } from 'lucide-react'
import { useEffect, useState } from 'react'
import { useLocation, useNavigate } from 'react-router-dom'
import { useAuth } from '../auth/AuthContext'
import { Input } from '../components/ui/Input'
import { Button } from '../components/ui/Button'
import { Alert } from '../components/ui/Alert'
import { Checkbox } from '../components/ui/Checkbox'
import { Typography } from '../components/ui/Typography'

export const LoginPage = () => {
  const { login, user } = useAuth()
  const navigate = useNavigate()
  const location = useLocation()
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [remember, setRemember] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [isSubmitting, setIsSubmitting] = useState(false)

  useEffect(() => {
    if (user) {
      navigate('/')
    }
  }, [user, navigate])

  const handleSubmit = async (event: React.FormEvent) => {
    event.preventDefault()
    setError(null)
    setIsSubmitting(true)
    try {
      await login({ email, password, remember })
      const redirectTo = (location.state as { from?: string })?.from || '/'
      navigate(redirectTo)
    } catch {
      setError('Invalid credentials or server error. Try again.')
    } finally {
      setIsSubmitting(false)
    }
  }

  return (
    <div className="min-h-screen flex bg-gradient-to-br from-slate-900 to-slate-800">
      {/* Left side - Branding */}
      <div className="hidden md:flex flex-1 flex-col justify-center items-center p-12">
        <div className="w-20 h-20 rounded-xl bg-gradient-to-br from-primary to-primary-dark flex items-center justify-center mb-6 shadow-2xl shadow-primary/40">
          <School className="w-12 h-12 text-white" />
        </div>
        <Typography variant="h1" className="text-white text-center mb-4">
          School ERP
        </Typography>
        <Typography variant="body1" className="text-slate-300 text-center max-w-md text-lg leading-relaxed">
          Complete school management system for billing, inventory, procurement, and more.
        </Typography>
      </div>

      {/* Right side - Login form */}
      <div className="flex-1 md:flex-[0_0_480px] flex items-center justify-center p-6 bg-slate-50 md:rounded-l-[32px]">
        <div className="w-full max-w-md">
          <div className="flex justify-center md:hidden mb-6">
            <div className="w-14 h-14 rounded-lg bg-gradient-to-br from-primary to-primary-dark flex items-center justify-center">
              <School className="w-8 h-8 text-white" />
            </div>
          </div>

          <Typography variant="h4" className="mb-1 text-center md:text-left">
            Welcome back
          </Typography>
          <Typography variant="body2" color="secondary" className="mb-8 text-center md:text-left">
            Enter your credentials to access your account
          </Typography>

          {error && (
            <Alert severity="error" className="mb-6">
              {error}
            </Alert>
          )}

          <form onSubmit={handleSubmit} className="space-y-4">
            <Input
              label="Email address"
              type="email"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              required
              autoComplete="email"
            />
            <Input
              label="Password"
              type="password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              required
              autoComplete="current-password"
            />
            <Checkbox
              label="Remember me"
              checked={remember}
              onChange={(e) => setRemember(e.target.checked)}
            />
            <Button
              type="submit"
              variant="contained"
              fullWidth
              size="large"
              disabled={isSubmitting}
            >
              {isSubmitting ? 'Signing in...' : 'Sign in'}
            </Button>
          </form>

          <Typography variant="caption" color="secondary" className="mt-8 text-center block">
            Demo: admin@school.com / Admin123!
          </Typography>
        </div>
      </div>
    </div>
  )
}
