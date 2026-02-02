import { useNavigate } from 'react-router-dom'
import { Button } from '../components/ui/Button'
import { Typography } from '../components/ui/Typography'

export const AccessDeniedPage = () => {
  const navigate = useNavigate()

  return (
    <div className="text-center mt-16">
      <Typography variant="h4" className="mb-4">
        Access denied
      </Typography>
      <Typography color="secondary" className="mb-6">
        You do not have permission to view this page.
      </Typography>
      <Button variant="contained" onClick={() => navigate('/')}>
        Back to dashboard
      </Button>
    </div>
  )
}
