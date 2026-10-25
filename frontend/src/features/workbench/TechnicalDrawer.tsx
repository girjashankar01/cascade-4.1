import { useRef, useState } from 'react'
import { Button } from '../../components/ui/Button'
import { getDataService } from '../../data/api'
import { technicalRows } from '../../data/technical'
import type { RunResult } from '../../data/types'

export function TechnicalDrawer({ result }: { result: RunResult | null }) {
  const dialog = useRef<HTMLDialogElement>(null)
  const trigger = useRef<HTMLButtonElement>(null)
  const [feedback, setFeedback] = useState('')
  const rows = result ? technicalRows(result, getDataService().technicalEvidence(result.id)) : []
  async function copy(label: string, value: string) {
    try { await navigator.clipboard.writeText(value); setFeedback(`${label} copied.`) }
    catch { setFeedback('Copy is unavailable. Select the value to copy it manually.') }
  }
  return <>
    <Button variant="secondary" ref={trigger} onClick={() => { setFeedback(''); dialog.current?.showModal() }}>Show technical details</Button>
    <dialog className="technical-drawer" ref={dialog} aria-labelledby="technical-title" onClose={() => trigger.current?.focus()} onKeyDown={event => {
      if (event.key !== 'Tab') return
      const controls = Array.from(event.currentTarget.querySelectorAll<HTMLButtonElement>('button:not([disabled])'))
      const first = controls[0], last = controls.at(-1)
      if (event.shiftKey && document.activeElement === first) { event.preventDefault(); last?.focus() }
      else if (!event.shiftKey && document.activeElement === last) { event.preventDefault(); first?.focus() }
    }}>
      <div className="drawer-heading"><h2 id="technical-title">Technical details</h2><Button autoFocus variant="quiet" onClick={() => dialog.current?.close()}>Close details</Button></div>
      <p>Local demonstration. No real money. Only the recorded evidence is shown.</p>
      {!result ? <p>Run a safety check to create a record.</p> : <><p>{result.source === 'demo' ? 'Demo data uses authored examples. No transaction was sent to a chain.' : 'This record comes from the local service. Balance readings are reported, not independently verified.'}</p><dl className="technical-values">{rows.map(row => <div key={row.label}><dt>{row.label}</dt><dd><code title={row.value}>{/^0x/.test(row.value) ? `${row.value.slice(0, 10)}…${row.value.slice(-6)}` : row.value}</code><Button variant="quiet" aria-label={`Copy ${row.label.toLowerCase()}`} onClick={() => copy(row.label, row.value)}>Copy</Button></dd></div>)}</dl></>}
      <p role="status">{feedback}</p>
    </dialog>
  </>
}
