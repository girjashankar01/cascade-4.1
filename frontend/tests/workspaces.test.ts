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

test('reset stays locked during execution and resets selection only on completion', () => {
  let state = initialWorkspaces()
  const id = state.activeId
  state = workspaceReducer(state, { type: 'select', id, scenario: 'A' })
  state = workspaceReducer(state, { type: 'begin-reset', id })
  assert.equal(state.items[0].operation, 'reset')
  assert.equal(state.items[0].phase, 'running')
  assert.equal(workspaceReducer(state, { type: 'start', id }), state)
  assert.equal(workspaceReducer(state, { type: 'close', id }), state)
  state = workspaceReducer(state, { type: 'reset-done', id })
  assert.equal(state.items[0].scenario, null)
  assert.equal(state.items[0].result, null)
  assert.match(state.items[0].notice!, /restored/)
})

test('progress and completion stay with their original workspace after switching tabs', async () => {
  const { createFixtureService } = await import('../src/data/fixtures.ts')
  let state = initialWorkspaces()
  const id = state.activeId
  state = workspaceReducer(state, { type: 'select', id, scenario: 'B1' })
  state = workspaceReducer(state, { type: 'start', id })
  state = workspaceReducer(state, { type: 'add', id: 'other' })
  state = workspaceReducer(state, { type: 'progress', id, step: 3 })
  const result = await createFixtureService().run('B1')
  state = workspaceReducer(state, { type: 'finish', id, result })
  result.reason = 'Changed by consumer'
  assert.equal(state.activeId, 'other')
  assert.equal(state.items[0].phase, 'completed')
  assert.equal(state.items[0].result!.outcome, 'blocked')
  assert.notEqual(state.items[0].result!.reason, result.reason)
  assert.equal(state.items[1].result, null)
})

test('later live completion marks other live records as historical', async () => {
  const { createFixtureService } = await import('../src/data/fixtures.ts')
  const result = { ...await createFixtureService().run('A'), source: 'live' as const }
  let state = initialWorkspaces('live')
  const first = state.activeId
  state = workspaceReducer(state, { type: 'finish', id: first, result })
  state = workspaceReducer(state, { type: 'add', id: 'next-live' })
  state = workspaceReducer(state, { type: 'mode', id: 'next-live', mode: 'live' })
  state = workspaceReducer(state, { type: 'finish', id: 'next-live', result: { ...result, id: 'later' } })
  assert.equal(state.items[0].resultHistorical, true)
  assert.equal(state.items[1].resultHistorical, false)
})
