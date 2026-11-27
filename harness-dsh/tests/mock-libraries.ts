// Test-only doubles.
function mockLibraries(){
  const stable=(x)=>JSON.stringify(x,(_k,v)=>v&&typeof v==='object'&&!Array.isArray(v)?Object.fromEntries(Object.keys(v).sort().map(k=>[k,v[k]])):v)
  const copy=x=>JSON.parse(JSON.stringify(x))
  const e={
    normalizedArgsHash:stable,TaskContractSchema:{parse:copy},CapturedEvidenceSchema:{parse:copy},
    contractIdentityOf:c=>({contractId:c.ref.contractId,revision:0,contractContentHash:c.ref.contractId,basisHash:c.ref.sourceBasis.sessionId,sessionId:c.ref.sourceBasis.sessionId}),
    identitiesEqual:(a,b)=>stable(a)===stable(b),
    deriveCaptured:(r,o)=>({callId:r.callId,toolIdentity:r.name,normalizedArgs:r.arguments,normalizedArgsHash:stable(r.arguments),schemaVersion:1,evidenceType:'command_output',payload:{},producedBy:'tool',failed:r.isError,contractIdentity:o.contractIdentity})
  }
  class Oracle{async judge(ac,ev){const p=ev.payload;return {acId:ac.id,result:ev.failed?'fail':ev.evidenceType==='file_exists'?(p.exists?'pass':'fail'):(p.exitCode===0?'pass':'fail'),oracleTier:'T0'}}}
  const v={
    mintContract:o=>({ref:{contractId:stable([o.sessionId,o.goal,o.acceptanceCriteria]),sourceBasis:{sessionId:o.sessionId}},origin:o.origin,goal:o.goal,acceptanceCriteria:o.acceptanceCriteria,constraints:o.constraints,inputs:o.inputs,outOfScope:o.outOfScope}),
    createMemoryBlobStore:()=>{const data=new Map();return {async write(v){const id=stable(v);data.set(id,copy(v));return id},async read(k){return data.get(k)??null},async delete(k){data.delete(k)}}},
    async storePayload(store,value){return {blobKey:await store.write(value),rawHash:stable(value),originalLength:stable(value).length,truncated:false}},
    async bindSelectorForAc(ac,ctx,_type,opts){
      if(opts.familyFallback)throw Error('fallback must be disabled')
      const matches=x=>e.identitiesEqual(x.contractIdentity,ctx.contractIdentity)&&x.toolIdentity===ac.selector.toolIdentity&&x.normalizedArgsHash===ac.selector.normalizedArgsHash
      const refs=ctx.refs.filter(matches).map(x=>({...x,failedCapture:false})),failures=ctx.captureFailures.filter(matches).map(x=>({...x,failedCapture:true}))
      const latest=refs.concat(failures).sort((a,b)=>b.resultSeq-a.resultSeq)[0]
      if(!latest)return {kind:'no-evidence',reason:'no exact evidence'}
      if(latest.failedCapture)return {kind:'capture-failure',reason:'latest capture failed'}
      const value=await ctx.loadBlob(latest.blobHash)
      return value?{kind:'bound',evidence:{...value,acId:ac.id},resultSeq:latest.resultSeq}:{kind:'missing-blob',reason:'blob missing'}
    },
    TestRunOracle:Oracle,FileExistsOracle:Oracle,CommandExitOracle:Oracle,
    VerificationEngine:class{constructor(oracles){this.oracles=oracles}async verify(ac,evidence,identity){return {...await this.oracles[0].judge(ac,evidence[0]),contractIdentity:identity}}},
    CompletionGate:class{evaluate(contract,verdicts){const all=contract.acceptanceCriteria.map(c=>verdicts.get(c.id)?.result);return {status:all.some(x=>x==='fail'||!x)?'failed':all.every(x=>x==='pass')?'done':'blocked',reasons:[]}}}
  }
  const s={compareFingerprints:(a,b)=>!a?.available||!b?.available||!a.tree||!b.tree?'unknown':a.tree===b.tree?'same':'different'}
  return {e,v,s}
}
export { mockLibraries }
