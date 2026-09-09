import type { H3WindowPlan } from '../types'

/** Move narrative content between existing time slots, keeping timed assets
 * attached to their slots. Continuity must be reviewed in the new order. */
export function reorderWindowPrompts(plan: H3WindowPlan, from: number, to: number): H3WindowPlan {
  if (from === to || from < 0 || to < 0 || from >= plan.windows.length || to >= plan.windows.length) return plan
  const order = [...plan.windows]
  const [moved] = order.splice(from, 1)
  order.splice(to, 0, moved)
  const windows = order.map((content, position) => {
    const slot = plan.windows[position]
    return {
      ...content, index: position + 1,
      start_frame: slot.start_frame, end_frame: slot.end_frame,
      start_seconds: slot.start_seconds, end_seconds: slot.end_seconds,
      injected_keyframes: slot.injected_keyframes,
      opening_state: '', closing_state: '',
    }
  })
  const warning = 'Window order changed. Timing and timed references keep their slots; review dialogue, action duration and transitions before approval.'
  return { ...plan, windows, window_prompts: windows.map(window => window.prompt), order_edited: true,
    planning_warnings: [...new Set([...(plan.planning_warnings || []), warning])] }
}
