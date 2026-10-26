import { ThemeProvider } from './app/ThemeProvider'
import { WorkspaceProvider } from './app/WorkspaceProvider'
import { BrowserRouter, Link, Navigate, Route, Routes, useLocation, useSearchParams } from 'react-router-dom'
import { lazy, Suspense, useEffect } from 'react'
import { useTheme } from './app/theme'
import { useWorkspaces } from './app/workspace-context'
import { WorkbenchShell } from './components/layout/WorkbenchShell'
import { WorkbenchPage } from './pages/WorkbenchPage'
import { ProposalPage } from './pages/ProposalPage'
import { ManifestPage } from './pages/ManifestPage'
import { AuditPage } from './pages/AuditPage'
import { CoveragePage } from './pages/CoveragePage'

const StyleTile = import.meta.env.DEV ? lazy(() => import('./pages/StyleTilePage').then(module => ({ default: module.StyleTilePage }))) : null

function PreferenceUrlSync() {
  const [search, setSearch] = useSearchParams()
  const { theme } = useTheme()
  const { active } = useWorkspaces()
  const { pathname } = useLocation()
  useEffect(() => {
    const next = new URLSearchParams(search)
    if (pathname.startsWith('/app')) next.set('mode', active.mode)
    if (next.has('theme')) next.set('theme', theme)
    if (next.toString() !== search.toString()) setSearch(next, { replace: true })
  }, [theme, active.mode, pathname, search, setSearch])
  return null
}
function RootRedirect() { const location = useLocation(); return <Navigate to={`/app${location.search}`} replace /> }

function App() {
  return (
    <BrowserRouter>
      <ThemeProvider defaultTheme="light">
        <WorkspaceProvider>
          <PreferenceUrlSync />
          <Routes>
            <Route path="/" element={<RootRedirect />} />
            <Route path="/app" element={<WorkbenchShell />}>
              <Route index element={<WorkbenchPage />} />
              <Route path="proposal"  element={<ProposalPage />} />
              <Route path="manifest"  element={<ManifestPage />} />
              <Route path="audit"     element={<AuditPage />} />
              <Route path="coverage"  element={<CoveragePage />} />
              {/* Legacy redirects */}
              <Route path="payment-request" element={<Navigate to="/app/proposal" replace />} />
              <Route path="approved-plan"   element={<Navigate to="/app/manifest"  replace />} />
              <Route path="record"          element={<Navigate to="/app/audit"     replace />} />
            </Route>
            <Route
              path="/style-tile"
              element={
                StyleTile ? (
                  <Suspense fallback={<main className="route-feedback">Opening design foundations…</main>}>
                    <StyleTile />
                  </Suspense>
                ) : (
                  <Navigate to="/app" replace />
                )
              }
            />
            <Route
              path="*"
              element={
                <main className="route-feedback">
                  <h1>This page is not available.</h1>
                  <p>Your workspaces are still here.</p>
                  <Link to="/app">Return to the workbench</Link>
                </main>
              }
            />
          </Routes>
        </WorkspaceProvider>
      </ThemeProvider>
    </BrowserRouter>
  )
}

export default App
