import { Outlet } from 'react-router-dom'
import { SidebarNav } from './SidebarNav'
import { TopBar } from './TopBar'
import { useState } from 'react'

export const AppLayout = () => {
  const [mobileNavOpen, setMobileNavOpen] = useState(false)

  return (
    <div className="flex min-h-screen bg-slate-50">
      <SidebarNav mobileOpen={mobileNavOpen} onMobileClose={() => setMobileNavOpen(false)} />
      <div 
        className="flex-1 flex flex-col overflow-hidden lg:ml-[280px]"
      >
        <TopBar onOpenNav={() => setMobileNavOpen(true)} />
        <main className="flex-1 p-4 sm:p-6 lg:p-8 overflow-y-auto">
          <Outlet />
        </main>
      </div>
    </div>
  )
}
