import assert from 'node:assert/strict'
import { test } from 'node:test'
import { Context } from '@deepseek-ai/cordis'
import { mountAgentLoopTestDependencies, mountAgentLoopTestHarness } from '@deepseek-ai/dsh-agent-loop-testkit'
import { createUserMessage, LlmAdapter, type StreamChunk, type ToolCallId } from '@deepseek-ai/dsh-llm'
import type { SessionId } from '@deepseek-ai/dsh-session'
import { defineTool } from '@deepseek-ai/dsh-tools'
import * as plugin from '../src/index.ts'

// Only the model is scripted. The agent loop, session, tool dispatch and
// plugin lifecycle are actual DSH services; no network or model key needed.
class ScriptedAdapter extends LlmAdapter {
  requests = 0

  async resolveModel(provider: string, model: string) {
    return { provider, id: model, name: model }
  }

  async *stream(): AsyncIterable<StreamChunk> {
    this.requests += 1
    if (this.requests === 1) {
      yield { type: 'block-start', index: 0, blockType: 'tool-call' }
      yield { type: 'block-end', index: 0, block: { type: 'tool-call', id: 'probe-1' as ToolCallId, name: 'probe', arguments: '{}' } }
      yield { type: 'finish', reason: { kind: 'tool-calls' } }
    } else {
      yield { type: 'block-start', index: 0, blockType: 'text' }
      yield { type: 'text-delta', index: 0, text: 'done' }
      yield { type: 'block-end', index: 0, block: { type: 'text', text: 'done' } }
      yield { type: 'finish', reason: { kind: 'stop' } }
    }
  }
}

test('native agent and tool events are observed until the plugin is disposed', { timeout: 15000 }, async (t) => {
  const ctx = new Context()
  t.after(() => ctx.fiber.dispose())
  const lines: string[] = []
  t.mock.method(console, 'log', (line: unknown) => {
    if (typeof line === 'string' && line.startsWith('[harness-dsh] ')) lines.push(line)
  })
  await mountAgentLoopTestDependencies(ctx)
  const fiber = ctx.plugin(plugin)
  await fiber
  const adapter = new ScriptedAdapter()
  ctx.llm.registerAdapter(['mock'], adapter)
  let toolCalls = 0
  ctx.tools.register(defineTool({
    name: 'probe', description: 'Test-only tool', parameters: {},
    output: { schema: { type: 'string' }, render: (_args, value) => [{ type: 'text', text: value }] },
    async execute() { toolCalls += 1; return 'ok' },
  }))
  const harness = await mountAgentLoopTestHarness(ctx)
  const agent = await harness.create('harness-dsh-test' as SessionId, { provider: 'mock', model: 'mock' })
  const prompt = () => createUserMessage({ content: [{ type: 'text', text: 'test' }], source: { kind: 'user' } })
  agent.followup(prompt())
  await agent.whenIdle()
  assert.equal(toolCalls, 1)
  assert.equal(adapter.requests, 2)
  assert.deepEqual(lines, [
    '[harness-dsh] loaded',
    '[harness-dsh] harness-dsh-test turn/start',
    '[harness-dsh] harness-dsh-test step/start',
    '[harness-dsh] harness-dsh-test tool/call probe',
    '[harness-dsh] harness-dsh-test tool/result',
    '[harness-dsh] harness-dsh-test step/end',
    '[harness-dsh] harness-dsh-test step/start',
    '[harness-dsh] harness-dsh-test step/end',
    '[harness-dsh] harness-dsh-test turn/end',
  ])
  await fiber.dispose()
  assert.equal(lines.at(-1), '[harness-dsh] unloaded')
  const before = lines.length
  agent.followup(prompt())
  await agent.whenIdle()
  assert.equal(adapter.requests, 3)
  assert.equal(lines.length, before)
})
