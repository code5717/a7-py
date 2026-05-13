import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import { BrowserRouter } from 'react-router-dom'
import './styles/global.css'
import App from './App'

const recovered = sessionStorage.getItem('a7:redirect')
if (recovered) {
  sessionStorage.removeItem('a7:redirect')
  if (recovered !== window.location.pathname + window.location.search + window.location.hash) {
    window.history.replaceState(null, '', recovered)
  }
}

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <BrowserRouter basename="/a7-py">
      <App />
    </BrowserRouter>
  </StrictMode>,
)
