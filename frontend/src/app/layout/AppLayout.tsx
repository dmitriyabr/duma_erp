import { Outlet } from 'react-router-dom'
import { SidebarNav, drawerWidth } from './SidebarNav'
import { TopBar } from './TopBar'

export const AppLayout = () => {
  return (
    <div className="flex min-h-screen bg-slate-50">
      <SidebarNav />
      <div 
        className="flex-1 flex flex-col overflow-hidden"
        style={{ marginLeft: drawerWidth }}
      >
        <TopBar />
        <main className="flex-1 p-8 overflow-y-auto">
          <Outlet />
        </main>
      </div>
    </div>
  )
}
