import assert from 'node:assert/strict'
import { test } from 'node:test'
import { execFileSync, spawnSync } from 'node:child_process'
import { existsSync, mkdtempSync, rmSync } from 'node:fs'
import { tmpdir } from 'node:os'
import { join } from 'node:path'
import { acquireWorkspaceLock } from '../src/workspace-lock.ts'

const moduleUrl=new URL('../src/workspace-lock.ts',import.meta.url).href
function child(root: string, body: string) {
  return spawnSync(process.execPath,['--experimental-strip-types','--input-type=module','-e',`import { acquireWorkspaceLock } from ${JSON.stringify(moduleUrl)}; const lock=acquireWorkspaceLock(process.argv[1]); ${body}`,root],{encoding:'utf8',timeout:10000})
}
test('exclusive lock across processes, release and fail-closed abandoned lock',t=>{
  const root=mkdtempSync(join(tmpdir(),'dsh workspace '))
  t.after(()=>rmSync(root,{recursive:true,force:true}))
  execFileSync('git',['init','-q'],{cwd:root})
  const lock=acquireWorkspaceLock(root)
  lock.assertOwned()
  assert.throws(()=>acquireWorkspaceLock(root),/already locked/)
  const denied=child(root,'lock.release()')
  assert.notEqual(denied.status,0);assert.match(denied.stderr,/already locked/)
  lock.release();assert.equal(existsSync(lock.path),false)
  assert.equal(child(root,'lock.release()').status,0)
  assert.equal(child(root,'process.exit(0)').status,0)
  assert.throws(()=>acquireWorkspaceLock(root),/already locked/)
  // Fixture-only explicit recovery after the child has exited.
  rmSync(lock.path,{recursive:true})
  const next=acquireWorkspaceLock(root);next.release()
})
