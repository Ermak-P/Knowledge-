import { createHash } from 'node:crypto'
import { verifyRed } from './reprolab/red-verifier.ts'
import { verifyGreen } from './reprolab/green-verifier.ts'
import { verifyRegression } from './reprolab/regression-verifier.ts'
import { gitFiles, hashFiles, isTestPath } from './dotnet.ts'

const hash=(v)=>createHash('sha256').update(JSON.stringify(v)).digest('hex')
const classifier=(run)=>({kind:run.classifier??'infra_failure',matchedTests:(run.results??[]).map(r=>r.name),summary:run.summary,fingerprint:run.classifier==='test_failure'?hash(run.failures.map(f=>[f.name,f.message])):null})
export function tddController(root,testProjects,check,fingerprint,compare){
  const testCriterion=s=>s.task.criteria.find(c=>c.kind==='test')
  const testDigest=s=>hashFiles(root,[...gitFiles(root).filter(p=>isTestPath(p,testProjects)||/\.(props|targets|runsettings|slnx?)$/i.test(p)||/(^|\/)(global\.json|nuget\.config)$/i.test(p)),...s.task.testFiles])
  const production=s=>fingerprint(s.task.testFiles.map(p=>'./'+p))
  return {
    checkTdd(s,red){return testDigest(s)===red.testPatchHash&&hash(testCriterion(s))===red.commandHash},
    async baseline(s,signal){
      const run=await check(s,testCriterion(s),signal)
      return {comparable:['test_pass','test_failure'].includes(run.classifier),failures:(run.failures??[]).map(f=>f.name),productionFingerprint:production(s)}
    },
    async red(s,base,expected,signal){
      if(!base.productionFingerprint?.available||compare(base.productionFingerprint,production(s))!=='same')return {valid:false,reason:'production changed before RED'}
      if(!Array.isArray(expected)||!expected.length||expected.some(x=>typeof x.name!=='string'||!x.name||typeof x.message!=='string'||!x.message||base.failures.includes(x.name)))return {valid:false,reason:'expected new failing tests must be named with failure reason'}
      const testPatchHash=testDigest(s),commandHash=hash(testCriterion(s)),run=await check(s,testCriterion(s),signal)
      if(testDigest(s)!==testPatchHash||compare(base.productionFingerprint,production(s))!=='same')return {valid:false,reason:'inputs changed during RED'}
      const failures=run.failures??[]
      if(!expected.every(e=>failures.some(f=>f.name===e.name&&f.message.includes(e.message)))||failures.some(f=>!base.failures.includes(f.name)&&!expected.some(e=>e.name===f.name&&f.message.includes(e.message))))return {valid:false,reason:'RED failed for an unexpected reason'}
      const result=verifyRed({testPatchHash,commandHash,fixFrozen:false,classifier:classifier(run)})
      return {valid:result.verdict==='valid_red',reason:result.reasons.join(', '),testPatchHash,commandHash,fingerprint:result.fingerprint,baseline:base.failures}
    },
    async green(s,red,signal){
      if(testDigest(s)!==red.testPatchHash)return {status:'blocked',reason:'frozen tests changed after RED'}
      const run=await check(s,testCriterion(s),signal)
      const g=verifyGreen({red,green:{testPatchHash:testDigest(s),commandHash:hash(testCriterion(s)),classifier:classifier(run)}})
      const r=verifyRegression({baseline:{ran:true,failures:red.baseline},candidate:{comparable:['test_pass','test_failure'].includes(run.classifier),failures:(run.failures??[]).map(f=>f.name)}})
      if(g.verdict==='valid_green'&&r.verdict==='pass')return {status:'pass',reason:'GREEN, no regression',run}
      return {status:run.classifier==='test_failure'&&testDigest(s)===red.testPatchHash?'fail':'blocked',reason:[...g.reasons,r.verdict].join(', '),run}
    }
  }
}
