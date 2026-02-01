import { Box, Tabs, Tab } from '@mui/material'
import { Outlet, useNavigate, useLocation } from 'react-router-dom'

export interface ReportsTab { path: string; label: string }

interface ReportsSectionLayoutProps {
  basePath: string
  tabs: ReportsTab[]
}

export function ReportsSectionLayout({ basePath, tabs }: ReportsSectionLayoutProps) {
  const location = useLocation()
  const navigate = useNavigate()
  const pathname = location.pathname
  const activeTab = tabs.find((t) => pathname === `${basePath}/${t.path}`)
  const value = activeTab ? `${basePath}/${activeTab.path}` : (tabs[0] ? `${basePath}/${tabs[0].path}` : '')

  const handleChange = (_: React.SyntheticEvent, newValue: string) => {
    navigate(newValue)
  }

  return (
    <Box>
      <Tabs
        value={value}
        onChange={handleChange}
        sx={{ borderBottom: 1, borderColor: 'divider', mb: 2, minHeight: 40 }}
      >
        {tabs.map((t) => (
          <Tab key={t.path} label={t.label} value={`${basePath}/${t.path}`} sx={{ minHeight: 40, py: 1 }} />
        ))}
      </Tabs>
      <Outlet />
    </Box>
  )
}
