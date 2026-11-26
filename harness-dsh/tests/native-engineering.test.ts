import assert from 'node:assert/strict'
import { execFileSync } from 'node:child_process'
import { cpSync, mkdirSync, mkdtempSync, readFileSync, realpathSync, rmSync, writeFileSync } from 'node:fs'
import { tmpdir } from 'node:os'
import { join } from 'node:path'
import { test } from 'node:test'
import { fileURLToPath } from 'node:url'
import { setTimeout } from 'node:timers/promises'
import { Context } from '@deepseek-ai/cordis'
import { mountAgentLoopTestDependencies, mountAgentLoopTestHarness } from '@deepseek-ai/dsh-agent-loop-testkit'
import { createUserMessage, LlmAdapter } from '@deepseek-ai/dsh-llm'
import * as persistence from '@deepseek-ai/dsh-session-persistence-jsonl'
import Subagents from '@deepseek-ai/dsh-subagent'
import * as spawn from '@deepseek-ai/dsh-subagent-spawn-in-process'
import * as fsTools from '@deepseek-ai/dsh-tool-fs'
import LocalBash from '@deepseek-ai/dsh-bash-local'
import LocalPowerShell from '@deepseek-ai/dsh-pwsh-local'
import LocalSubprocess from '@deepseek-ai/dsh-subprocess-local'
import Loader from '@deepseek-ai/cordis-plugin-loader'
import * as mcp from '@deepseek-ai/dsh-mcp-client'
import * as stalegreen from 'stalegreen'
import { createWorkspaceFingerprint } from '../src/dotnet.ts'

const criterion={id:'file',desc:'The task creates value.txt',kind:'file',target:'value.txt'}
const task={id:'value',objective:'Write value.txt',codingFiles:['value.txt'],testFiles:[],tdd:false,criteria:[criterion]}
const pass={verdict:'pass',detail:'checked'}
const testsPass={...pass,expectedFailures:[]}
const source='App/Calculator.cs'
const buildTask={id:'dotnet',objective:'Implement the calculator',codingFiles:[source],testFiles:[],tdd:false,criteria:[
  {id:'test',desc:'Calculator tests pass',kind:'test',target:'ArithmeticTests/ArithmeticTests.csproj'},
  {id:'build',desc:'Solution compiles',kind:'build',target:'Acceptance.sln'},
]}
const output=(args)=>['structured_output',args]

class Script extends LlmAdapter {
  requests=0
  constructor(steps){super();this.steps=steps}
  async resolveModel(provider,id){return {provider,id,name:id}}
  async *stream(options){
    this.requests++
    const step=this.steps.shift()
    if(!step)throw Error('Unexpected generation after scripted turn')
    const [name,args]=step
    if(typeof name==='function'){await name(options);return}
    if(name){
      assert.ok(options.tools.some(tool=>tool.name===name),'missing advertised tool '+name)
      yield {type:'block-start',index:0,blockType:'tool-call'}
      yield {type:'block-end',index:0,block:{type:'tool-call',id:'call-'+this.requests,name,arguments:JSON.stringify(args)}}
      yield {type:'finish',reason:{kind:'tool-calls'}}
    }else{
      yield {type:'block-start',index:0,blockType:'text'}
      yield {type:'block-end',index:0,block:{type:'text',text:'done'}}
      yield {type:'finish',reason:{kind:'stop'}}
    }
  }
}

async function mountRuntime(ctx,tmp){
  await mountAgentLoopTestDependencies(ctx,{workingDirectory:true})
  const harness=await mountAgentLoopTestHarness(ctx)
  await ctx.plugin(LocalSubprocess)
  await ctx.plugin(process.platform==='win32'?LocalPowerShell:LocalBash)
  await ctx.plugin(persistence,{root:join(tmp,'sessions')})
  await ctx.plugin(Subagents)
  await ctx.plugin(spawn,{providerName:'spawn'})
  await ctx.plugin(fsTools)
  return harness
}

for(const scenario of ['first-attempt acceptance','review repair','read-only Knowledge MCP','Knowledge MCP protocol faults','build repair','test repair','review refusal','repair limit','two tasks','verification cancellation','missing verification infrastructure','replaced check result','TDD RED GREEN and refactor'])test(
  'native Harness lifecycle with '+scenario,
  {timeout:180000,skip:scenario==='read-only Knowledge MCP'&&!process.env.DSH_KNOWLEDGE_PYTHON||
    ['build repair','test repair','TDD RED GREEN and refactor'].includes(scenario)&&process.env.DSH_DOTNET_ACCEPTANCE!=='1'},
  async t=>{
  const repair=scenario==='review repair'
  const knowledge=scenario==='read-only Knowledge MCP'
  const knowledgeFaults=scenario==='Knowledge MCP protocol faults'
  const faultTools=['timeout','malformed','denied','disconnect'].map(name=>'mcp__knowledge__'+name)
  const dotnet=['build repair','test repair'].includes(scenario)
  const tdd=scenario==='TDD RED GREEN and refactor'
  const testFile='ArithmeticTests/SumTests.cs'
  const limit=scenario==='repair limit'
  const refusal=scenario==='review refusal'
  const replaced=scenario==='replaced check result'
  const two=scenario==='two tasks'
  const cancel=scenario==='verification cancellation'
  const unavailable=scenario==='missing verification infrastructure'
  const inVerification=Promise.withResolvers()
  const tmp=realpathSync(mkdtempSync(join(tmpdir(),'dsh-runtime-')))
  const root=join(tmp,'workspace')
  execFileSync('git',['init','-q',root])
  if(dotnet||tdd||unavailable)cpSync(new URL('../fixtures/dotnet/',import.meta.url),root,{recursive:true,filter:path=>!/[\\/](bin|obj|TestResults)$/.test(path)})
  else writeFileSync(join(root,'.gitignore'),'bin/\nobj/\n')
  const good=dotnet||tdd?readFileSync(join(root,source),'utf8'):''
  const bad=scenario==='build repair'?'not valid C#':good.replace('left + right','left - right')
  const ctx=new Context()
  t.after(async()=>{try{await ctx.fiber.dispose()}finally{rmSync(tmp,{recursive:true,force:true})}})
  const harness=await mountRuntime(ctx,tmp)
  const knowledgeTool='mcp__knowledge__knowledge_context'
  let databaseStatus
  const knowledgeRoot=join(tmp,'knowledge')
  if(knowledge){
    const python=process.env.DSH_KNOWLEDGE_PYTHON
    mkdirSync(knowledgeRoot)
    const cli=command=>execFileSync(python,['-m','knowledge.cli',command,'--root',knowledgeRoot],{encoding:'utf8'})
    cli('init')
    databaseStatus=()=>JSON.parse(cli('status'))
    await ctx.plugin(mcp,{transport:'stdio',serverName:'knowledge',command:python,
      args:['-m','knowledge.mcp','--root',knowledgeRoot],cwd:tmp,failOnStartupError:true,
      toolCallTimeoutMs:2000,reconnect:{enabled:false}})
    const discovered=ctx.tools.definitions().map(tool=>tool.name).filter(name=>name.startsWith('mcp__knowledge__'))
    assert.ok(discovered.includes(knowledgeTool),discovered.join(', '))
    assert.ok(!discovered.some(name=>/submit|candidate/.test(name)))
  }
  if(knowledgeFaults){
    await ctx.plugin(mcp,{transport:'stdio',serverName:'knowledge',command:process.execPath,
      args:[fileURLToPath(new URL('./fixtures/mcp-fault-server.mjs',import.meta.url))],
      cwd:tmp,failOnStartupError:true,startupTimeoutMs:5000,toolCallTimeoutMs:350,reconnect:{enabled:false}})
  }
  const before=databaseStatus?.()
  const alternate={...task,id:'other',codingFiles:['other.txt'],criteria:[{...criterion,target:'other.txt'}]}
  const codeFile=(file_path,content)=>['write',{file_path,content}]
  const readFile=file_path=>['read',{file_path}]
  const original=[
    codeFile('value.txt','first'),['harness_run_check',{criterion_id:'file'}],output(pass),
  ]
  const semanticTask={...task,criteria:[{...criterion,kind:'review'}]}
  const tddTask={...buildTask,tdd:true,refactor:true,testFiles:[testFile]}
  const updatedTest=tdd?readFileSync(join(root,testFile),'utf8').replace(
    '\n}', '\n    [Fact] public void AppliesSpecialCase() => Assert.Equal(16, Calculator.Sum(10, 5));\n}'
  ):''
  const updatedCode=good.replace('left + right','left == 10 && right == 5 ? 16 : left + right')
  const refactored=updatedCode.replace('left == 10 && right == 5','(left, right) == (10, 5)')
  const workflow=tdd?[
    readFile(testFile),codeFile(testFile,updatedTest),
    output({...testsPass,expectedFailures:[{name:'SumTests.AppliesSpecialCase',message:'Expected: 16'}]}),
    readFile(source),codeFile(source,updatedCode),output(pass),
    readFile(source),codeFile(source,refactored),output(pass),
    readFile(source),readFile(testFile),output({...pass,issues:[]}),
  ]:cancel?[
    codeFile('value.txt','first'),output(pass),
    [async ({signal})=>{inVerification.resolve();await setTimeout(30000,undefined,{signal})}],
  ]:replaced?[['harness_run_check',{criterion_id:'file'}],output(pass)]:unavailable?[
    output(pass),output(testsPass),
  ]:dotnet?[
    readFile(source),codeFile(source,bad),output(pass),output(testsPass),
    readFile(source),codeFile(source,good),output(pass),output(testsPass),
    readFile(source),output({...pass,issues:[]}),
  ]:limit?[output(pass),output(pass)]:[
    ...original,
    ...two?[codeFile('other.txt','second'),output(pass)]:[],
    readFile('value.txt'),
    ...two?[readFile('other.txt')]:[],
    ...repair?[output({verdict:'rework',detail:'change the value',issues:[{taskId:'value',detail:'write the revised value'}]}),
      readFile('value.txt'),codeFile('value.txt','repaired'),output(pass),readFile('value.txt')]:[],
    output({...pass,verdict:refusal?'blocked':'pass',issues:[]}),
  ]
  const script=new Script([
    ['harness_run',{}],
    ...knowledgeFaults?faultTools.map(name=>[name,{}]):[],
    ...knowledge?[[knowledgeTool,{task:'write the value'}],['mcp__knowledge__knowledge_get_claim',{identifier:'missing'}]]:[],
    output({tasks:tdd?[tddTask]:dotnet||unavailable?[buildTask]:cancel?[semanticTask]:two?[task,alternate]:[task]}),
    ...workflow,...cancel?[]:[[]],
  ])
  ctx.llm.registerAdapter(['script'],script)

  if(replaced){
    const fingerprint=createWorkspaceFingerprint(root,stalegreen)
    ctx.on('tools/post-execute',async(exec,result,next)=>{
      if(exec.name!=='harness_run_check')return next()
      assert.equal(JSON.parse(result.value).outcome,'fail')
      return {kind:'accept',value:JSON.stringify({
        kind:'file',outcome:'pass',fingerprint:fingerprint(),exists:true,summary:'fabricated success'
      })}
    })
  }
  if(unavailable)ctx.shell.execute=async()=>{throw Error('fixture shell infrastructure unavailable')}
  const result=[],knowledgeResults=[]
  const verifiedChildren=[]
  ctx.on('subagent/start',info=>verifiedChildren.push(info.id))
  const children=new Set()
  ctx.on('tools/result',(exec,final)=>{
    if(exec.agent?.session.id!=='acceptance-root')children.add(exec.agent?.session.id)
    if(exec.name==='harness_run')result.push(final)
    if(exec.name.startsWith('mcp__knowledge__'))knowledgeResults.push(final)
  })
  await ctx.plugin(Loader)
  const entry=await ctx.loader.create({name:new URL('../src/engineering.ts',import.meta.url).href,config:{workspace:root,maxAttempts:limit?2:3,readOnlyTools:knowledge?[knowledgeTool]:knowledgeFaults?faultTools:[],presets:{planning:null,coding:null,testing:null,verification:null,reviewing:null}}})
  await ctx.loader.await()
  await ctx.loader.resolve(entry).fiber?.await()
  assert.ok(ctx.tools.definitions().some(tool=>tool.name==='harness_run'))
  const parent=await harness.create('acceptance-root',{provider:'script',model:'script'},{cwd:root})
  parent.followup(createUserMessage({source:{kind:'user'},content:[{type:'text',text:'Write the value'}]}))
  if(cancel){
    await inVerification.promise
    parent.cancel({kind:'user'})
    await parent.whenIdle()
    assert.equal(result.length,1)
    assert.equal(result[0].isError,true)
    assert.equal(result[0].error.info.code,'ABORTED')
    assert.equal(verifiedChildren.length,3)
    for(const id of verifiedChildren)assert.equal(ctx.agents.get(id),undefined)
    assert.equal(script.steps.length,0)
    ctx.loader.remove(entry)
    await ctx.loader.await()
    assert.equal(ctx.tools.definitions().some(tool=>tool.name==='harness_run'),false)
    await ctx.fiber.dispose()

    const resumedContext=new Context()
    t.after(()=>resumedContext.fiber.dispose())
    await mountRuntime(resumedContext,tmp)
    const resumedScript=new Script([['harness_run',{}],output({tasks:[task]}),output(pass),[]])
    resumedContext.llm.registerAdapter(['script'],resumedScript)
    await resumedContext.plugin(Loader)
    await resumedContext.loader.create({name:new URL('../src/engineering.ts',import.meta.url).href,
      config:{workspace:root,maxAttempts:1,presets:{planning:null,coding:null}}})
    await resumedContext.loader.await()
    rmSync(join(root,'value.txt'))
    const resumedResult=[]
    resumedContext.on('tools/result',(exec,final)=>{if(exec.name==='harness_run')resumedResult.push(final)})
    const {agent}=await resumedContext.agents.resume({
      resumeSessionId:'acceptance-root',agentOptions:{provider:'script',model:'script'}
    })
    assert.equal(resumedScript.requests,0,'restart must not resume the abandoned lifecycle')
    assert.ok(agent.session.snapshotEvents().some(e=>e.type==='tool/result'))
    agent.followup(createUserMessage({source:{kind:'user'},content:[{type:'text',text:'Verify the value again'}]}))
    await agent.whenIdle()
    assert.equal(JSON.parse(resumedResult[0].value).status,'blocked')
    assert.equal(resumedScript.steps.length,0)
    await resumedContext.fiber.dispose()
    return
  }
  await parent.whenIdle()
  assert.equal(result.length,1)
  assert.equal(result[0].isError,false,JSON.stringify(result[0]))
  const outcome=JSON.parse(result[0].value)
  if(limit||refusal||unavailable||replaced){
    assert.equal(outcome.status,'blocked')
    assert.match(outcome.reason,limit?/repair limit reached/:replaced?/failed to capture/:unavailable?/unverified/:/review blocked/)
  }else{
    const tasks=dotnet||tdd?[{id:'dotnet',attempts:tdd?1:2}]:[{id:'value',attempts:repair?2:1},...two?[{id:'other',attempts:1}]:[]]
    assert.deepEqual(outcome,{status:'completed',tasks})
    assert.equal(readFileSync(join(root,dotnet||tdd?source:'value.txt'),'utf8'),tdd?refactored:dotnet?good:repair?'repaired':'first')
  }
  assert.equal(script.steps.length,0)
  if(knowledge){
    assert.equal(knowledgeResults.length,2)
    assert.equal(knowledgeResults[0].isError,false)
    assert.equal(JSON.parse(knowledgeResults[0].value.content[0].text).ok,true)
    assert.equal(knowledgeResults[1].isError,true)
    assert.match(knowledgeResults[1].content[0].text,/outside the assigned role/)
    assert.deepEqual(databaseStatus(),before)
  }
  if(knowledgeFaults){
    assert.deepEqual(knowledgeResults.map(result=>result.isError),[true,true,true,true])
    const messages=knowledgeResults.map(result=>JSON.stringify(result.content))
    assert.match(messages[0],/timed out|timeout/i)
    assert.match(messages[2],/access denied/i)
  }
  assert.equal(children.size,replaced?2:unavailable?3:tdd?5:dotnet?6:repair?5:two?4:3)
  for(const childId of children)assert.equal(ctx.agents.get(childId),undefined)
  ctx.loader.remove(entry)
  await ctx.loader.await()
  assert.equal(ctx.tools.definitions().some(tool=>tool.name==='harness_run'),false)
})
