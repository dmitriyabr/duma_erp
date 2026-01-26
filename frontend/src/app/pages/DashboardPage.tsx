import { Box, Card, CardContent, Typography } from '@mui/material'

const metrics = [
  { label: 'Active Students', value: '—' },
  { label: 'Outstanding Invoices', value: '—' },
  { label: 'Payments (This Month)', value: '—' },
  { label: 'Stock Alerts', value: '—' },
]

export const DashboardPage = () => {
  return (
    <Box>
      <Typography variant="h4" sx={{ fontWeight: 700, mb: 3 }}>
        Dashboard
      </Typography>
      <Box
        sx={{
          display: 'grid',
          gridTemplateColumns: {
            xs: '1fr',
            sm: 'repeat(2, 1fr)',
            md: 'repeat(4, 1fr)',
          },
          gap: 2,
        }}
      >
        {metrics.map((metric) => (
          <Card key={metric.label}>
            <CardContent>
              <Typography variant="body2" color="text.secondary">
                {metric.label}
              </Typography>
              <Typography variant="h5" sx={{ mt: 1 }}>
                {metric.value}
              </Typography>
            </CardContent>
          </Card>
        ))}
      </Box>
    </Box>
  )
}
