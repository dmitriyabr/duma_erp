import { Outlet, useNavigate, useLocation } from 'react-router-dom'
import { Tabs, TabsList, Tab } from '../../components/ui/Tabs'

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

  const handleChange = (newValue: string) => {
    navigate(newValue)
  }

  return (
    <div>
      <Tabs
        value={value}
        onChange={handleChange}
        className="border-b border-slate-200 mb-4"
      >
        <TabsList>
          {tabs.map((t) => (
            <Tab key={t.path} value={`${basePath}/${t.path}`}>
              {t.label}
            </Tab>
          ))}
        </TabsList>
      </Tabs>
      <Outlet />
    </div>
  )
}
