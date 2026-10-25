import { useReducer, useRef } from 'react'
import type { ReactNode } from 'react'
import { initialWorkspaces, workspaceReducer } from './workspaces'
import { WorkspaceContext } from './workspace-context'
import { getDataService } from '../data/api'
import { DataError } from '../data/types'

export function WorkspaceProvider({ children }: { children: ReactNode }) {
  const [state, dispatch] = useReducer(workspaceReducer, undefined, () => initialWorkspaces(new URLSearchParams(location.search).get('mode') === 'live' ? 'live' : 'demo'))
  const active = state.items.find(item => item.id === state.activeId)!
  const pending = useRef(new Set<string>())
  async function perform(reset: boolean) {
    const workspace = active
    if (pending.current.has(workspace.id) || workspace.phase === 'running' || (!reset && !workspace.scenario)) return
    const service = getDataService()
    if (workspace.mode === 'live' && service.liveOperationPending()) return
    pending.current.add(workspace.id)
    dispatch({ type: reset ? 'begin-reset' : 'start', id: workspace.id })
    try {
      // Only fixtures have authored step timing. Live waiting never claims observed progress.
      if (!reset && workspace.mode === 'demo') {
        const duration = parseFloat(getComputedStyle(document.documentElement).getPropertyValue('--motion-duration-explain')) * 1000
        for (let step = 0; step < 4; step++) {
          dispatch({ type: 'progress', id: workspace.id, step })
          if (duration > 0) await new Promise(resolve => setTimeout(resolve, duration))
        }
      }
      if (reset && workspace.mode === 'demo') {
        await service.reset('demo', workspace.id)
        dispatch({ type: 'reset-done', id: workspace.id })
      } else {
        const result = await service.run(workspace.mode, workspace.id, reset ? 'C' : workspace.scenario!)
        dispatch({ type: 'finish', id: workspace.id, result })
      }
    } catch (error) {
      dispatch({ type: 'fail', id: workspace.id, message: error instanceof DataError ? error.message : 'The check could not finish. Check the record before another live run, or use demo data.' })
    } finally { pending.current.delete(workspace.id) }
  }
  return <WorkspaceContext.Provider value={{ state, active, dispatch, run: () => perform(false), reset: () => perform(true) }}>{children}</WorkspaceContext.Provider>
}
