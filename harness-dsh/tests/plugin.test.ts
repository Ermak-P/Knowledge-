import assert from 'node:assert/strict'
import { test } from 'node:test'
import { apply, inject, name } from '../src/index.ts'

test('registers a passive observer, filters event data and releases it on unload', (t) => {
  const lines: string[] = []
  t.mock.method(console, 'log', (line: string) => { lines.push(line) })
  const disposers: (() => void)[] = []
  type Listener = (session: { id: string }, event: { type: string; data?: unknown }) => void
  const listeners = new Set<Listener>()
  const ctx = {
    on(event: string, listener: Listener) {
      assert.equal(event, 'session/event')
      listeners.add(listener)
      disposers.push(() => { listeners.delete(listener) })
    },
    effect(register: () => () => void) { disposers.push(register()) },
  }
  const emit = (type: string, data?: unknown) => {
    for (const listener of listeners) listener({ id: 's1' }, { type, data })
  }
  assert.equal(name, 'harness-dsh')
  assert.deepEqual(inject, ['sessions'])
  apply(ctx as unknown as Parameters<typeof apply>[0])
  emit('turn/start')
  emit('step/start')
  emit('user/message', { text: 'PRIVATE' })
  emit('tool/call', { name: 'read', arguments: 'PRIVATE' })
  emit('tool/result', { content: 'PRIVATE' })
  emit('step/end')
  emit('turn/end')
  for (const dispose of disposers.reverse()) dispose()
  emit('turn/start')
  assert.equal(listeners.size, 0)
  assert.deepEqual(lines, [
    '[harness-dsh] loaded',
    '[harness-dsh] s1 turn/start',
    '[harness-dsh] s1 step/start',
    '[harness-dsh] s1 tool/call read',
    '[harness-dsh] s1 tool/result',
    '[harness-dsh] s1 step/end',
    '[harness-dsh] s1 turn/end',
    '[harness-dsh] unloaded',
  ])
})
