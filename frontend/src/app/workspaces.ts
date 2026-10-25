import type { Mode, RunResult, ScenarioId } from '../data/types.ts'
export interface Workspace {
  id: string
  name: string
  mode: Mode
  scenario: ScenarioId | null
  phase: 'idle' | 'running' | 'completed' | 'error'
  result: RunResult | null
  error: string | null
}
export interface WorkspaceState { items: Workspace[]; activeId: string; nextNumber: number }
export type WorkspaceAction =
  | { type: 'add'; id: string }
  | { type: 'activate' | 'close'; id: string; replacementId?: string }
  | { type: 'rename'; id: string; name: string }
  | { type: 'mode'; id: string; mode: Mode }
  | { type: 'select'; id: string; scenario: ScenarioId }
  | { type: 'start' | 'reset'; id: string }
  | { type: 'finish'; id: string; result: RunResult }
  | { type: 'fail'; id: string; message: string }

export function newWorkspace(id: string, name: string, mode: Mode = 'demo'): Workspace {
  return { id, name, mode, scenario: null, phase: 'idle', result: null, error: null }
}
export function initialWorkspaces(mode: Mode = 'demo'): WorkspaceState {
  const initial = newWorkspace(crypto.randomUUID(), 'Payment review', mode)
  return { items: [initial], activeId: initial.id, nextNumber: 2 }
}
export function workspaceReducer(state: WorkspaceState, action: WorkspaceAction): WorkspaceState {
  const current = state.items.find(item => item.id === action.id)
  if (action.type === 'add') {
    if (current) return state
    const item = newWorkspace(action.id, `Workspace ${state.nextNumber}`)
    return { items: [...state.items, item], activeId: item.id, nextNumber: state.nextNumber + 1 }
  }
  if (!current) return state
  if (action.type === 'activate') return { ...state, activeId: current.id }
  if (action.type === 'close') {
    if (current.phase === 'running') return state
    const index = state.items.indexOf(current)
    const remaining = state.items.filter(item => item.id !== current.id)
    if (!remaining.length) {
      const item = newWorkspace(action.replacementId ?? crypto.randomUUID(), 'Payment review')
      return { ...state, items: [item], activeId: item.id }
    }
    return { ...state, items: remaining, activeId: state.activeId === current.id ? remaining[Math.min(index, remaining.length - 1)].id : state.activeId }
  }
  let updated = current
  if (action.type === 'rename') {
    const name = action.name.trim().slice(0, 40)
    if (!name) return state
    updated = { ...current, name }
  }
  if (current.phase === 'running' && ['mode', 'select', 'start', 'reset'].includes(action.type)) return state
  if (action.type === 'mode') updated = { ...current, mode: action.mode, phase: 'idle', result: null, error: null }
  if (action.type === 'select') updated = { ...current, scenario: action.scenario, phase: 'idle', result: null, error: null }
  if (action.type === 'start') { if (!current.scenario) return state; updated = { ...current, phase: 'running', result: null, error: null } }
  if (action.type === 'reset') updated = { ...current, scenario: null, phase: 'idle', result: null, error: null }
  if (action.type === 'finish') updated = { ...current, phase: 'completed', result: structuredClone(action.result), error: null }
  if (action.type === 'fail') updated = { ...current, phase: 'error', error: action.message }
  return { ...state, items: state.items.map(item => item.id === current.id ? updated : item) }
}
