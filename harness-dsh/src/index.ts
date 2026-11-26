import type { Context } from '@deepseek-ai/cordis'
import type {} from '@deepseek-ai/dsh-session'

export const name = 'harness-dsh'
export const inject = ['sessions']

export function apply(ctx: Context) {
  ctx.on('session/event', (session, event) => {
    switch (event.type) {
      case 'turn/start':
      case 'turn/end':
      case 'step/start':
      case 'step/end':
      case 'tool/result':
        console.log(`[harness-dsh] ${session.id} ${event.type}`)
        break
      case 'tool/call':
        console.log(`[harness-dsh] ${session.id} ${event.type} ${event.data.name}`)
        break
    }
  })
  ctx.effect(() => {
    console.log('[harness-dsh] loaded')
    return () => { console.log('[harness-dsh] unloaded') }
  })
}
