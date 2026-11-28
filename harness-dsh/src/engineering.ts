// Production composition. No mock fallback is imported by this module.
import { randomUUID } from 'node:crypto'
import { execFileSync } from 'node:child_process'
import { realpathSync } from 'node:fs'
import { resolve, relative, isAbsolute, sep } from 'node:path'
import { EvidenceBook, runEngineering } from './lifecycle.ts'
import { projectRoot, safePath, discoverTests, validateTaskPaths, hashFiles, runCheck, isTestPath, createWorkspaceFingerprint, createTrxParser } from './dotnet.ts'
import { tddController } from './tdd.ts'
import { acquireWorkspaceLock } from './workspace-lock.ts'

export const name='harness-dsh-engineering'
export const inject=['agents','subagents','tools','shell']
const readTools=new Set(['read','read_image','glob','grep'])
// Read-only discovery must work before a task, even with an empty MCP allowlist.
const discoveryTools=new Set(['mcp__knowledge__knowledge_capabilities'])
const roles=['planning','coding','testing','verification','reviewing']
const commandTool='harness_run_check'

function sessionId(agent){return String(agent?.session?.id??'')}
function userBasis(parent){
  const events=parent.session.snapshotEvents()
  const start=[...events].reverse().find(e=>e.type==='turn/start')
  const event=[...events].reverse().find(e=>e.type==='user/message'&&e.data?.source?.kind==='user'&&(!start||e.seq>=start.seq))
  const request=event?.data?.content?.filter(b=>b.type==='text').map(b=>b.text).join('\n')
  if(!request?.trim())throw Error('harness_run requires an actual direct user message in the current turn')
  return {request,seq:event.seq,basis:[{kind:'user-message',eventRef:sessionId(parent)+':'+event.seq,seq:event.seq,text:request}]}
}
function tool(name,description,parameters,execute,render){
  return {name,description,parameters,output:{schema:{type:'string'},render:(_args,value)=>[{type:'text',text:render?render(JSON.parse(value)):value}]},execute}
}
const object=(properties={},required=[])=>({type:'object',properties,required,additionalProperties:false})
function resultForCapture(value){
  const {results,failures,...rest}=value
  return {...rest,...(failures?{failures:failures.slice(0,20)}:{})}
}
function diagnostic(value){
  const {kind,outcome,exitCode,classifier,passed,failed,skipped}=value
  const buildCodes=kind==='build'&&outcome==='fail'
    ?[...new Set(value.summary.match(/\b(?:CS|MSB|NETSDK|NU)\d{3,5}\b/g)??[])].slice(0,8)
    :undefined
  return {kind,outcome,exitCode,classifier,passed,failed,skipped,buildCodes}
}
const roleInstructions={
  planning:'Plan only; no mutations. Return the structured plan. Each task has exact repo-relative codingFiles and testFiles, an objective, tdd boolean, optional refactor boolean for a necessary TDD refactor, and criteria. Each criterion has id, desc, kind (build/test/file/review), target (repo-relative file or existing .NET project/solution). C# changes need build and test criteria. Use discovered test project paths. Use review criteria for semantic behavior that commands cannot prove. TDD requires exactly one test criterion and explicit test files. Keep scopes minimal.',
  coding:'Implement only this task and only its codingFiles. Use native read/edit/write. Never change tests or build/test controls. You can run harness_run_check with a criterion_id from the contract. Do not approve the task. Return a factual summary.',
  testing:'Independently analyze test design, coverage of acceptance criteria, missing cases and assertion quality. Write only listed testFiles. In RED mode create tests before production changes; identify exact TRX test names and expected failure-message substrings. Never weaken existing assertions to match incorrect behavior. If no test files were approved, analyze read-only. Report coverage as qualitative unless measured evidence is available.',
  verification:'Read the actual files for each review criterion and independently compare expected and actual. Native read results are required for every cited path. Return one criterion verdict per review criterion with exact repo-relative paths and a specific reason. Use harness_run_check only for checks explicitly missing or stale. Do not modify files or approve the task yourself.',
  reviewing:'Review final implementation against the original request and entire plan. Read every changed planned file; inspect the provided actual Git diff and test/gate context. Check omissions, business logic, architecture, regressions, test manipulation and unnecessary changes. Return pass with no issues or rework with concrete findings assigned to task ids. Do not modify files.'
}

export function mountEngineering(ctx,config,libs,xml){
  if(typeof config?.workspace!=='string'||!config.workspace)throw Error('harness-dsh requires an explicit workspace repository root')
  const root=projectRoot(config.workspace),s=libs.s
  const maxAttempts=config.maxAttempts??3
  if(!Number.isInteger(maxAttempts)||maxAttempts<1||maxAttempts>10)throw Error('invalid maxAttempts')
  const budgetMs=config.fingerprintBudgetMs??5000
  if(!Number.isInteger(budgetMs)||budgetMs<150||budgetMs>60000)throw Error('invalid fingerprintBudgetMs')
  const timeoutMs=config.checkTimeoutMs??300000
  if(!Number.isInteger(timeoutMs)||timeoutMs<1000||timeoutMs>3600000)throw Error('invalid checkTimeoutMs')
  const trustedReads=new Set(config.readOnlyTools??[])
  if([...trustedReads].some(n=>typeof n!=='string'||!n.startsWith('mcp__')))throw Error('readOnlyTools must contain exact, manually audited MCP tool names')
  const presets=config.presets??{}
  const runs=new Map(),assignments=new Map(),seenTurns=new Map()
  const computeFresh=createWorkspaceFingerprint(root,s,budgetMs,metrics=>{
    const run=runs.values().next().value
    if(!run)return
    run.fingerprintCount++;run.fingerprintMs+=metrics.totalMs
    if(config.fingerprintMetrics===true)console.log('[harness-dsh-fingerprint] '+JSON.stringify({runId:run.id,phase:run.phase,...metrics}))
  })
  const fresh=(ignore=[])=>{
    try{runs.values().next().value?.lock.assertOwned()}
    catch(error){return {available:false,tree:null,reason:String(error)}}
    return computeFresh(ignore)
  }
  const own=(agent)=>!!agent&&ctx.agents.get(agent.id)===agent
  const cwdOf=agent=>agent?.session&&(ctx.get?.('workingDirectory')?.get(agent.session)??agent.session.header?.cwd)
  const inProject=(agent)=>{
    const cwd=cwdOf(agent)
    if(typeof cwd!=='string')return false
    let path=resolve(cwd)
    try{path=realpathSync.native(path)}catch{}
    const rel=relative(root,path)
    return rel!=='..'&&!rel.startsWith('..'+sep)&&!isAbsolute(rel)
  }
  const isRoot=(agent)=>own(agent)&&inProject(agent)&&ctx.subagents.rootOf(agent)===agent
  const assignment=(agent)=>own(agent)?assignments.get(sessionId(agent)):undefined
  const scoped=(agent)=>inProject(agent)||!!assignment(agent)
  const log=(run,p)=>console.log('[harness-dsh] '+JSON.stringify({runId:run.id,taskId:p.taskId,phase:p.phase,detail:p.detail?.slice(0,1000)}))
  const deny=reason=>'harness-dsh: '+reason
  const allowedWrite=(a,agent,args)=>{
    if(!a.state||!['coding','testing'].includes(a.role)||!args||typeof args.file_path!=='string'||args.sandbox_permissions!==undefined)return false
    a.run.lock.assertOwned()
    const path=safePath(root,resolve(realpathSync.native(cwdOf(agent)),args.file_path))
    const paths=a.role==='coding'?a.state.task.codingFiles:a.state.task.testFiles
    return paths.includes(path)&&(a.role==='testing'?isTestPath(path,a.run.testProjects):!isTestPath(path,a.run.testProjects))
  }
  ctx.effect(()=>ctx.tools.guard(exec=>{
    const a=assignment(exec.agent)
    if(!scoped(exec.agent))return undefined
    if(!own(exec.agent))return deny('unknown agent')
    if((a&&exec.name==='structured_output')||readTools.has(exec.name)||discoveryTools.has(exec.name)||trustedReads.has(exec.name))return undefined
    if(exec.name==='harness_run'&&isRoot(exec.agent)&&!runs.size)return undefined
    if(a&&a.state&&exec.name===commandTool&&['coding','testing','verification'].includes(a.role))return undefined
    if(a&&['write','edit'].includes(exec.name)){
      try{if(allowedWrite(a,exec.agent,exec.arguments))return undefined}catch{}
    }
    return deny('operation is outside the assigned role or frozen task scope: '+exec.name)
  }))
  // DSH's final immutable outcome, not the model's summary or an intermediate result.
  ctx.on('tools/result',(exec,result)=>{
    const a=assignment(exec.agent)
    if(!a)return
    if(exec.name==='read'&&!result.isError){
      try{a.observed.add(safePath(root,resolve(realpathSync.native(cwdOf(exec.agent)),exec.arguments.file_path)))}catch{}
    }
    if(exec.name!==commandTool||!a.state)return
    const key=exec.token??exec.callId
    const receipt=a.receipts.get(key)
    a.receipts.delete(key)
    const value=!result.isError&&receipt?.rendered===result.value?receipt?.value:undefined
    void a.run.book.capture({taskId:a.state.task.id,role:a.role,agentId:String(exec.agent.id),sessionId:sessionId(exec.agent)},{callId:String(exec.callId),name:exec.name,arguments:exec.arguments,isError:result.isError,value}).catch(error=>{a.state.captureOverflow=true;console.warn('[harness-dsh] capture error',String(error))})
  })
  ctx.effect(()=>ctx.tools.register(tool(commandTool,'Execute one frozen acceptance check for your assigned task. No arbitrary commands.',object({criterion_id:{type:'string'}},['criterion_id']),async(args,exec)=>{
    const a=assignment(exec.agent)
    if(!a?.state||!['coding','testing','verification'].includes(a.role))throw Error('no trusted task assignment')
    const c=a.state.task.criteria.find(x=>x.id===args.criterion_id&&x.kind!=='review')
    if(!c)throw Error('unknown deterministic criterion')
    const signal=AbortSignal.any([exec.signal,a.run.signal])
    const pending=runCheck(ctx,exec.agent,root,c,()=>fresh(),s.compareFingerprints,xml,signal,timeoutMs)
    a.run.checks.add(pending)
    let value
    try{value=resultForCapture(await pending)}finally{a.run.checks.delete(pending)}
    const rendered=JSON.stringify(diagnostic(value))
    a.receipts.set(exec.token??exec.callId,{rendered,value})
    return rendered
  }),{when:({agent})=>{const a=assignment(agent);return !!a?.state&&['coding','testing','verification'].includes(a.role)}}))
  ctx.effect(()=>ctx.tools.register(tool('harness_run','Execute a software change through Planning, Coding, independent Verification, Testing where applicable, and final Reviewing. Required for modifying the managed workspace. Uses the actual current user request. Read-only questions do not need this tool.',object(),async(_args,exec)=>{
    const parent=exec.agent
    if(!isRoot(parent)||runs.size)throw Error('a managed root agent and exclusive workspace are required')
    const {request,seq,basis}=userBasis(parent)
    if(seenTurns.get(sessionId(parent))===seq)throw Error('this user request already started a Harness run; a new user request is required')
    const lock=acquireWorkspaceLock(root)
    let run
    try{
    seenTurns.set(sessionId(parent),seq)
    const abort=new AbortController()
    const signal=AbortSignal.any([exec.signal,abort.signal])
    run={id:randomUUID(),parent,abort,signal,lock,checks:new Set(),teardownFailed:false,fingerprintCount:0,fingerprintMs:0,phase:'setup',book:new EvidenceBook(libs,()=>fresh()),testProjects:discoverTests(root)}
    runs.set(run.id,run)
    const baseline=new Map()
    const checkRaw=(_state,c,checkSignal)=>runCheck(ctx,parent,root,c,()=>fresh(),s.compareFingerprints,xml,checkSignal,timeoutMs)
    const captureTrusted=async(state,c,value)=>{
      await run.book.capture({taskId:state.task.id,role:'host',agentId:'harness:'+run.id,sessionId:sessionId(parent)},{callId:randomUUID(),name:commandTool,arguments:{criterion_id:c.id},isError:false,value:resultForCapture(value)})
      log(run,{taskId:state.task.id,phase:'check:'+c.kind,detail:JSON.stringify(diagnostic(value))})
      return value
    }
    const tdd=tddController(root,run.testProjects,checkRaw,fresh,s.compareFingerprints)
    const host={
      progress:p=>{run.phase=p.phase;log(run,p)},
      async validate(plan){
        validateTaskPaths(root,plan,run.testProjects)
        for(const p of new Set(plan.flatMap(t=>t.codingFiles.concat(t.testFiles))))baseline.set(p,hashFiles(root,[p]))
      },
      async check(state,c,checkSignal){return captureTrusted(state,c,await checkRaw(state,c,checkSignal))},
      baseline:tdd.baseline,red:tdd.red,checkTdd:tdd.checkTdd,
      async green(state,red,checkSignal){const g=await tdd.green(state,red,checkSignal);if(g.run)await captureTrusted(state,state.task.criteria.find(c=>c.kind==='test'),g.run);return g},
      async changes(){
        const paths=[...baseline.keys()].filter(p=>hashFiles(root,[p])!==baseline.get(p))
        let diff=''
        try{if(paths.length)diff=execFileSync('git',['diff','--no-ext-diff','HEAD','--',...paths],{cwd:root,timeout:30000,maxBuffer:2*1024*1024,stdio:['ignore','pipe','pipe']}).toString('utf8').slice(0,16000)}catch{diff='Git diff unavailable; inspect all changed files directly.'}
        return {paths,diff,scope:'HEAD diff may include pre-existing edits; changed paths are measured against the run baseline. New files must be read directly.'}
      },
      async spawn(role,state,extra,schema,childSignal){
        if(!roles.includes(role)||childSignal.aborted)throw Error('invalid or cancelled role')
        const readOnly=['planning','verification','reviewing'].includes(role)
        const before=readOnly?fresh():null,id=randomUUID()
        const a={role,state,run,observed:new Set(),receipts:new Map()}
        assignments.set(id,a) // reserve before the native child can issue a tool call
        let activation
        let disposal
        const cancel=()=>{if(activation&&!disposal){disposal=activation.dispose();void disposal.catch(()=>{})}}
        try{
          const prompt=roleInstructions[role]+'\n'+JSON.stringify({...extra,workspace:root,...(role==='planning'?{testProjects:run.testProjects}:{} )})
          activation=await ctx.subagents.startActivation({provider:'spawn',childId:id,parent,cwd:root,label:(state?state.task.id+' ':'')+role,delivery:'caller',signal:childSignal,maxDepth:1,prompt:[{type:'text',text:prompt}],outputSchema:schema,agentPreset:presets[role]===null?undefined:presets[role]??'standard'})
          if(String(activation.childId)!==id)throw Error('native child did not preserve reserved identity')
          childSignal.addEventListener('abort',cancel,{once:true})
          if(childSignal.aborted)cancel()
          const result=await activation.result
          if(result.stopReason!=='completed'||childSignal.aborted||!result.structured)throw Error(role+' failed: '+result.stopReason)
          const after=readOnly?fresh():null
          if(readOnly&&s.compareFingerprints(before,after)!=='same')throw Error(role+' workspace changed or freshness unavailable: '+(before.reason??after.reason??'workspace changed'))
          if(role==='reviewing'&&result.structured.verdict==='pass'&&!extra.changes.paths.every(p=>a.observed.has(p)))throw Error('review did not inspect every changed planned file')
          return {structured:result.structured,observedPaths:[...a.observed],fingerprint:after,producer:{agentId:id,sessionId:id}}
        }finally{
          childSignal.removeEventListener('abort',cancel)
          try{if(activation)await(disposal??activation.dispose())}catch(error){run.teardownFailed=true;throw error}finally{assignments.delete(id)}
        }
      }
    }
    const result=await runEngineering(host,run.book,request,basis,run.id,sessionId(parent),signal,maxAttempts)
    lock.assertOwned()
    return JSON.stringify(result)
    }finally{
      if(!run){lock.release()}
      else{
        try{
          await Promise.allSettled([...run.checks])
          await run.book.drain()
          if(run.teardownFailed)throw Error('Harness teardown failed; workspace lock retained: '+lock.path)
          lock.release()
        }finally{
          runs.delete(run.id)
          console.log('[harness-dsh] '+JSON.stringify({runId:run.id,phase:'fingerprint-summary',count:run.fingerprintCount,totalMs:run.fingerprintMs}))
        }
      }
    }
  }),{when:({agent})=>isRoot(agent)}))
  ctx.on('session/disposed',session=>{seenTurns.delete(String(session.id))})
  ctx.effect(()=>()=>{for(const r of runs.values())r.abort.abort();seenTurns.clear()})
}

export async function apply(ctx,config){
  const [v,e,s,xml]=await Promise.all([import('@bpc-oss/dsh-verification'),import('@bpc-oss/dsh-evidence'),import('stalegreen'),import('fast-xml-parser')])
  mountEngineering(ctx,config,{v,e,s},createTrxParser(xml))
}
