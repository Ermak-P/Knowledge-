// Self-contained browser function: injected by the optional observer, no bundle/build.
export function mountHandoffPanel(options){
  const boot=()=>{
    const old=document.getElementById('harness-dsh-handoffs')
    if(old)old.remove()
    const host=document.createElement('div');host.id='harness-dsh-handoffs';document.body.append(host)
    const shadow=host.attachShadow({mode:'open'})
    shadow.innerHTML=`<style>
      :host{all:initial;color-scheme:dark;font:14px system-ui,sans-serif;color:#e7edf7}
      *{box-sizing:border-box}button,select{font:inherit;color:inherit;background:#1a2538;border:1px solid #43536e;border-radius:9px;padding:8px 12px;cursor:pointer}
      button:focus-visible,select:focus-visible{outline:2px solid #73c9ff;outline-offset:3px}
      .launch{position:fixed;right:20px;bottom:76px;z-index:10000;box-shadow:0 8px 30px #0006}
      .panel{position:fixed;inset:7vh 4vw;z-index:10001;background:#0c1422;border:1px solid #34445d;border-radius:18px;box-shadow:0 24px 90px #0009;display:flex;flex-direction:column;overflow:hidden}
      [hidden]{display:none!important}header{display:flex;align-items:center;gap:14px;padding:18px 22px;border-bottom:1px solid #28374f}h2{font-size:18px;margin:0;flex:1}select{max-width:45%}
      .meta{padding:14px 22px;color:#aabbd2;line-height:1.6}.state{color:#8bd4ff;font-weight:600}.content{overflow:auto;padding:0 22px 24px;flex:1}
      .route{display:flex;flex-wrap:wrap;align-items:center;gap:10px;margin:12px 0 24px}.node{padding:12px 16px;border:1px solid #40516c;border-radius:12px;background:#172238;min-width:130px}.node small{display:block;color:#aabbd2;margin-top:5px}.node.active{border:2px solid #71c9ff;background:#17334b;box-shadow:0 0 20px #4aaeff25}.node.good{border-color:#4b9b78}.node.bad{border-color:#cf8860}.arrow{color:#7b9cbd;font-size:24px}
      .handoff{display:grid;grid-template-columns:6px 1fr;gap:14px;background:#141e30;border:1px solid #2e405a;border-radius:12px;margin:10px 0;padding:14px}.bar{border-radius:4px;background:#4d698e}.handoff.active .bar{background:#74ceff}.handoff.good .bar{background:#6dc89c}.handoff.bad .bar{background:#edac7a}.top{display:flex;gap:12px;justify-content:space-between}.title{font-weight:650}.detail{color:#bdcbe0;white-space:pre-wrap;overflow-wrap:anywhere;margin-top:8px}.muted{color:#91a5c0;font-size:12px;line-height:1.5}.tag{display:inline-block;background:#23354e;border-radius:5px;padding:2px 6px;margin:6px 5px 0 0;font-size:12px}
      .note{border-top:1px solid #28374f;color:#91a5c0;font-size:12px;padding:12px 22px}.empty{padding:30px 0;color:#aabbd2}#connection{color:#aabbd2;font-size:12px}@media(max-width:650px){.panel{inset:2vh 2vw}header{flex-wrap:wrap}select{max-width:100%;width:100%}.node{min-width:110px}}
      </style><button class="launch" type="button">⇄ Передача работы</button><section class="panel" role="dialog" aria-modal="true" aria-label="Передача работы между агентами" hidden><header><h2>Передача работы</h2><select aria-label="Запуск Harness"></select><button class="close" type="button" aria-label="Закрыть">Закрыть</button></header><div class="meta"><div id="connection">Подключение…</div><div id="status" class="state"></div><div id="workspace"></div><div id="phase"></div></div><div class="content"><div class="route"></div><div id="history"></div></div><div class="note">Фактическая последовательность запусков. Повторные проверки показаны отдельно. Вердикт агента и итог Harness различаются.</div></section>`
    const $=s=>shadow.querySelector(s),panel=$('.panel'),launch=$('.launch'),select=$('select')
    const labels={main:'Main',planning:'Planning',coding:'Coding',testing:'Testing',verification:'Verification',reviewing:'Reviewing'}
    const phases={'setup':'Подготовка','planning':'Планирование','coding':'Реализация','testing':'Тестирование','verification':'Проверка','gate':'Проверка критериев','accepted':'Задача принята','repair':'Возврат на исправление','repair-attempt':'Повторная попытка','refactor':'Рефакторинг','final-verification':'Повторная итоговая проверка','reviewing':'Финальное ревью','review-outcome':'Результат ревью','completed':'Завершено','blocked':'Заблокировано','cancelled':'Остановлено'}
    const states={running:'Работает',completed:'Ответ получен',pass:'Вердикт: pass',rework:'Нужна доработка',blocked:'Заблокировано',cancelled:'Остановлено'}
    let open=false,timer,controller,epoch=0,snapshot={runs:[]},selected='',revision='',priorFocus,followLatest=true,etag=''
    const el=(tag,cls,text)=>{const e=document.createElement(tag);if(cls)e.className=cls;if(text!==undefined)e.textContent=text;return e}
    const seconds=(start,end)=>Math.max(0,Math.floor(((end??Date.now())-start)/1000))+' с'
    const tone=s=>s==='running'?'active':['completed','pass'].includes(s)?'good':'bad'
    function render(force=false){
      const runs=snapshot.runs
      if(followLatest||!runs.some(r=>r.id===selected))selected=runs[0]?.id??''
      const r=runs.find(r=>r.id===selected),key=r?r.id+':'+r.revision:'empty'
      if(force||revision!==key){
        revision=key;select.replaceChildren(...runs.map(r=>{const o=el('option','',new Date(r.startedAt).toLocaleTimeString()+' · '+r.sessionId.slice(0,12));o.value=r.id;return o}));select.value=selected
        $('.route').replaceChildren();$('#history').replaceChildren()
        if(!r){$('#status').textContent='Ожидаем запуск Harness';$('#workspace').textContent='';$('#phase').textContent='';$('#history').append(el('div','empty','Начни задачу через harness_run. Здесь появятся реальные передачи работы.'));return}
        $('#workspace').textContent=r.workspace+' · сессия '+r.sessionId
        const current=r.steps.find(s=>s.status==='running')
        $('#status').textContent=(r.status==='completed'?'Harness: COMPLETED':r.status==='blocked'?'Harness: BLOCKED':r.status==='cancelled'?'Harness: CANCELLED':current?'Сейчас работает '+labels[current.role]:'Сейчас работает Harness')
        $('#phase').textContent='Этап: '+(phases[r.phase]??r.phase)+(r.taskId?' · задача '+r.taskId:'')+(r.detail?' · '+r.detail:'')
        const seq=[{role:'main',status:'completed',order:0},...r.steps]
        for(const [i,s] of seq.entries()){
          if(i)$('.route').append(el('span','arrow','→'))
          const n=el('div','node '+tone(s.status),labels[s.role]??s.role);n.append(el('small','',s.role==='main'?'Постановка задачи':(s.taskId??'План целиком')+(s.attempt?' · попытка '+s.attempt:'')));$('.route').append(n)
        }
        if(r.truncated)$('#history').append(el('p','muted','Показаны последние '+r.steps.length+' запусков из '+r.totalSteps+'.'))
        for(const [i,s] of r.steps.entries()){
          const prior=r.steps[i-1],from=prior?(labels[prior.role]??prior.role):(r.truncated?'Предыдущий агент':'Main')
          const item=el('article','handoff '+tone(s.status)),body=el('div'),top=el('div','top'),time=el('span','muted');time.dataset.start=s.startedAt;if(s.endedAt!==null)time.dataset.end=s.endedAt
          top.append(el('span','title',from+' → '+(labels[s.role]??s.role)),time);body.append(top)
          body.append(el('span','tag','#'+s.order),el('span','tag',states[s.status]??s.status))
          if(s.taskId)body.append(el('span','tag','Задача '+s.taskId));if(s.attempt)body.append(el('span','tag','Попытка '+s.attempt))
          if(s.objective)body.append(el('div','detail',s.objective))
          if(s.reason)body.append(el('div','detail','Передано: '+s.reason))
          if(s.detail)body.append(el('div','detail','Результат: '+s.detail))
          body.append(el('div','muted','Агент: '+s.id));item.append(el('div','bar'),body);$('#history').append(item)
        }
      }
      shadow.querySelectorAll('[data-start]').forEach(e=>{e.textContent=seconds(Number(e.dataset.start),e.dataset.end?Number(e.dataset.end):null)})
    }
    async function poll(){
      if(!open||document.hidden)return
      const mine=epoch,requestController=new AbortController();controller=requestController
      const deadline=setTimeout(()=>requestController.abort(),5000)
      try{
        const headers={'x-harness-handoff-token':options.token};if(etag)headers['If-None-Match']=etag
        const response=await fetch(options.path,{headers,cache:'no-store',signal:requestController.signal})
        if(response.status===304){if(mine===epoch){$('#connection').textContent='Наблюдение подключено';render()}return}
        if(!response.ok)throw Error('HTTP '+response.status)
        const next=await response.json();if(mine===epoch){snapshot=next;etag=response.headers.get('ETag')??'';$('#connection').textContent='Наблюдение подключено';render()}
      }catch(e){if(mine===epoch)$('#connection').textContent='Связь потеряна: '+e.message+' · последнее состояние сохранено'}
      finally{clearTimeout(deadline);if(controller===requestController)controller=undefined;if(mine===epoch&&open&&!document.hidden)timer=setTimeout(poll,1000)}
    }
    function stop(){epoch++;clearTimeout(timer);controller?.abort();controller=undefined}
    function close(){open=false;panel.hidden=true;launch.hidden=false;stop();priorFocus?.focus?.()}
    launch.onclick=()=>{priorFocus=document.activeElement;open=true;panel.hidden=false;launch.hidden=true;$('.close').focus();poll()}
    $('.close').onclick=close
    select.onchange=()=>{selected=select.value;followLatest=select.selectedIndex===0;render(true)}
    const visibility=()=>{stop();if(open&&!document.hidden)poll()}
    const keys=e=>{if(!open)return;if(e.key==='Escape'){e.preventDefault();e.stopPropagation();close()}else if(e.key==='Tab'){const xs=[select,$('.close')],at=shadow.activeElement;if(!e.shiftKey&&at===xs.at(-1)){e.preventDefault();xs[0].focus()}else if(e.shiftKey&&at===xs[0]){e.preventDefault();xs.at(-1).focus()}}}
    document.addEventListener('visibilitychange',visibility);shadow.addEventListener('keydown',keys)
    window.addEventListener('pagehide',stop,{once:true})
  }
  if(document.readyState==='loading')document.addEventListener('DOMContentLoaded',boot,{once:true});else boot()
}
