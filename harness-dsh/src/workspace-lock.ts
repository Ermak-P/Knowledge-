import { execFileSync } from 'node:child_process'
import { randomUUID } from 'node:crypto'
import { mkdirSync, readFileSync, realpathSync, rmSync, writeFileSync } from 'node:fs'
import { join } from 'node:path'
import { hostname } from 'node:os'

// Cooperative, fail-closed lock in the actual worktree Git directory, outside the fingerprint scope.
// Never steal an abandoned lock automatically: a surviving child may still be modifying files.
export function acquireWorkspaceLock(root: string) {
  const gitDir=realpathSync(execFileSync('git',['rev-parse','--absolute-git-dir'],{cwd:root,encoding:'utf8',timeout:30000,windowsHide:true}).trim())
  const path=join(gitDir,'harness-dsh-run.lock'), ownerFile=join(path,'owner.json')
  const token=randomUUID()
  try{mkdirSync(path)}catch(error){
    if(error.code==='EEXIST')throw Error('Harness workspace already locked: '+path+'; stop all Harness processes before manual recovery')
    throw error
  }
  try{writeFileSync(ownerFile,JSON.stringify({token,pid:process.pid,host:hostname(),startedAt:new Date().toISOString()},null,2),{flag:'wx'})}
  catch(error){throw Error('Cannot record Harness lock ownership; manual recovery required: '+path+'; '+String(error))}
  const assertOwned=()=>{
    if(JSON.parse(readFileSync(ownerFile,'utf8')).token!==token)throw Error('Harness workspace lock ownership lost: '+path)
  }
  let released=false
  return {path,assertOwned,release(){
    if(released)return
    assertOwned()
    rmSync(path,{recursive:true})
    released=true
  }}
}
