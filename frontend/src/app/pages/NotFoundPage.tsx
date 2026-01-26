import { Box, Button, Typography } from '@mui/material'
import { useNavigate } from 'react-router-dom'

export const NotFoundPage = () => {
  const navigate = useNavigate()

  return (
    <Box sx={{ textAlign: 'center', mt: 8 }}>
      <Typography variant="h4" sx={{ fontWeight: 700, mb: 2 }}>
        Page not found
      </Typography>
      <Typography color="text.secondary" sx={{ mb: 3 }}>
        The page you requested does not exist.
      </Typography>
      <Button variant="contained" onClick={() => navigate('/')}>
        Back to dashboard
      </Button>
    </Box>
  )
}
