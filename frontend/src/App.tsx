import { useEffect } from 'react'
import { AuthProvider } from './app/auth/AuthContext'
import { AppRoutes } from './app/routes'

function App() {
  useEffect(() => {
    const handleWheel = (event: WheelEvent) => {
      const activeElement = document.activeElement
      if (
        activeElement instanceof HTMLInputElement &&
        activeElement.type === 'number'
      ) {
        activeElement.blur()
        event.preventDefault()
      }
    }

    window.addEventListener('wheel', handleWheel, { passive: false })
    return () => {
      window.removeEventListener('wheel', handleWheel)
    }
  }, [])

  return (
    <AuthProvider>
      <AppRoutes />
    </AuthProvider>
  )
}

export default App
