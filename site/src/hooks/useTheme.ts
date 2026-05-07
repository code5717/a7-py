import { useEffect, useMemo, useState } from 'react'

export type ThemePreference = 'system' | 'light' | 'dark'
type ResolvedTheme = 'light' | 'dark'

const STORAGE_KEY = 'a7-docs-theme'

function readStoredPreference(): ThemePreference {
  if (typeof window === 'undefined') {
    return 'system'
  }

  const stored = window.localStorage.getItem(STORAGE_KEY)
  return stored === 'light' || stored === 'dark' || stored === 'system' ? stored : 'system'
}

function hasDarkExtensionActive() {
  const html = document.documentElement
  const body = document.body

  if (
    html.hasAttribute('data-darkreader-mode')
    || html.hasAttribute('data-darkreader-scheme')
    || html.classList.contains('darkreader')
    || body?.classList.contains('darkreader')
  ) {
    return true
  }

  return Boolean(
    document.querySelector(
      'style.darkreader, link.darkreader, meta[name="darkreader"], style[data-darkreader], style[id*="dark-reader"]',
    ),
  )
}

export function useTheme() {
  const [preference, setPreference] = useState<ThemePreference>(() => readStoredPreference())
  const [prefersDark, setPrefersDark] = useState(false)
  const [darkExtensionActive, setDarkExtensionActive] = useState(false)

  useEffect(() => {
    const media = window.matchMedia('(prefers-color-scheme: dark)')
    const updatePreference = () => setPrefersDark(media.matches)

    updatePreference()
    media.addEventListener('change', updatePreference)

    return () => media.removeEventListener('change', updatePreference)
  }, [])

  useEffect(() => {
    const updateExtensionState = () => setDarkExtensionActive(hasDarkExtensionActive())

    updateExtensionState()

    const observer = new MutationObserver(updateExtensionState)
    observer.observe(document.documentElement, { attributes: true })
    if (document.body) {
      observer.observe(document.body, { attributes: true, childList: true })
    }

    return () => observer.disconnect()
  }, [])

  const resolvedTheme = useMemo<ResolvedTheme>(() => {
    if (preference === 'dark') {
      return 'dark'
    }

    if (preference === 'light') {
      return 'light'
    }

    return prefersDark ? 'dark' : 'light'
  }, [preference, prefersDark])

  useEffect(() => {
    window.localStorage.setItem(STORAGE_KEY, preference)
  }, [preference])

  useEffect(() => {
    const root = document.documentElement
    root.dataset.themePreference = preference
    root.dataset.theme = resolvedTheme
    root.dataset.darkExtensionActive = darkExtensionActive ? 'true' : 'false'
    root.style.colorScheme = resolvedTheme
  }, [darkExtensionActive, preference, resolvedTheme])

  const cycleTheme = () => {
    setPreference((current) => {
      if (current === 'system') {
        return 'light'
      }

      if (current === 'light') {
        return 'dark'
      }

      return 'system'
    })
  }

  return {
    preference,
    resolvedTheme,
    darkExtensionActive,
    setPreference,
    cycleTheme,
  }
}
