import { useNavigate } from 'react-router-dom'
import { Button } from '../components/ui/Button'
import { Typography } from '../components/ui/Typography'

export const NotFoundPage = () => {
  const navigate = useNavigate()

  return (
    <div className="text-center mt-16">
      <Typography variant="h4" className="mb-4">
        Page not found
      </Typography>
      <Typography color="secondary" className="mb-6">
        The page you requested does not exist.
      </Typography>
      <Button variant="contained" onClick={() => navigate('/')}>
        Back to dashboard
      </Button>
    </div>
  )
}
