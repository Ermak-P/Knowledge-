// Optional DSH Desktop/Web observer. Uses the existing listener; no extra server.
import { randomBytes, timingSafeEqual } from 'node:crypto'
import { handoffJournal } from './handoff-state.ts'
import { mountHandoffPanel } from './handoff-client.js'

export const name='harness-dsh-handoffs'
export const inject=['webServer']

export function mountHandoffs(ctx,journal=handoffJournal){
  const token=randomBytes(32).toString('hex')
  const path='/plugins/harness-dsh/handoffs/'+randomBytes(8).toString('hex')
  ctx.effect(()=>ctx.webServer.register({kind:'exact',path,auth:'anonymous',handler(req,res){
    res.setHeader('Cache-Control','no-store')
    res.setHeader('X-Content-Type-Options','nosniff')
    if(req.method!=='GET'){res.writeHead(405,{'Allow':'GET'});res.end();return}
    const supplied=req.headers['x-harness-handoff-token']
    if(typeof supplied!=='string'||!/^[0-9a-f]{64}$/.test(supplied)||!timingSafeEqual(Buffer.from(supplied),Buffer.from(token))){res.writeHead(403);res.end();return}
    const etag='"'+journal.revision+'"';res.setHeader('ETag',etag)
    if(req.headers['if-none-match']===etag){res.writeHead(304);res.end();return}
    res.writeHead(200,{'Content-Type':'application/json; charset=utf-8'})
    res.end(JSON.stringify(journal.snapshot()))
  }}))
  ctx.on('webserver/index-inject',table=>{
    table.push({kind:'script',placement:'body',text:'('+mountHandoffPanel.toString()+')('+JSON.stringify({path,token})+');'})
  })
}

export function apply(ctx){mountHandoffs(ctx)}
