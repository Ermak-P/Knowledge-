import { createInterface } from 'node:readline'

const tools = ['timeout', 'malformed', 'denied', 'disconnect']
const input = createInterface({ input: process.stdin })
for await (const line of input) {
  const message = JSON.parse(line)
  if (message.id === undefined) continue
  const send = result => process.stdout.write(JSON.stringify({ jsonrpc: '2.0', id: message.id, result }) + '\n')
  if (message.method === 'initialize') {
    send({
      protocolVersion: message.params.protocolVersion,
      capabilities: { tools: {} },
      serverInfo: { name: 'knowledge-fault-fixture', version: '1' },
    })
  } else if (message.method === 'tools/list') {
    send({ tools: tools.map(name => ({
      name, description: 'Fixture ' + name, inputSchema: { type: 'object', properties: {} },
    })) })
  } else if (message.method === 'tools/call') {
    switch (message.params.name) {
      case 'timeout': break
      case 'malformed': send({ content: 'invalid result block shape' }); break
      case 'denied': send({ content: [{ type: 'text', text: 'fixture access denied' }], isError: true }); break
      case 'disconnect': process.exit(0)
    }
  } else {
    process.stdout.write(JSON.stringify({
      jsonrpc: '2.0', id: message.id, error: { code: -32601, message: 'Method not found' },
    }) + '\n')
  }
}
