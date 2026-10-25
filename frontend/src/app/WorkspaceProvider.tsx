import { useReducer } from 'react'
import type { ReactNode } from 'react'
import { initialWorkspaces, workspaceReducer } from './workspaces'
import { WorkspaceContext } from './workspace-context'

export function WorkspaceProvider({ children }: { children: ReactNode }) {
  const [state, dispatch] = useReducer(workspaceReducer, undefined, () => initialWorkspaces(new URLSearchParams(location.search).get('mode') === 'live' ? 'live' : 'demo'))
  const active = state.items.find(item => item.id === state.activeId)!
  return <WorkspaceContext.Provider value={{ state, active, dispatch }}>{children}</WorkspaceContext.Provider>
}
