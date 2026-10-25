import test from 'node:test'
import assert from 'node:assert/strict'
import { initialWorkspaces, workspaceReducer } from '../src/app/workspaces.ts'

test('tabs keep independent scenarios, mode and names', () => {
  let state = initialWorkspaces()
  const first = state.activeId
  state = workspaceReducer(state, { type: 'select', id: first, scenario: 'A' })
  state = workspaceReducer(state, { type: 'rename', id: first, name: '  Valid payout  ' })
  state = workspaceReducer(state, { type: 'add', id: 'second' })
  state = workspaceReducer(state, { type: 'select', id: 'second', scenario: 'B1' })
  state = workspaceReducer(state, { type: 'mode', id: 'second', mode: 'live' })
  state = workspaceReducer(state, { type: 'activate', id: first })
  assert.equal(state.items[0].scenario, 'A'); assert.equal(state.items[0].name, 'Valid payout'); assert.equal(state.items[0].mode, 'demo')
  assert.equal(state.items[1].scenario, 'B1'); assert.equal(state.items[1].mode, 'live')
})
test('closing the last tab returns a fresh empty demo workspace', () => {
  const state = initialWorkspaces('live')
  const result = workspaceReducer(state, { type: 'close', id: state.activeId, replacementId: 'replacement' })
  assert.equal(result.items.length, 1); assert.equal(result.activeId, 'replacement')
  assert.equal(result.items[0].mode, 'demo'); assert.equal(result.items[0].scenario, null)
})
test('a running session cannot be reset, closed, switched or reselected', () => {
  let state = initialWorkspaces()
  const id = state.activeId
  state = workspaceReducer(state, { type: 'select', id, scenario: 'A' })
  state = workspaceReducer(state, { type: 'start', id })
  for (const action of [{ type: 'close', id }, { type: 'reset', id }, { type: 'mode', id, mode: 'live' }, { type: 'select', id, scenario: 'B1' }] as const) assert.equal(workspaceReducer(state, action), state)
})
test('unknown ids and blank names do not corrupt the active workspace', () => {
  const state = initialWorkspaces()
  assert.equal(workspaceReducer(state, { type: 'activate', id: 'missing' }), state)
  assert.equal(workspaceReducer(state, { type: 'rename', id: state.activeId, name: '  ' }), state)
})
