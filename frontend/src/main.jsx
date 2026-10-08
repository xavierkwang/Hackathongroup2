import React from 'react'
import { createRoot } from 'react-dom/client'
import App from './App.jsx'
import { handleRedirect } from './auth'
import './styles.css'

handleRedirect().finally(() => {
  createRoot(document.getElementById('root')).render(
    <React.StrictMode>
      <App />
    </React.StrictMode>,
  )
})
