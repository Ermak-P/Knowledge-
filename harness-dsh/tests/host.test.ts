// Real Git/filesystem in Node; native DSH services and external libraries are doubles.
import assert from 'node:assert/strict'
import { test } from 'node:test'
import { mkdtempSync, mkdirSync, writeFileSync, readFileSync, rmSync, realpathSync } from 'node:fs'
import { tmpdir } from 'node:os'
import { join } from 'node:path'
import { execFileSync } from 'node:child_process'
import { projectRoot } from '../src/dotnet.ts'
import { mountEngineering } from '../src/engineering.ts'
import { mockLibraries } from './mock-libraries.ts'

async function exerciseHost(mount,root,libs,files,signal){
  let version=1,seq=0,disposed=0,checks=0
  const guards=[],listeners=new Map(),tools=new Map(),roles=[]
  const parent={id:'root',session:{id:'root',header:{cwd:root},snapshotEvents:()=>[{type:'turn/start',seq:1},{type:'user/message',seq:2,data:{source:{kind:'user'},content:[{type:'text',text:'Implement value'}]}}]}}
  const agents=new Map([[parent.id,parent]])
  libs.s.pathIgnorer=()=>()=>false
  libs.s.computeFingerprint=()=>({available:true,tree:'tree-'+version})
  const exec=(agent,name,args={})=>({agent,name,arguments:args,callId:'call-'+(++seq),signal})
  const deny=(a,n,args={})=>guards.some(g=>!!g(exec(a,n,args)))
  const emit=(call,value)=>{for(const l of listeners.get('tools/result')??[])l(call,{isError:false,value})}
  const ctx={
    agents:{get:id=>agents.get(id)},shell:{},
    on(name,listener){if(!listeners.has(name))listeners.set(name,[]);listeners.get(name).push(listener)},
    effect:register=>register(),
    tools:{guard(fn){guards.push(fn);return ()=>{}},register(def){tools.set(def.name,def);return ()=>{}}},
    subagents:{rootOf:()=>parent,async startActivation(spec){
      const role=spec.label.split(' ').at(-1);roles.push(role)
      assert.equal(spec.provider,'spawn');assert.equal(spec.delivery,'caller');assert.equal(spec.parent,parent)
      const child={id:spec.childId,session:{id:spec.childId,header:{cwd:root}}};agents.set(child.id,child)
      for(const name of ['bash','pwsh','run_code','apply_patch','update_goal','subagent','workflow','mcp__knowledge__knowledge_submit_candidates'])assert.equal(deny(child,name),true,role+' '+name)
      assert.equal(deny(child,'mcp__knowledge__knowledge_context'),false)
      let structured
      if(role==='planning'){
        assert.equal(deny(child,'write',{file_path:'Src/value.txt'}),true)
        structured={tasks:[{id:'one',objective:'write value',codingFiles:['Src/value.txt'],testFiles:['Tests/probe.txt'],tdd:false,criteria:[{id:'exists',desc:'file exists',kind:'file',target:'Src/value.txt'},{id:'semantic',desc:'value implements request',kind:'review',target:'Src/value.txt'}]}]}
      }else if(role==='coding'){
        assert.equal(deny(child,'write',{file_path:'Src/value.txt'}),false)
        for(const p of ['Tests/probe.txt','../escape.txt','Src/other.txt'])assert.equal(deny(child,'edit',{file_path:p}),true)
        assert.equal(deny(child,'write',{file_path:'Src/value.txt',sandbox_permissions:'require_escalated'}),true)
        files.write('Src/value.txt','implemented');version++
        const call=exec(child,'harness_run_check',{criterion_id:'exists'})
        emit(call,await tools.get(call.name).execute(call.arguments,call));checks++
        structured={verdict:'pass',detail:'coded'}
      }else if(role==='testing'){
        assert.equal(deny(child,'edit',{file_path:'Src/value.txt'}),true)
        assert.equal(deny(child,'write',{file_path:'Tests/probe.txt'}),false)
        files.write('Tests/probe.txt','test fixture');version++
        structured={verdict:'pass',detail:'tests inspected',expectedFailures:[]}
      }else if(role==='verification'){
        assert.equal(deny(child,'write',{file_path:'Src/value.txt'}),true)
        emit(exec(child,'read',{file_path:'Src/value.txt'}),files.read('Src/value.txt'))
        structured={verdict:'pass',detail:'verified',criteria:[{id:'semantic',verdict:'pass',detail:'actual matches expected',paths:['Src/value.txt']}]}
      }else if(role==='reviewing'){
        assert.equal(deny(child,'edit',{file_path:'Src/value.txt'}),true)
        for(const p of ['Src/value.txt','Tests/probe.txt'])emit(exec(child,'read',{file_path:p}),files.read(p))
        structured={verdict:'pass',detail:'reviewed',issues:[]}
      }else throw Error('unexpected role')
      return {childId:child.id,result:Promise.resolve({stopReason:'completed',structured}),async dispose(){disposed++;agents.delete(child.id)}}
    }}
  }
  mount(ctx,{workspace:root,readOnlyTools:['mcp__knowledge__knowledge_context']},libs,()=>{throw Error('XML not needed')})
  assert.equal(deny(parent,'write',{file_path:'Src/value.txt'}),true)
  assert.equal(deny(parent,'harness_run'),false)
  const tool=tools.get('harness_run')
  const result=JSON.parse(await tool.execute({},exec(parent,'harness_run')))
  assert.equal(result.status,'completed',result.reason)
  assert.equal(roles.join(','),'planning,coding,testing,verification,reviewing')
  assert.equal(disposed,5);assert.equal(checks,1)
  assert.equal(files.read('Src/value.txt'),'implemented');assert.equal(files.read('Tests/probe.txt'),'test fixture')
  await assert.rejects(()=>tool.execute({},exec(parent,'harness_run')))
  return result
}
export { exerciseHost }
test('native service doubles: guard, reserved identity, evidence capture, disposal and final acceptance',async t=>{
  const root=realpathSync(mkdtempSync(join(tmpdir(),'harness-dsh-host-')))
  t.after(()=>rmSync(root,{recursive:true,force:true}))
  execFileSync('git',['init','-q'],{cwd:root});mkdirSync(join(root,'Src'));mkdirSync(join(root,'Tests'))
  await exerciseHost(mountEngineering,root,mockLibraries(),{write:(p,v)=>writeFileSync(join(root,p),v),read:p=>readFileSync(join(root,p),'utf8')},new AbortController().signal)
})

test('repository root accepts equivalent Windows spelling and rejects nested directories', t=>{
  const root=realpathSync(mkdtempSync(join(tmpdir(),'harness-dsh-root-')))
  t.after(()=>rmSync(root,{recursive:true,force:true}))
  execFileSync('git',['init','-q'],{cwd:root})
  mkdirSync(join(root,'nested'))
  assert.equal(projectRoot(root),realpathSync.native(root))
  assert.throws(()=>projectRoot(join(root,'nested')), /workspace must be repository root/)
  if(process.platform==='win32'){
    assert.equal(projectRoot(root.replaceAll('\\','/')),realpathSync.native(root))
    const alternate=root.replace(/^[A-Za-z]:/,d=>d[0]===d[0].toUpperCase()?d.toLowerCase():d.toUpperCase())
    assert.equal(projectRoot(alternate).toLowerCase(),realpathSync.native(root).toLowerCase())
  }
})
