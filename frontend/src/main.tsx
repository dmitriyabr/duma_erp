import { createRoot } from 'react-dom/client'
import './index.css'
import App from './App.tsx'

// StrictMode disabled: in dev it double-invokes effects, so every useApi request ran twice.
// Re-enable <StrictMode> when you want to catch side-effect bugs (recommended for new code).
createRoot(document.getElementById('root')!).render(<App />)
