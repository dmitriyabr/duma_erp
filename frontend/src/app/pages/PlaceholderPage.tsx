import { Typography } from '../components/ui/Typography'

interface PlaceholderPageProps {
  title: string
  description?: string
}

export const PlaceholderPage = ({ title, description }: PlaceholderPageProps) => {
  return (
    <div>
      <Typography variant="h4" className="mb-2">
        {title}
      </Typography>
      <Typography color="secondary">
        {description ?? 'This section will be available soon.'}
      </Typography>
    </div>
  )
}
