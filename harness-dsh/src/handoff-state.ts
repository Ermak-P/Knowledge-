// Passive, bounded host facts. No model calls, workspace writes or task authority.
export function createHandoffJournal({maxRuns=8,maxSteps=256,clock=Date.now}={}){
  const runs=new Map()
  let revision=0
  const text=(v,n=800)=>typeof v==='string'?v.slice(0,n):''
  const changed=r=>{r.updatedAt=clock();r.revision++;revision++}
  return {
    get revision(){return revision},
    start({runId,sessionId,workspace}){
      const now=clock()
      const r={id:runId,sessionId,workspace,startedAt:now,updatedAt:now,revision:0,status:'running',phase:'setup',taskId:null,detail:'',steps:[],totalSteps:0,truncated:false}
      runs.set(runId,r)
      revision++
      while(runs.size>maxRuns)runs.delete(runs.keys().next().value)
    },
    phase(id,p){const r=runs.get(id);if(!r)return;r.phase=text(p.phase,80);r.taskId=p.taskId??null;r.detail=text(p.detail);changed(r)},
    enter(id,{agentId,role,taskId=null,objective='',attempt=null,reason=''}){
      const r=runs.get(id);if(!r)return
      const previous=r.steps.at(-1)
      r.steps.push({id:agentId,order:++r.totalSteps,from:previous?.id??r.sessionId,role,taskId,objective:text(objective,300),attempt,reason:text(reason),startedAt:clock(),endedAt:null,status:'running',detail:''})
      if(r.steps.length>maxSteps){r.steps.shift();r.truncated=true}
      changed(r)
    },
    leave(id,agentId,{status='completed',detail=''}={}){
      const r=runs.get(id),s=r?.steps.find(s=>s.id===agentId)
      if(!s||s.endedAt!==null)return
      s.endedAt=clock();s.status=['completed','pass','rework','blocked','cancelled'].includes(status)?status:'blocked';s.detail=text(detail);changed(r)
    },
    finish(id,status,detail=''){
      const r=runs.get(id);if(!r)return
      r.status=['completed','cancelled','blocked'].includes(status)?status:'blocked';r.detail=text(detail)
      for(const s of r.steps)if(s.endedAt===null){s.endedAt=clock();s.status=r.status==='cancelled'?'cancelled':'blocked'}
      r.endedAt=clock();changed(r)
    },
    snapshot(){return structuredClone({runs:[...runs.values()].reverse()})}
  }
}

export const handoffJournal=createHandoffJournal()
