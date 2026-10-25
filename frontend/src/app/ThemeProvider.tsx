import { useLayoutEffect, useState } from 'react'
import type { ReactNode } from 'react'
import { ThemeContext } from './theme'
import type { Theme } from './theme'

function initialTheme(defaultTheme: Theme): Theme {
  const requested = new URLSearchParams(window.location.search).get('theme')
  if (requested === 'light' || requested === 'dark') return requested
  try {
    const stored = localStorage.getItem('dao-theme')
    if (stored === 'light' || stored === 'dark') return stored
  } catch { /* A blocked store must never prevent rendering. */ }
  return defaultTheme
}

export function ThemeProvider({ children, defaultTheme = 'light' }: { children: ReactNode; defaultTheme?: Theme }) {
  const [theme, setTheme] = useState<Theme>(() => initialTheme(defaultTheme))
  const [reduceMotion, setMotionPreference] = useState(() => {
    try { return localStorage.getItem('dao-reduce-motion') === 'true' } catch { return false }
  })
  useLayoutEffect(() => { document.documentElement.dataset.theme = theme }, [theme])
  useLayoutEffect(() => { document.documentElement.dataset.reduceMotion = String(reduceMotion) }, [reduceMotion])
  function setReduceMotion(value: boolean) {
    setMotionPreference(value)
    try { localStorage.setItem('dao-reduce-motion', String(value)) } catch { /* Session preference remains available. */ }
  }
  function toggleTheme() {
    const next = theme === 'light' ? 'dark' : 'light'
    setTheme(next)
    try { localStorage.setItem('dao-theme', next) } catch { /* Session state still works. */ }
  }
  return <ThemeContext.Provider value={{ theme, toggleTheme, reduceMotion, setReduceMotion }}>{children}</ThemeContext.Provider>
}
