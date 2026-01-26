import { Box, Typography } from '@mui/material'

interface PlaceholderPageProps {
  title: string
  description?: string
}

export const PlaceholderPage = ({ title, description }: PlaceholderPageProps) => {
  return (
    <Box>
      <Typography variant="h4" sx={{ fontWeight: 700, mb: 1 }}>
        {title}
      </Typography>
      <Typography color="text.secondary">
        {description ?? 'This section will be available soon.'}
      </Typography>
    </Box>
  )
}
