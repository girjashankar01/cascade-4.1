import { Link, useLocation } from 'react-router-dom'
import { useWorkspaces } from '../app/workspace-context'
import { Icon } from '../components/ui/Icon'

const descriptions: Record<string, { title: string; empty: string }> = {
  '/app/payment-request': { title: 'Payment request', empty: 'No payment request is open in this workspace.' },
  '/app/approved-plan': { title: 'Approved plan', empty: 'No approved plan record is open in this workspace.' },
  '/app/record': { title: 'Record of what happened', empty: 'No completed check has been recorded in this workspace.' },
  '/app/coverage': { title: 'What this does and does not cover', empty: 'This local demonstration checks defined payments and software changes. It does not prove that every contract or every possible effect is safe.' },
}
export function WorkspacePage() {
  const { active } = useWorkspaces()
  const location = useLocation()
  const page = descriptions[location.pathname.replace(/\/+$/, '')]
  return <section className="workspace-empty-page"><h1>{page.title}</h1><p>{page.empty}</p><p>{active.scenario ? 'Your selected scenario stays in this workspace when you return to the workbench.' : 'Start by choosing a scenario in the workbench.'}</p><Link className="workspace-text-link" to={{ pathname: '/app', search: location.search }}>Return to the workbench <Icon name="arrow" /></Link></section>
}
