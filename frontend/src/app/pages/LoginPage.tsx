import {
  Alert,
  Box,
  Button,
  Checkbox,
  FormControlLabel,
  Paper,
  TextField,
  Typography,
} from '@mui/material'
import SchoolIcon from '@mui/icons-material/School'
import { useEffect, useState } from 'react'
import { useLocation, useNavigate } from 'react-router-dom'
import { useAuth } from '../auth/AuthContext'

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
    <Box
      sx={{
        minHeight: '100vh',
        display: 'flex',
        background: 'linear-gradient(135deg, #1e293b 0%, #0f172a 100%)',
      }}
    >
      {/* Left side - Branding */}
      <Box
        sx={{
          flex: 1,
          display: { xs: 'none', md: 'flex' },
          flexDirection: 'column',
          justifyContent: 'center',
          alignItems: 'center',
          p: 6,
        }}
      >
        <Box
          sx={{
            width: 80,
            height: 80,
            borderRadius: 3,
            background: 'linear-gradient(135deg, #6366f1 0%, #4f46e5 100%)',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            mb: 3,
            boxShadow: '0 20px 40px -10px rgba(99, 102, 241, 0.4)',
          }}
        >
          <SchoolIcon sx={{ color: 'white', fontSize: 48 }} />
        </Box>
        <Typography
          variant="h3"
          sx={{
            fontWeight: 700,
            color: '#ffffff',
            textAlign: 'center',
            mb: 2,
          }}
        >
          School ERP
        </Typography>
        <Typography
          sx={{
            color: '#94a3b8',
            textAlign: 'center',
            maxWidth: 400,
            fontSize: '1.125rem',
            lineHeight: 1.6,
          }}
        >
          Complete school management system for billing, inventory, procurement, and more.
        </Typography>
      </Box>

      {/* Right side - Login form */}
      <Box
        sx={{
          flex: { xs: 1, md: '0 0 480px' },
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          p: 3,
          backgroundColor: '#f8fafc',
          borderRadius: { xs: 0, md: '32px 0 0 32px' },
        }}
      >
        <Paper
          elevation={0}
          sx={{
            p: 5,
            width: '100%',
            maxWidth: 400,
            backgroundColor: 'transparent',
          }}
        >
          <Box sx={{ display: { xs: 'flex', md: 'none' }, justifyContent: 'center', mb: 3 }}>
            <Box
              sx={{
                width: 56,
                height: 56,
                borderRadius: 2,
                background: 'linear-gradient(135deg, #6366f1 0%, #4f46e5 100%)',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
              }}
            >
              <SchoolIcon sx={{ color: 'white', fontSize: 32 }} />
            </Box>
          </Box>

          <Typography
            variant="h4"
            sx={{
              fontWeight: 700,
              mb: 1,
              color: '#1e293b',
              textAlign: { xs: 'center', md: 'left' },
            }}
          >
            Welcome back
          </Typography>
          <Typography
            sx={{
              color: '#64748b',
              mb: 4,
              textAlign: { xs: 'center', md: 'left' },
            }}
          >
            Enter your credentials to access your account
          </Typography>

          {error ? (
            <Alert severity="error" sx={{ mb: 3 }}>
              {error}
            </Alert>
          ) : null}

          <Box component="form" onSubmit={handleSubmit}>
            <TextField
              label="Email address"
              value={email}
              onChange={(event) => setEmail(event.target.value)}
              fullWidth
              margin="normal"
              type="email"
              required
              autoComplete="email"
              sx={{ mb: 2 }}
            />
            <TextField
              label="Password"
              value={password}
              onChange={(event) => setPassword(event.target.value)}
              fullWidth
              margin="normal"
              type="password"
              required
              autoComplete="current-password"
              sx={{ mb: 1 }}
            />
            <FormControlLabel
              control={
                <Checkbox
                  checked={remember}
                  onChange={(event) => setRemember(event.target.checked)}
                  sx={{
                    color: '#94a3b8',
                    '&.Mui-checked': {
                      color: '#6366f1',
                    },
                  }}
                />
              }
              label={
                <Typography sx={{ color: '#64748b', fontSize: '0.875rem' }}>
                  Remember me
                </Typography>
              }
              sx={{ mb: 3 }}
            />
            <Button
              type="submit"
              variant="contained"
              fullWidth
              size="large"
              disabled={isSubmitting}
              sx={{
                py: 1.5,
                fontSize: '1rem',
              }}
            >
              {isSubmitting ? 'Signing in...' : 'Sign in'}
            </Button>
          </Box>

          <Typography
            sx={{
              mt: 4,
              textAlign: 'center',
              color: '#94a3b8',
              fontSize: '0.8125rem',
            }}
          >
            Demo: admin@school.com / Admin123!
          </Typography>
        </Paper>
      </Box>
    </Box>
  )
}
