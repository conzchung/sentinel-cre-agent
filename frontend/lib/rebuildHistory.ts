import type { Turn } from './types';
import { normalizePlan } from './planParse';
import { normalizeActions } from './streamParser';

// Turn a persisted dialog (list of {role, content, figures?, plan?, actions?})
// into render-ready Turn objects. Figures are raw Plotly JSON strings;
// unparseable ones are skipped while text is preserved. plan/actions are
// normalized the same way the live stream parser does — missing/malformed →
// []/pending, never throws — so a resumed conversation renders exactly as it did
// live. Mirrors the Python dialog_utils.rebuild_history.
export function rebuildHistory(dialog: unknown[]): Turn[] {
  const turns: Turn[] = [];
  for (const raw of dialog || []) {
    const msg = (raw || {}) as {
      role?: string;
      content?: string;
      figures?: unknown[];
      plan?: unknown;
      actions?: unknown;
    };
    const role: 'user' | 'assistant' = msg.role === 'assistant' ? 'assistant' : 'user';
    const charts: string[] = [];
    for (const fj of msg.figures || []) {
      if (typeof fj === 'string') {
        try {
          JSON.parse(fj);
          charts.push(fj);
        } catch {
          // skip unparseable figure
        }
      }
    }
    turns.push({
      role,
      text: msg.content || '',
      plan: normalizePlan(msg.plan),
      actions: normalizeActions(msg.actions),
      charts,
      suggestions: [],
    });
  }
  return turns;
}
