import { School, ChevronDown, ChevronUp } from 'lucide-react'
import { useEffect, useMemo, useState } from 'react'
import { NavLink, useLocation } from 'react-router-dom'
import { accountantNavItems, navItems } from '../navigation/navItems'
import { useAuth } from '../auth/AuthContext'
import { cn } from '../utils/cn'

export const drawerWidth = 280

type SidebarNavProps = {
  mobileOpen?: boolean
  onMobileClose?: () => void
}

export const SidebarNav = ({ mobileOpen = false, onMobileClose }: SidebarNavProps) => {
  const { user } = useAuth()
  const location = useLocation()
  const [openGroups, setOpenGroups] = useState<Record<string, boolean>>({})

  const role = user?.role
  const availableItems = useMemo(() => {
    if (!role) {
      return []
    }
    if (role === 'Accountant') {
      return accountantNavItems
    }
    return navItems.filter((item) => item.roles.includes(role))
  }, [role])

  const toggleGroup = (label: string) => {
    setOpenGroups((prev) => ({ ...prev, [label]: !prev[label] }))
  }

  useEffect(() => {
    if (mobileOpen) {
      onMobileClose?.()
    }
    // Close drawer on navigation
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [location.pathname])

  const NavContent = (
    <div
      className="h-full flex flex-col bg-gradient-to-b from-slate-800 to-slate-900 text-slate-200"
      style={{ width: drawerWidth }}
    >
      <div className="px-6 py-6 flex items-center gap-3">
        <div className="w-10 h-10 rounded-lg bg-gradient-to-br from-primary to-primary-dark flex items-center justify-center">
          <School className="w-6 h-6 text-white" />
        </div>
        <div>
          <h1 className="text-lg font-bold text-white tracking-tight">School ERP</h1>
          <p className="text-xs text-slate-400">Management System</p>
        </div>
      </div>

      <nav className="px-3 py-2 flex-1 overflow-y-auto">
        <ul className="space-y-1">
          {availableItems.map((item) => {
            const hasChildren = !!item.children?.length
            const isChildActive = item.children?.some(
              (child) =>
                location.pathname === child.path ||
                (child.path !== item.path && location.pathname.startsWith(child.path + '/'))
            )
            const isActive = location.pathname === item.path || isChildActive
            const isGroupOpen = openGroups[item.label] ?? !!isChildActive

            return (
              <li key={item.label}>
                {hasChildren ? (
                  <button
                    onClick={() => toggleGroup(item.label)}
                    className={cn(
                      'w-full flex items-center gap-3 px-4 py-3 rounded-lg mb-1 transition-colors',
                      isActive
                        ? 'bg-primary/20 text-white'
                        : 'text-slate-400 hover:bg-white/5 hover:text-white'
                    )}
                  >
                    {item.icon && (
                      <span className={cn('flex-shrink-0', isActive ? 'text-primary-light' : 'text-slate-500')}>
                        {item.icon}
                      </span>
                    )}
                    <span className={cn('flex-1 text-sm text-left', isActive ? 'font-semibold' : 'font-medium')}>
                      {item.label}
                    </span>
                    {isGroupOpen ? (
                      <ChevronUp className="w-4 h-4 opacity-70" />
                    ) : (
                      <ChevronDown className="w-4 h-4 opacity-70" />
                    )}
                  </button>
                ) : (
                  <NavLink
                    to={item.path}
                    className={cn(
                      'flex items-center gap-3 px-4 py-3 rounded-lg mb-1 transition-colors',
                      isActive
                        ? 'bg-primary/20 text-white'
                        : 'text-slate-400 hover:bg-white/5 hover:text-white'
                    )}
                  >
                    {item.icon && (
                      <span className={cn('flex-shrink-0', isActive ? 'text-primary-light' : 'text-slate-500')}>
                        {item.icon}
                      </span>
                    )}
                    <span className={cn('text-sm', isActive ? 'font-semibold' : 'font-medium')}>
                      {item.label}
                    </span>
                  </NavLink>
                )}
                {hasChildren && (
                  <div
                    className={cn(
                      'overflow-hidden transition-all duration-200',
                      isGroupOpen ? 'max-h-96 opacity-100' : 'max-h-0 opacity-0'
                    )}
                  >
                    <ul className="pl-2 space-y-0.5 mt-0.5">
                      {item.children?.map((child) => {
                        if (!role || !child.roles.includes(role)) {
                          return null
                        }
                        const isChildItemActive =
                          location.pathname === child.path ||
                          location.pathname.startsWith(child.path + '/')
                        return (
                          <li key={child.label}>
                            <NavLink
                              to={child.path}
                              className={cn(
                                'flex items-center px-4 py-2 rounded-lg text-sm transition-colors relative',
                                isChildItemActive
                                  ? 'bg-primary/15 text-white font-semibold'
                                  : 'text-slate-400 hover:bg-white/5 hover:text-white'
                              )}
                            >
                              {isChildItemActive && (
                                <span className="absolute left-0 top-1/2 -translate-y-1/2 w-1 h-5 bg-primary rounded-r" />
                              )}
                              <span>{child.label}</span>
                            </NavLink>
                          </li>
                        )
                      })}
                    </ul>
                  </div>
                )}
              </li>
            )
          })}
        </ul>
      </nav>

      <div className="px-6 py-4 border-t border-white/10">
        <p className="text-xs text-slate-500">Version 1.0.0</p>
      </div>
    </div>
  )

  return (
    <>
      {/* Desktop sidebar */}
      <aside className="hidden lg:fixed lg:left-0 lg:top-0 lg:block lg:h-full lg:flex-shrink-0 z-50" style={{ width: drawerWidth }}>
        {NavContent}
      </aside>

      {/* Mobile drawer */}
      <div className={cn('lg:hidden fixed inset-0 z-50', mobileOpen ? 'block' : 'hidden')}>
        <button
          type="button"
          aria-label="Close navigation"
          className="absolute inset-0 bg-black/40"
          onClick={() => onMobileClose?.()}
        />
        <div
          className={cn(
            'absolute left-0 top-0 h-full shadow-2xl transform transition-transform duration-200',
            mobileOpen ? 'translate-x-0' : '-translate-x-full'
          )}
        >
          {NavContent}
        </div>
      </div>
    </>
  )
}
