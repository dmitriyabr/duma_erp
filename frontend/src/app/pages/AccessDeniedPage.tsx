import { Box, Button, Typography } from '@mui/material'
import { useNavigate } from 'react-router-dom'

export const AccessDeniedPage = () => {
  const navigate = useNavigate()

  return (
    <Box sx={{ textAlign: 'center', mt: 8 }}>
      <Typography variant="h4" sx={{ fontWeight: 700, mb: 2 }}>
        Access denied
      </Typography>
      <Typography color="text.secondary" sx={{ mb: 3 }}>
        You do not have permission to view this page.
      </Typography>
      <Button variant="contained" onClick={() => navigate('/')}>
        Back to dashboard
      </Button>
    </Box>
  )
}
