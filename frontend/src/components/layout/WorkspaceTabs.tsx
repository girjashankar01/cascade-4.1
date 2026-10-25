import { useEffect, useLayoutEffect, useRef, useState } from 'react'
import { useWorkspaces } from '../../app/workspace-context'
import { Button } from '../ui/Button'
import { Icon } from '../ui/Icon'

export function WorkspaceTabs() {
  const { state, active, dispatch } = useWorkspaces()
  const [renaming, setRenaming] = useState(false)
  const [name, setName] = useState('')
  const [invalid, setInvalid] = useState(false)
  const dialog = useRef<HTMLDialogElement>(null)
  const tabs = useRef<HTMLDivElement>(null)
  useLayoutEffect(() => {
    const keepActiveVisible = () => document.getElementById(`workspace-tab-${active.id}`)?.scrollIntoView({ block: 'nearest', inline: 'nearest', behavior: 'instant' })
    keepActiveVisible()
    const observer = new ResizeObserver(keepActiveVisible)
    if (tabs.current) observer.observe(tabs.current)
    return () => observer.disconnect()
  }, [active.id])
  useEffect(() => {
    if (renaming) dialog.current?.showModal()
    else dialog.current?.close()
  }, [renaming])
  function activate(id: string) { dispatch({ type: 'activate', id }); document.getElementById(`workspace-tab-${id}`)?.focus() }
  return <>
    <div className="workspace-bar">
      <div ref={tabs} className="workspace-tabs" role="tablist" aria-label="Scenario workspaces">
        {state.items.map((workspace, index) => <button key={workspace.id} id={`workspace-tab-${workspace.id}`} type="button" role="tab" aria-selected={workspace.id === active.id} aria-controls="workspace-panel" tabIndex={workspace.id === active.id ? 0 : -1} className={`workspace-tab ${workspace.id === active.id ? 'is-active' : ''}`} onClick={() => dispatch({ type: 'activate', id: workspace.id })} onKeyDown={event => {
          const next = event.key === 'ArrowRight' ? (index + 1) % state.items.length : event.key === 'ArrowLeft' ? (index - 1 + state.items.length) % state.items.length : event.key === 'Home' ? 0 : event.key === 'End' ? state.items.length - 1 : -1
          if (next >= 0) { event.preventDefault(); activate(state.items[next].id) }
        }}><Icon name="workspace" /><span>{workspace.name}</span>{workspace.phase === 'running' && <span className="visually-hidden">Check in progress</span>}</button>)}
      </div>
      <Button variant="quiet" className="new-workspace" aria-label="Open a new workspace" onClick={() => dispatch({ type: 'add', id: crypto.randomUUID() })}><Icon name="plus" /><span>New</span></Button>
    </div>
    <div className="workspace-tools"><span>Each tab keeps its own scenario and record.</span><div><Button variant="quiet" onClick={() => { setName(active.name); setInvalid(false); setRenaming(true) }}><Icon name="edit" />Rename</Button><Button variant="quiet" disabled={active.phase === 'running'} onClick={() => dispatch({ type: 'close', id: active.id })}><Icon name="close" />Close<span className="visually-hidden"> current workspace</span></Button></div></div>
    <dialog ref={dialog} className="rename-dialog" aria-labelledby="rename-title" onCancel={() => setRenaming(false)} onClose={() => setRenaming(false)}>
      {renaming && <form onSubmit={event => { event.preventDefault(); if (!name.trim()) { setInvalid(true); return }; dispatch({ type: 'rename', id: active.id, name }); setRenaming(false) }}><h2 id="rename-title">Name this workspace</h2><p>A short name makes sessions easier to compare.</p><label htmlFor="workspace-name">Workspace name</label><input id="workspace-name" autoFocus maxLength={40} value={name} aria-invalid={invalid} aria-describedby={invalid ? 'name-error' : undefined} onChange={event => { setName(event.target.value); setInvalid(false) }} />{invalid && <p id="name-error" role="alert">Enter a name for this workspace.</p>}<div className="dialog-actions"><Button variant="secondary" onClick={() => setRenaming(false)}>Cancel</Button><Button type="submit">Save name</Button></div></form>}
    </dialog>
  </>
}
