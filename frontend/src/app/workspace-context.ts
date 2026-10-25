import { createContext, useContext } from 'react'
import type { Dispatch } from 'react'
import type { Workspace, WorkspaceAction, WorkspaceState } from './workspaces'
export const WorkspaceContext = createContext<{ state: WorkspaceState; active: Workspace; dispatch: Dispatch<WorkspaceAction>; run: () => Promise<void>; reset: () => Promise<void> } | null>(null)
export function useWorkspaces() {
  const value = useContext(WorkspaceContext)
  if (!value) throw new Error('WorkspaceProvider is required')
  return value
}
