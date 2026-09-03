import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import './index.css'
import App from './App'
import { AuthProvider } from './context/AuthProvider'

const rootElement = document.getElementById('root')

if (!rootElement) {
    throw new Error('Impossible de trouver l’élément racine de l’application.')
}

createRoot(rootElement).render(
    <StrictMode>
        <AuthProvider><App /></AuthProvider>
    </StrictMode>,
)
