import { LogOut, User } from 'lucide-react'
import { useState, useRef, useEffect } from 'react'
import { useAuth } from '../auth/AuthContext'

export const TopBar = () => {
  const { user, logout } = useAuth()
  const [menuOpen, setMenuOpen] = useState(false)
  const menuRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    const handleClickOutside = (event: MouseEvent) => {
      if (menuRef.current && !menuRef.current.contains(event.target as Node)) {
        setMenuOpen(false)
      }
    }

    if (menuOpen) {
      document.addEventListener('mousedown', handleClickOutside)
    }

    return () => {
      document.removeEventListener('mousedown', handleClickOutside)
    }
  }, [menuOpen])

  const getInitials = (name: string) => {
    return name
      .split(' ')
      .map((n) => n[0])
      .join('')
      .toUpperCase()
      .slice(0, 2)
  }

  return (
    <header className="sticky top-0 z-30 bg-white border-b border-slate-200 shadow-none">
      <div className="flex items-center justify-between px-6 h-16">
        <div>
          <h2 className="text-lg font-semibold text-slate-800">
            {user ? `Welcome back, ${user.full_name.split(' ')[0]}` : 'School ERP'}
          </h2>
          <p className="text-sm text-slate-500">
            {new Date().toLocaleDateString('en-GB', {
              weekday: 'long',
              year: 'numeric',
              month: 'long',
              day: 'numeric',
            })}
          </p>
        </div>

        <div className="relative" ref={menuRef}>
          <button
            onClick={() => setMenuOpen(!menuOpen)}
            className="p-1 rounded-lg hover:bg-primary/8 transition-colors"
            aria-label="Account menu"
          >
            <div
              className="w-10 h-10 rounded-full bg-gradient-to-br from-primary to-primary-dark flex items-center justify-center text-white text-sm font-semibold"
            >
              {user ? getInitials(user.full_name) : <User className="w-5 h-5" />}
            </div>
          </button>

          {menuOpen && (
            <div className="absolute right-0 top-full mt-2 w-56 bg-white rounded-lg shadow-xl border border-slate-200 overflow-hidden z-50">
              <div className="px-4 py-3 border-b border-slate-200">
                <p className="font-semibold text-slate-800">{user?.full_name}</p>
                <p className="text-sm text-slate-500">{user?.email}</p>
                <span className="inline-block mt-1 px-2 py-0.5 rounded bg-primary/10 text-primary text-xs font-medium">
                  {user?.role}
                </span>
              </div>
              <button
                onClick={() => {
                  setMenuOpen(false)
                  logout()
                }}
                className="w-full flex items-center gap-3 px-4 py-3 text-error hover:bg-error/8 transition-colors"
              >
                <LogOut className="w-5 h-5" />
                <span>Sign out</span>
              </button>
            </div>
          )}
        </div>
      </div>
    </header>
  )
}
