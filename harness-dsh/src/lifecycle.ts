// Host-neutral task policy. All production evidence/oracles are supplied by the reviewed upstream packages.


function freeze(value){if(value&&typeof value==='object'&&!Object.isFrozen(value)){for(const v of Object.values(value))freeze(v);Object.freeze(value)}return value}

function validatePlan(raw){
  if(!raw||!Array.isArray(raw.tasks)||raw.tasks.length===0||raw.tasks.length>32)throw Error('plan must contain 1–32 tasks')
  const ids=new Set()
  const str=(v)=>typeof v==='string'&&v.trim().length>0&&v.length<=8000
  const files=(v)=>{if(!Array.isArray(v)||v.length>100||v.some(x=>!str(x))||new Set(v).size!==v.length)throw Error('invalid file scope');return [...v]}
  return freeze(raw.tasks.map(t=>{
    if(!str(t.id)||! /^[a-zA-Z0-9_-]{1,48}$/.test(t.id)||ids.has(t.id)||!str(t.objective))throw Error('invalid or duplicate task id/objective')
    ids.add(t.id)
    if(t.refactor!==undefined&&typeof t.refactor!=='boolean')throw Error('invalid refactor flag')
    if(t.refactor&&!t.tdd)throw Error('refactor stage requires TDD')
    if(typeof t.tdd!=='boolean'||!Array.isArray(t.criteria)||!t.criteria.length||t.criteria.length>32)throw Error('invalid task criteria')
    const codingFiles=files(t.codingFiles),testFiles=files(t.testFiles)
    if(codingFiles.some(x=>testFiles.includes(x)))throw Error('overlapping coding/testing scope')
    const cids=new Set()
    const criteria=t.criteria.map(c=>{
      if(!str(c.id)||! /^[a-zA-Z0-9_-]{1,48}$/.test(c.id)||cids.has(c.id)||!str(c.desc)||!['build','test','file','review'].includes(c.kind)||!str(c.target))throw Error('invalid acceptance criterion')
      cids.add(c.id)
      return {id:c.id,desc:c.desc,kind:c.kind,target:c.target}
    })
    if(t.tdd&&(!testFiles.length||criteria.filter(c=>c.kind==='test').length!==1))throw Error('TDD requires test files and exactly one frozen test criterion')
    return {id:t.id,objective:t.objective,codingFiles,testFiles,tdd:t.tdd,refactor:t.refactor??false,criteria}
  }))
}

const planSchema = {
  "type": "object",
  "properties": {
    "tasks": {
      "type": "array",
      "items": {
        "type": "object",
        "properties": {
          "id": {
            "type": "string"
          },
          "objective": {
            "type": "string"
          },
          "codingFiles": {
            "type": "array",
            "items": {
              "type": "string"
            }
          },
          "testFiles": {
            "type": "array",
            "items": {
              "type": "string"
            }
          },
          "tdd": {
            "type": "boolean"
          },
            "refactor": {"type":"boolean"},
          "criteria": {
            "type": "array",
            "items": {
              "type": "object",
              "properties": {
                "id": {
                  "type": "string"
                },
                "desc": {
                  "type": "string"
                },
                "kind": {
                  "type": "string",
                  "enum": [
                    "build",
                    "test",
                    "file",
                    "review"
                  ]
                },
                "target": {
                  "type": "string"
                }
              },
              "required": [
                "id",
                "desc",
                "kind",
                "target"
              ],
              "additionalProperties": false
            }
          }
        },
        "required": [
          "id",
          "objective",
          "codingFiles",
          "testFiles",
          "tdd",
          "criteria"
        ],
        "additionalProperties": false
      }
    }
  },
  "required": [
    "tasks"
  ],
  "additionalProperties": false
}

const resultSchema = {
  "type": "object",
  "properties": {
    "verdict": {
      "type": "string",
      "enum": [
        "pass",
        "rework",
        "blocked"
      ]
    },
    "detail": {
      "type": "string"
    }
  },
  "required": [
    "verdict",
    "detail"
  ],
  "additionalProperties": false
}

const verificationSchema = {
  "type": "object",
  "properties": {
    "verdict": {
      "type": "string",
      "enum": [
        "pass",
        "rework",
        "blocked"
      ]
    },
    "detail": {
      "type": "string"
    },
    "criteria": {
      "type": "array",
      "items": {
        "type": "object",
        "properties": {
          "id": {
            "type": "string"
          },
          "verdict": {
            "type": "string",
            "enum": [
              "pass",
              "rework",
              "blocked"
            ]
          },
          "detail": {
            "type": "string"
          },
          "paths": {
            "type": "array",
            "items": {
              "type": "string"
            }
          }
        },
        "required": [
          "id",
          "verdict",
          "detail",
          "paths"
        ],
        "additionalProperties": false
      }
    }
  },
  "required": [
    "verdict",
    "detail",
    "criteria"
  ],
  "additionalProperties": false
}

const testingSchema = {
  "type": "object",
  "properties": {
    "verdict": {
      "type": "string",
      "enum": [
        "pass",
        "rework",
        "blocked"
      ]
    },
    "detail": {
      "type": "string"
    },
    "expectedFailures": {
      "type": "array",
      "items": {
        "type": "object",
        "properties": {
          "name": {
            "type": "string"
          },
          "message": {
            "type": "string"
          }
        },
        "required": [
          "name",
          "message"
        ],
        "additionalProperties": false
      }
    }
  },
  "required": [
    "verdict",
    "detail",
    "expectedFailures"
  ],
  "additionalProperties": false
}

const reviewSchema = {
  "type": "object",
  "properties": {
    "verdict": {
      "type": "string",
      "enum": [
        "pass",
        "rework",
        "blocked"
      ]
    },
    "detail": {
      "type": "string"
    },
    "issues": {
      "type": "array",
      "items": {
        "type": "object",
        "properties": {
          "taskId": {
            "type": "string"
          },
          "detail": {
            "type": "string"
          }
        },
        "required": [
          "taskId",
          "detail"
        ],
        "additionalProperties": false
      }
    }
  },
  "required": [
    "verdict",
    "detail",
    "issues"
  ],
  "additionalProperties": false
}

class EvidenceBook {
  constructor(lib, fingerprint){this.lib=lib;this.fingerprint=fingerprint;this.store=lib.v.createMemoryBlobStore();this.tasks=new Map();this.seq=0;this.pending=new Set()}
  add(task,runId,sessionId,basis){
    if(this.tasks.has(task.id))throw Error('duplicate task')
    const {v,e}=this.lib
    const criteria=task.criteria.map(c=>({id:c.id,desc:c.desc,oracleHint:c.kind==='test'?'test':c.kind==='file'?'file':c.kind==='review'?'review':'run',...(c.kind==='review'?{}:{selector:{schemaVersion:1,toolIdentity:'harness_run_check',normalizedArgsHash:e.normalizedArgsHash({criterion_id:c.id}),evidenceType:c.kind==='test'?'test_run':c.kind==='file'?'file_exists':'command_output'}})}))
    const contract=freeze(e.TaskContractSchema.parse(v.mintContract({sessionId,origin:'model-self-declared',goal:runId+'/'+task.id+': '+task.objective,acceptanceCriteria:criteria,constraints:[],inputs:task.codingFiles.concat(task.testFiles),outOfScope:[],basis})))
    const state={task,contract,identity:freeze(e.contractIdentityOf(contract)),refs:[],failures:[],semantic:new Map(),attempts:0,red:null}
    this.tasks.set(task.id,state);return state
  }
  capture(assignment,record){
    const state=this.tasks.get(assignment.taskId)
    if(!state||!['coding','testing','verification','host'].includes(assignment.role)||record.name!=='harness_run_check')return
    const seq=++this.seq
    const job=this.captureOne(state,assignment,record,seq)
    this.pending.add(job);void job.finally(()=>this.pending.delete(job)).catch(()=>{})
    return job
  }
  async captureOne(state,assignment,record,seq){
    const {e,v}=this.lib
    const base={contractIdentity:state.identity,callId:String(record.callId),toolIdentity:record.name,normalizedArgsHash:e.normalizedArgsHash(record.arguments),resultSeq:seq,producerAgentId:assignment.agentId,producerSessionId:assignment.sessionId,taskId:state.task.id}
    const criterion=state.task.criteria.find(c=>c.id===record.arguments.criterion_id&&c.kind!=='review')
    if(!criterion)return
    const fail=(reason)=>state.failures.push({...base,evidenceType:'command_output',error:reason})
    try{
      const value=record.value
      if(record.isError||!value||value.kind!==criterion.kind||!['pass','fail'].includes(value.outcome)||!value.fingerprint?.available||!value.fingerprint.tree){fail('failed, interrupted or unavailable check');return}
      if(state.refs.length+state.failures.length>=200){state.captureOverflow=true;fail('evidence limit reached');return}
      let captured=e.deriveCaptured({...record,content:[],meta:undefined},{contractIdentity:state.identity,parseTestRuns:false})
      if(!captured){fail('cannot derive evidence');return}
      const payload=criterion.kind==='test'?{exitCode:value.exitCode,passCount:value.passed,failCount:value.failed,output:value.summary}:criterion.kind==='file'?{path:criterion.target,exists:value.exists}:{exitCode:value.exitCode,stdout:value.summary}
      if(criterion.kind==='test'&&(!Number.isInteger(value.passed)||!Number.isInteger(value.failed)||value.passed+value.failed===0||value.skipped!==0||(value.outcome==='pass'&&(value.failed!==0||value.passed===0)))){fail('no executed tests');return}
      if(criterion.kind!=='file'&&(!Number.isInteger(value.exitCode)||(value.outcome==='pass'&&value.exitCode!==0))){fail('missing or inconsistent exit status');return}
      captured=e.CapturedEvidenceSchema.parse({...captured,evidenceType:criterion.kind==='test'?'test_run':criterion.kind==='file'?'file_exists':'command_output',payload,failed:value.outcome!=='pass'})
      const stored=await v.storePayload(this.store,captured)
      if(stored.truncated){fail('truncated evidence');return}
      state.refs.push({...base,evidenceType:captured.evidenceType,blobHash:stored.blobKey,rawHash:stored.rawHash,originalLength:stored.originalLength,truncated:false,completeness:'complete',schemaVersion:1,summary:value.summary??'',fingerprint:freeze(structuredClone(value.fingerprint)),outcome:value.outcome})
    }catch(error){fail(String(error))}
  }
  async drain(){while(this.pending.size)await Promise.all([...this.pending])}
  recordSemantic(state,review,observedPaths,fingerprint,producer){
    const expected=state.task.criteria.filter(c=>c.kind==='review')
    if(!Array.isArray(review?.criteria)||review.criteria.length!==expected.length)throw Error('missing semantic verdicts')
    const entries=new Map()
    for(const c of expected){
      const matches=review.criteria.filter(x=>x.id===c.id)
      const r=matches[0]
      if(matches.length!==1||!['pass','rework','blocked'].includes(r.verdict)||typeof r.detail!=='string'||!r.detail.trim()||!Array.isArray(r.paths)||!r.paths.length||!r.paths.every(p=>observedPaths.includes(p)))throw Error('semantic verdict lacks observed file evidence')
      if(!r.paths.includes(c.target))throw Error('semantic criterion target was not observed')
      entries.set(c.id,freeze({verdict:r.verdict,detail:r.detail,paths:[...r.paths],fingerprint:structuredClone(fingerprint),producer}))
    }
    state.semantic=entries
  }
  async evaluate(state){
    await this.drain()
    const {v,e,s}=this.lib
    if(state.captureOverflow)return {status:'blocked',details:[{reason:'evidence limit reached'}],reasons:['evidence limit reached']}
    const now=this.fingerprint(),verdicts=new Map(),details=[]
    let uncertain=false
    const failure=(ac,reason,blocked=true)=>{if(blocked)uncertain=true;details.push({id:ac.id,reason});verdicts.set(ac.id,{claimId:ac.id,acId:ac.id,result:blocked?'need_human':'fail',oracleTier:'T4',contractIdentity:state.identity,detail:reason})}
    for(const ac of state.contract.acceptanceCriteria){
      if(ac.oracleHint==='review'){
        const r=state.semantic.get(ac.id)
        if(!r||s.compareFingerprints(r.fingerprint,now)!=='same'){failure(ac,'missing or stale independent semantic review');continue}
        if(r.verdict!=='pass'){failure(ac,r.detail,r.verdict==='blocked');continue}
        verdicts.set(ac.id,{claimId:ac.id,acId:ac.id,result:'pass',oracleTier:'T2',contractIdentity:state.identity,detail:r.detail});continue
      }
      const outcome=await v.bindSelectorForAc(ac,{contractIdentity:state.identity,refs:state.refs,captureFailures:state.failures,loadBlob:key=>this.store.read(key)},()=>ac.selector.evidenceType,{familyFallback:false})
      if(outcome.kind!=='bound'){failure(ac,outcome.reason??'missing evidence');if(outcome.kind==='no-evidence')details.at(-1).recheck=true;continue}
      const ref=state.refs.find(r=>r.resultSeq===outcome.resultSeq)
      if(!ref||ref.taskId!==state.task.id||s.compareFingerprints(ref.fingerprint,now)!=='same'){failure(ac,'missing or stale evidence');details.at(-1).recheck=true;continue}
      if(ref.outcome!=='pass'||outcome.evidence.failed){failure(ac,'actual check failed',false);continue}
      if(outcome.evidence.evidenceType!==ac.selector.evidenceType||!e.identitiesEqual(outcome.evidence.contractIdentity,state.identity)){failure(ac,'evidence identity/type mismatch');continue}
      try{
        const oracle=ac.oracleHint==='test'?new v.TestRunOracle():ac.oracleHint==='file'?new v.FileExistsOracle():new v.CommandExitOracle()
        const verdict=await new v.VerificationEngine([oracle]).verify(ac,[outcome.evidence],state.identity)
        if(verdict.result!=='pass')details.push({id:ac.id,reason:verdict.detail??'oracle rejected evidence'})
        verdicts.set(ac.id,verdict)
      }catch(error){failure(ac,String(error))}
    }
    const gate=new v.CompletionGate().evaluate(state.contract,verdicts,[])
    const stable=s.compareFingerprints(now,this.fingerprint())==='same'
    return {status:!stable?'blocked':gate.status==='done'?'pass':gate.status==='failed'?'fail':'blocked',details:stable?details:[...details,{reason:'workspace changed or freshness unavailable during gate'}],reasons:gate.reasons,fingerprint:now,uncertain}
  }
}

async function runEngineering(host,book,request,basis,runId,sessionId,signal,maxAttempts=3){
  const progress=(phase,task,detail='')=>host.progress({phase,taskId:task?.id??null,detail})
  const check=()=>{if(signal.aborted)throw Error('cancelled')}
  const child=async(role,state,extra,schema)=>{
    check();progress(role,state?.task)
    const result=await host.spawn(role,state,extra,schema,signal)
    check()
    if(!result||!result.structured)throw Error(role+' returned no validated structured result')
    return result
  }
  const taskPrompt=(s)=>({task:s.task,contract:s.contract})
  const verify=async(s)=>{
    progress('verification',s.task)
    let gate=await book.evaluate(s)
    if(gate.status==='pass')return gate
    // Deterministic work is executed by the trusted host only when missing or stale.
    // Fresh failed evidence is not retried until Coding repairs it.
    if(host.check){
      for(const detail of gate.details){
        const c=s.task.criteria.find(c=>c.id===detail.id&&c.kind!=='review')
        if(c&&detail.recheck){check();await host.check(s,c,signal)}
      }
      gate=await book.evaluate(s)
      if(gate.status==='pass'||gate.status==='fail')return gate
      if(!s.task.criteria.some(c=>c.kind==='review'))return gate
    }
    const result=await child('verification',s,{...taskPrompt(s),missing:gate.details},verificationSchema)
    if(result.structured.verdict==='blocked')return {status:'blocked',details:[{reason:result.structured.detail}]}
    if(result.structured.verdict==='rework')return {status:'fail',details:[{reason:result.structured.detail}]}
    if(result.structured.verdict!=='pass')return {status:'blocked',details:[{reason:'invalid verification verdict'}]}
    book.recordSemantic(s,result.structured,result.observedPaths,result.fingerprint,result.producer)
    return book.evaluate(s)
  }
  const execute=async(s,reason)=>{
    while(s.attempts<maxAttempts){
      check();s.attempts++;s.semantic.clear()
      if(s.task.tdd&&!s.red){
        const baseline=await host.baseline(s,signal)
        if(!baseline.comparable)throw Error('TDD baseline unavailable')
        const tested=await child('testing',s,{...taskPrompt(s),mode:'RED',baseline},testingSchema)
        if(tested.structured.verdict!=='pass')throw Error('Testing did not prepare RED: '+tested.structured.detail)
        s.red=await host.red(s,baseline,tested.structured.expectedFailures,signal)
        if(!s.red.valid)throw Error('invalid RED: '+s.red.reason)
      }
      const coded=await child('coding',s,{...taskPrompt(s),repair:reason},resultSchema)
      if(coded.structured.verdict==='rework'){reason=coded.structured.detail;continue}
      if(coded.structured.verdict!=='pass')throw Error('Coding did not complete: '+coded.structured.detail)
      if(!s.task.tdd&&(s.task.testFiles.length||s.task.criteria.some(c=>c.kind==='test'))){
        const tested=await child('testing',s,{...taskPrompt(s),mode:'test and assess coverage'},testingSchema)
        if(tested.structured.verdict!=='pass')throw Error('Testing did not accept test quality: '+tested.structured.detail)
      }
      if(s.red){
        const g=await host.green(s,s.red,signal)
        if(g.status==='blocked')throw Error(g.reason)
        if(g.status==='fail'){reason=g.reason;continue}
        if(s.task.refactor&&!s.refactored){
          s.refactored=true;progress('refactor',s.task)
          const r=await child('coding',s,{...taskPrompt(s),mode:'refactor only; preserve behavior',repair:''},resultSchema)
          if(r.structured.verdict==='blocked')throw Error('refactor blocked: '+r.structured.detail)
          if(r.structured.verdict!=='pass'){reason=r.structured.detail;continue}
          const after=await host.green(s,s.red,signal)
          if(after.status==='blocked')throw Error(after.reason)
          if(after.status==='fail'){reason=after.reason;continue}
        }
      }
      const gate=await verify(s)
      if(gate.status==='pass'){progress('accepted',s.task);return}
      if(gate.status==='blocked')throw Error('unverified '+s.task.id+': '+JSON.stringify(gate.details))
      reason=JSON.stringify(gate.details);progress('repair',s.task,reason)
    }
    throw Error('repair limit reached for '+s.task.id)
  }
  try{
    check()
    const planned=await child('planning',null,{request},planSchema)
    const plan=validatePlan(planned.structured)
    await host.validate(plan)
    const states=plan.map(t=>book.add(t,runId,sessionId,basis))
    for(const s of states)await execute(s,'')
    for(let round=0;round<=maxAttempts*states.length;round++){
      check();progress('final-verification',null)
      let repaired=false
      for(const s of states){
        if(s.red&&host.checkTdd&&!host.checkTdd(s,s.red))throw Error('frozen TDD inputs changed: '+s.task.id)
        const gate=await verify(s)
        if(gate.status==='blocked')throw Error('final verification unavailable for '+s.task.id)
        if(gate.status==='fail'){await execute(s,JSON.stringify(gate.details));repaired=true;break}
      }
      if(repaired)continue
      const reviewed=await child('reviewing',null,{request,plan,attempts:states.map(s=>({taskId:s.task.id,attempts:s.attempts})),changes:await host.changes()},reviewSchema)
      const r=reviewed.structured
      if(r.verdict==='pass'&&Array.isArray(r.issues)&&!r.issues.length){
        for(const s of states)if((await book.evaluate(s)).status!=='pass')throw Error('evidence changed after review')
        if(!reviewed.fingerprint?.available||book.lib.s.compareFingerprints(reviewed.fingerprint,book.fingerprint())!=='same')throw Error('review snapshot stale')
        progress('completed',null);return {status:'completed',tasks:states.map(s=>({id:s.task.id,attempts:s.attempts}))}
      }
      if(r.verdict!=='rework'||!Array.isArray(r.issues)||!r.issues.length)throw Error('review blocked: '+r.detail)
      const affected=new Map()
      for(const issue of r.issues){const s=book.tasks.get(issue.taskId);if(!s||typeof issue.detail!=='string'||!issue.detail.trim())throw Error('invalid review finding');affected.set(s,(affected.get(s)??'')+'\n'+issue.detail)}
      for(const [s,why] of affected)await execute(s,why)
    }
    throw Error('final review repair limit reached')
  }catch(error){const status=signal.aborted?'cancelled':'blocked';progress(status,null,String(error));return {status,reason:String(error)}}
}

export { freeze, validatePlan, planSchema, resultSchema, verificationSchema, testingSchema, reviewSchema, EvidenceBook, runEngineering }
