import assert from 'node:assert/strict'
import { once } from 'node:events'
import { createServer } from 'node:http'
import { test } from 'node:test'
import { Context } from '@deepseek-ai/cordis'
import { mountAgentLoopTestDependencies, mountAgentLoopTestHarness } from '@deepseek-ai/dsh-agent-loop-testkit'
import { createUserMessage } from '@deepseek-ai/dsh-llm'
import * as openai from '@deepseek-ai/dsh-llm-pi-ai'
import * as retryPolicy from '@deepseek-ai/dsh-llm-retry'
import { defineTool } from '@deepseek-ai/dsh-tools'

test('DSH OpenAI-compatible HTTP transport handles tool calls with reasoning off', {timeout:20000}, async t=>{
  const requests=[]
  const interrupted=Promise.withResolvers()
  const closed=Promise.withResolvers()
  const attempts=new Map()
  const server=createServer(async(req,res)=>{
    const body=[]
    for await(const chunk of req)body.push(chunk)
    const data=JSON.parse(Buffer.concat(body).toString())
    requests.push({url:req.url,body:data})
    const scenario=data.messages.find(message=>message.role==='user')?.content
    const name=typeof scenario==='string'?scenario:scenario?.[0]?.text
    const attempt=(attempts.get(name)??0)+1
    attempts.set(name,attempt)
    if(name==='timeout')return
    if(name==='interrupt'){
      res.once('close',closed.resolve)
      interrupted.resolve()
      return
    }
    if(name==='context'||(name==='retry'&&attempt===1)){
      res.writeHead(name==='context'?400:503,{'content-type':'application/json'})
      res.end(JSON.stringify({error:{message:name==='context'
        ?'This model maximum context length is 8192 tokens. Reduce the length of the messages.'
        :'Fixture temporarily unavailable'}}))
      return
    }
    const index=requests.length
    res.writeHead(200,{'content-type':'text/event-stream'})
    const send=(delta,reason)=>res.write('data: '+JSON.stringify({
      id:'chatcmpl-fixture',created:1,object:'chat.completion.chunk',model:'fixture',
      choices:[{index:0,delta,finish_reason:reason}]
    })+'\n\n')
    send({role:'assistant'},null)
    if(index<3){
      send({tool_calls:[{index:0,id:'call_'+index,type:'function',function:{
        name:'probe',arguments:index===1?'{"value":"wire"}':'{"value":4}'
      }}]},null)
      send({},'tool_calls')
    }else{
      send({content:'done'},null)
      send({},'stop')
    }
    res.end('data: [DONE]\n\n')
  }).listen(0,'127.0.0.1')
  t.after(()=>{server.closeAllConnections();return new Promise(resolve=>server.close(resolve))})
  await once(server,'listening')

  const ctx=new Context()
  const originalKey=process.env.DSH_FIXTURE_API_KEY
  process.env.DSH_FIXTURE_API_KEY='fixture-key'
  t.after(()=>{if(originalKey===undefined)delete process.env.DSH_FIXTURE_API_KEY;else process.env.DSH_FIXTURE_API_KEY=originalKey})
  t.after(()=>ctx.fiber.dispose())
  await mountAgentLoopTestDependencies(ctx)
  await ctx.plugin(retryPolicy)
  await ctx.plugin(openai,{providers:{fixture:{
    api:'openai-completions',baseURL:'http://127.0.0.1:'+server.address().port+'/v1',
    apiKeyEnv:'DSH_FIXTURE_API_KEY',timeoutMs:2000,streamIdleTimeoutMs:700,
    retryPolicy:{mode:'normal',maxRetries:1,backoff:{initialDelayMs:20,maxDelayMs:20,jitterRatio:0}},
    models:[{id:'fixture',contextWindow:8192,maxTokens:512,reasoningEfforts:{off:'off',low:'low'}}],
  }}})
  let calls=0
  ctx.tools.register(defineTool({
    name:'probe',description:'Echo a string',parameters:{value:{type:'string',required:true}},
    output:{schema:{type:'string'},render:(_args,value)=>[{type:'text',text:value}]},
    async execute(args){calls++;assert.equal(args.value,'wire');return args.value},
  }))
  const outcomes=[]
  ctx.on('tools/result',(exec,result)=>{if(exec.name==='probe')outcomes.push(result.isError)})
  const harness=await mountAgentLoopTestHarness(ctx)
  const agent=await harness.create('provider-acceptance',{provider:'fixture',model:'fixture',reasoningEffort:'off'})
  agent.followup(createUserMessage({source:{kind:'user'},content:[{type:'text',text:'Exercise the tool'}]}))
  await agent.whenIdle()
  assert.equal(calls,1,JSON.stringify(agent.session.snapshotEvents().filter(e=>e.type==='turn/end'||e.type==='step/end')))
  assert.deepEqual(outcomes,[false,true])
  assert.equal(requests.length,3)
  assert.ok(requests.every(({url,body})=>url==='/v1/chat/completions'&&[undefined,'off'].includes(body.reasoning_effort)))
  assert.ok(requests[2].body.messages.some(message=>message.role==='tool'&&message.tool_call_id==='call_2'))

  async function start(prompt){
    const agent=await harness.create('provider-'+prompt,{provider:'fixture',model:'fixture',reasoningEffort:'off'})
    agent.followup(createUserMessage({source:{kind:'user'},content:[{type:'text',text:prompt}]}))
    return agent
  }
  const reason=agent=>agent.session.snapshotEvents().findLast(e=>e.type==='turn/end').data.reason
  const retry=await start('retry')
  await retry.whenIdle()
  assert.equal(attempts.get('retry'),2,JSON.stringify(reason(retry)))
  assert.equal(reason(retry).kind,'completed')

  const context=await start('context')
  await context.whenIdle()
  assert.equal(reason(context).kind,'error')
  assert.match(JSON.stringify(reason(context)),/context/i)

  const timeout=await start('timeout')
  await timeout.whenIdle()
  assert.equal(reason(timeout).kind,'error')
  assert.match(JSON.stringify(reason(timeout)),/timeout|timed out/i)
  assert.ok(attempts.get('timeout')<=2)

  const stop=await start('interrupt')
  await interrupted.promise
  stop.cancel({kind:'user'})
  await stop.whenIdle()
  await closed.promise
  assert.match(JSON.stringify(reason(stop)),/cancel|abort/i)
})
