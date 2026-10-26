import { useEffect, useState } from 'react'
import { Link, NavLink, Outlet, useLocation, useNavigate } from 'react-router-dom'
import { useWorkspaces } from '../../app/workspace-context'
import { useTheme } from '../../app/theme'
import { useConnection } from '../../hooks/useConnection'
import { Icon } from '../ui/Icon'
import { Button } from '../ui/Button'
import { ThemeToggle } from '../ui/ThemeToggle'
import { WorkspaceTabs } from './WorkspaceTabs'
import { SectionRail } from './SectionRail'
import './WorkbenchShell.css'

const pages = [
  { to: '/app',             name: 'Execution workbench' },
  { to: '/app/proposal',    name: 'Proposal' },
  { to: '/app/manifest',    name: 'Manifest and versions' },
  { to: '/app/audit',       name: 'Audit record' },
  { to: '/app/coverage',    name: 'What this does and does not cover' },
]

export function WorkbenchShell() {
  const { active, dispatch } = useWorkspaces()
  const { reduceMotion, setReduceMotion } = useTheme()
  const connection = useConnection(active.mode, active.id)
  const navigate = useNavigate()
  const [copyFeedback, setCopyFeedback] = useState({ key: '', message: '' })
  const copyKey = `${active.id}:${active.mode}`
  const copyMessage = copyFeedback.key === copyKey ? copyFeedback.message : ''
  const setCopyMessage = (message: string) => setCopyFeedback({ key: copyKey, message })
  const location = useLocation()
  useEffect(() => { document.title = `${pages.find(page => page.to === location.pathname.replace(/\/+$/, ''))?.name ?? 'Workbench'} | DAO Accountability Engine` }, [location.pathname])
  const unavailable = active.mode === 'live' && !connection.checking && connection.connection?.chain !== 'online'
  return <>
    <a className="skip-link" href="#workbench-main">Skip to content</a>
    <div className="workbench-shell">
      <header className="workbench-header"><Link to="/app" className="workbench-brand"><Icon name="lock" /><span>DAO Accountability Engine</span></Link><div className="workbench-header-actions"><span className="source-label">{active.mode === 'demo' ? 'Demo data · test tokens' : 'Local test service'}</span><ThemeToggle /></div></header>
      <WorkspaceTabs />
      <nav className="workspace-pages" aria-label="Pages in this workspace"><label className="workspace-page-selector" htmlFor="workspace-page">Page<select id="workspace-page" aria-label="Workspace page" value={location.pathname.replace(/\/+$/, '')} onChange={event => navigate({ pathname: event.target.value, search: location.search })}>{pages.map(page => <option key={page.to} value={page.to}>{page.name}</option>)}</select></label>{pages.map(page => <NavLink key={page.to} to={{ pathname: page.to, search: location.search }} end>{page.name}</NavLink>)}</nav>
      <div className="workbench-layout"><SectionRail /><main id="workbench-main" tabIndex={-1}>
        <div id="workspace-panel" role="tabpanel" aria-labelledby={`workspace-tab-${active.id}`} tabIndex={-1}>
          <div className="workspace-context"><p className="workspace-current">{active.name}</p><div className="mode-controls"><label htmlFor="data-mode">Data source</label><select id="data-mode" disabled={active.phase === 'running'} value={active.mode} onChange={event => dispatch({ type: 'mode', id: active.id, mode: event.target.value === 'live' ? 'live' : 'demo' })}><option value="demo">Demo data</option><option value="live">Local service</option></select></div></div>
          <div className="connection-message" role="status"><Icon name={active.mode === 'demo' ? 'details' : 'workspace'} /><span>{connection.checking ? 'Checking the local connection…' : connection.connection?.message ?? 'Preparing this workspace…'}</span>{active.mode === 'live' && !connection.checking && <Button variant="quiet" onClick={connection.retry}>Check again</Button>}</div>
          {unavailable && <div className="service-fallback"><p>You can explore every example with demo data.</p><div className="fallback-actions"><Button variant="secondary" onClick={() => dispatch({ type: 'mode', id: active.id, mode: 'demo' })}>Use demo data</Button><Button variant="quiet" onClick={async () => { try { await navigator.clipboard.writeText(`DAO Accountability Engine — connection check: ${connection.diagnostic || 'CHAIN_UNAVAILABLE'}. No payment run was started by this check.`); setCopyMessage('Details copied.') } catch { setCopyMessage('Copy is unavailable. Ask the developer to check the local service connection.') } }}>Copy details for the developer</Button></div><span role="status" className="copy-feedback">{copyMessage}</span></div>}
          <Outlet context={connection} />
        </div>
        <footer className="workbench-footer"><p>Local demonstration. No real money.</p><label className="preference-control"><input type="checkbox" checked={reduceMotion} onChange={event => setReduceMotion(event.target.checked)} />Reduce motion</label>{import.meta.env.DEV && <Link to="/style-tile">Design foundations</Link>}</footer>
      </main></div>
    </div>
  </>
}
