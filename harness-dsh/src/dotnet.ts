// Trusted .NET verification. No agent-supplied shell fragments.
import { execFileSync } from 'node:child_process'
import { createHash } from 'node:crypto'
import { existsSync, lstatSync, readFileSync, realpathSync, readdirSync, mkdtempSync, rmSync } from 'node:fs'
import { tmpdir } from 'node:os'
import { resolve, relative, dirname, basename, isAbsolute, sep, join } from 'node:path'

export function safePath(root: string, value: string) {
  if(typeof value !== 'string'||!value.trim()||/[\0\r\n*?<>|"'$&;!%^\x60]/.test(value))throw Error('unsafe path')
  const target=resolve(root,value), rel=relative(root,target)
  if(!rel||rel==='..'||rel.startsWith('..'+sep)||isAbsolute(rel))throw Error('path outside workspace')
  const parts=rel.split(sep)
  if(parts.some(p=>p.includes(':')||p.endsWith('.')||p.endsWith(' ')||/^(\.git|\.knowledge|\.harness|\.maintenance|\.dsh|node_modules|bin|obj)$/i.test(p)))throw Error('protected path')
  let cur=root
  for(const part of parts){cur=join(cur,part);try{if(lstatSync(cur).isSymbolicLink())throw Error('symlink/junction path denied')}catch(e){if(e.code!=='ENOENT')throw e}}
  return rel.split(sep).join('/')
}
export function gitFiles(root: string): string[] {
  return [...new Set(execFileSync('git',['ls-files','-z','--cached','--others','--exclude-standard'],{cwd:root,maxBuffer:64*1024*1024,timeout:30000}).toString('utf8').split('\0').filter(Boolean))]
}
export function projectRoot(path: string) {
  const root=realpathSync(path)
  const git=realpathSync(execFileSync('git',['rev-parse','--show-toplevel'],{cwd:root,timeout:30000}).toString('utf8').trim())
  if(root!==git)throw Error('workspace must be repository root')
  return root
}
export function discoverTests(root: string) {
  return gitFiles(root).filter(p=>/Tests\.csproj$/i.test(p)&&existsSync(resolve(root,p))).sort()
}
export function isTestPath(path: string, projects: string[]) {
  const p=path.toLowerCase()
  return /(?:^|\/)[^/]*tests?(?:\/|\.csproj$)/i.test(p)||projects.some(x=>{const d=dirname(x).replaceAll('\\','/').toLowerCase();return d==='.'?p.endsWith('.cs')||p===x.toLowerCase():p.startsWith(d+'/')})
}
export function validateTaskPaths(root: string, plan, testProjects: string[]) {
  for(const task of plan){
    const paths=[...task.codingFiles,...task.testFiles]
    const key=p=>process.platform==='win32'?p.toLowerCase():p
    if(new Set(paths.map(key)).size!==paths.length)throw Error('overlapping file scopes')
    for(const p of paths){
      if(safePath(root,p)!==p)throw Error('plan paths must be canonical repo-relative: '+p)
      if(/(?:^|\/)(?:Directory\.Build\..*|Directory\.Packages\.props|global\.json|NuGet\.Config|[^/]*\.(?:props|targets|runsettings|sln|slnx))$/i.test(p))throw Error('build/test control file requires separate approval: '+p)
      if(task.codingFiles.includes(p)&&isTestPath(p,testProjects))throw Error('Coding scope contains tests: '+p)
      if(task.testFiles.includes(p)&&!isTestPath(p,testProjects))throw Error('Testing scope contains production file: '+p)
    }
    for(const c of task.criteria){
      if(safePath(root,c.target)!==c.target)throw Error('invalid criterion target')
      if(c.kind==='build'&&(!/\.(csproj|sln|slnx)$/i.test(c.target)||!existsSync(resolve(root,c.target))))throw Error('build target must exist')
      if(c.kind==='test'&&!testProjects.includes(c.target))throw Error('test target is not a discovered *Tests.csproj')
    }
    if(paths.some(p=>/\.(cs|csproj)$/i.test(p))){
      if(!task.criteria.some(c=>c.kind==='build'))throw Error('C# changes require a build criterion')
      if(!task.criteria.some(c=>c.kind==='test'))throw Error('C# changes require an actual discovered test project; no-test success is not supported')
    }
  }
}
function arr(v){return v===undefined||v===null?[]:Array.isArray(v)?v:[v]}
function integer(v){const n=typeof v==='number'?v:typeof v==='string'&&/^\d+$/.test(v)?Number(v):NaN;if(!Number.isSafeInteger(n)||n<0)throw Error('invalid TRX counter');return n}
export function summarizeTrx(documents){
  if(!documents.length)throw Error('no fresh TRX results')
  const results=[]
  let total=0,passed=0,failed=0,skipped=0
  for(const doc of documents){
    const run=doc.TestRun
    const counters=run?.ResultSummary?.Counters
    if(!counters)throw Error('missing TRX counters')
    const rows=arr(run.Results?.UnitTestResult)
    const n=integer(counters['@_total']),p=integer(counters['@_passed']),f=integer(counters['@_failed'])
    const local=rows.map(row=>{
      const name=row['@_testName'],outcome=row['@_outcome']
      if(typeof name!=='string'||!name||!['Passed','Failed','NotExecuted','Skipped'].includes(outcome))throw Error('unsupported or incomplete test result')
      const msg=row.Output?.ErrorInfo?.Message
      return {name,outcome,message:typeof msg==='string'?msg.slice(0,2000):''}
    })
    for(const k of ['error','timeout','aborted','inconclusive','notRunnable','disconnected','inProgress','pending'])if(counters['@_'+k]!==undefined&&integer(counters['@_'+k])!==0)throw Error('TRX infrastructure/incomplete outcome: '+k)
    const s=local.filter(x=>['NotExecuted','Skipped'].includes(x.outcome)).length
    if(n!==local.length||p!==local.filter(x=>x.outcome==='Passed').length||f!==local.filter(x=>x.outcome==='Failed').length||p+f+s!==n)throw Error('TRX counters do not match actual test rows')
    total+=n;passed+=p;failed+=f;skipped+=s;results.push(...local)
  }
  return {total,passed,failed,skipped,failures:results.filter(x=>x.outcome==='Failed'),results}
}
export function classifyTest(shell, trx){
  if(shell.aborted)return 'cancelled'
  if(shell.timedOut)return 'timed_out'
  if(shell.signal)return 'crashed'
  if(shell.sandbox?.denied||shell.sandbox?.runnerFailed||!Number.isInteger(shell.exitCode))return 'infra_failure'
  if(!trx)return 'infra_failure'
  if(trx.passed+trx.failed===0)return 'not_discovered'
  if(trx.skipped>0)return 'infra_failure'
  if(shell.exitCode===0&&trx.failed===0&&trx.passed>0)return 'test_pass'
  if(shell.exitCode!==0&&trx.failed>0)return 'test_failure'
  return 'infra_failure'
}
function quote(p: string){if(/[\r\n"$&;!%^\x60]/.test(p))throw Error('unsafe shell argument');return '"'+p.replaceAll('\\','/')+'"'}
function trxFiles(dir: string): string[]{return readdirSync(dir,{withFileTypes:true}).flatMap(e=>e.isSymbolicLink()?[]:e.isDirectory()?trxFiles(join(dir,e.name)):/\.trx$/i.test(e.name)?[join(dir,e.name)]:[])}
export function hashFiles(root: string, paths: string[]) {
  const hash=createHash('sha256')
  for(const p of [...new Set(paths)].sort()){
    safePath(root,p);hash.update(JSON.stringify(p))
    const path=resolve(root,p)
    if(existsSync(path)){const st=lstatSync(path);if(!st.isFile())throw Error('not a file: '+p);hash.update(createHash('sha256').update(readFileSync(path)).digest())}
    else hash.update('missing')
  }
  return hash.digest('hex')
}
export async function runCheck(ctx,agent,root,criterion,fresh,compare,xml,signal,timeoutMs=300000){
  const before=fresh()
  const unknown=reason=>({kind:criterion.kind,outcome:'unverified',summary:String(reason).slice(0,4000),fingerprint:fresh(),exitCode:null})
  if(signal.aborted||!before?.available)return unknown('cancelled or freshness unavailable')
  let temp,release
  try{
    const path=resolve(root,safePath(root,criterion.target))
    if(criterion.kind==='file'){
      const exists=existsSync(path)&&lstatSync(path).isFile()
      const after=fresh()
      return {kind:'file',outcome:compare(before,after)==='same'?(exists?'pass':'fail'):'unverified',exists,summary:exists?'file exists':'file missing',fingerprint:after}
    }
    if(!['build','test'].includes(criterion.kind)||!existsSync(path))return unknown('unknown or missing check target')
    let command='dotnet '+criterion.kind+' '+quote(path)
    if(criterion.kind==='test'){
      temp=mkdtempSync(join(tmpdir(),'harness-dsh-trx-'))
      // Respect the live native sandbox; never ask for wider privileges.
      if(ctx.shell.sandboxMode!==undefined){
        if(!ctx.sandboxPolicy?.registerWritableRoot)return unknown('native sandbox grant unavailable')
        release=ctx.sandboxPolicy.registerWritableRoot(agent.session,temp)
      }
      command+=' --logger trx --results-directory '+quote(temp)
    }
    const policy=ctx.sandboxPolicy?.resolve({session:agent.session})
    if(ctx.shell.sandboxMode!==undefined&&!policy)return unknown('native sandbox policy missing')
    const shell=await (await ctx.shell.execute(ctx.shell.resolve({command,workdir:root,timeoutMs,signal,...(policy?{sandboxPolicy:policy}:{})}))).result()
    const after=fresh()
    if(signal.aborted||compare(before,after)!=='same')return unknown('workspace changed, cancelled or fingerprint unavailable during check')
    const text=String(shell.stdout?.text??'')+'\n'+String(shell.stderr?.text??'')
    if(criterion.kind==='build'){
      const outcome=shell.aborted||shell.timedOut||shell.signal||shell.sandbox?.denied||shell.sandbox?.runnerFailed||!Number.isInteger(shell.exitCode)?'unverified':shell.exitCode===0?'pass':'fail'
      return {kind:'build',outcome,exitCode:shell.exitCode,summary:text.slice(-4000),fingerprint:after}
    }
    let trx,parseError=''
    try{
      const files=trxFiles(temp)
      if(files.length>100)throw Error('too many TRX files')
      trx=summarizeTrx(files.map(file=>{const st=lstatSync(file);if(st.size>64*1024*1024)throw Error('TRX exceeds size limit');return xml(readFileSync(file,'utf8'))}))
    }catch(e){parseError=String(e)}
    const classifier=classifyTest(shell,trx)
    const outcome=classifier==='test_pass'?'pass':classifier==='test_failure'?'fail':'unverified'
    return {kind:'test',outcome,exitCode:shell.exitCode,classifier,...(trx??{}),summary:(parseError||('passed='+ (trx?.passed??0)+' failed='+ (trx?.failed??0)+' skipped='+ (trx?.skipped??0)+'; '+classifier)).slice(0,4000),fingerprint:after}
  }catch(e){return unknown(e)}
  finally{try{release?.()}finally{if(temp)rmSync(temp,{recursive:true,force:true})}}
}
