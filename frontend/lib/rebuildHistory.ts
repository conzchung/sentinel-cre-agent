import type { Turn } from './types';

// Turn a persisted dialog (list of {role, content, figures?}) into render-ready
// Turn objects. Figures are raw Plotly JSON strings; unparseable ones are
// skipped while text is preserved. Mirrors the Python dialog_utils.rebuild_history.
export function rebuildHistory(dialog: unknown[]): Turn[] {
  const turns: Turn[] = [];
  for (const raw of dialog || []) {
    const msg = (raw || {}) as { role?: string; content?: string; figures?: unknown[] };
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
      plan: [],
      actions: [],
      charts,
      suggestions: [],
    });
  }
  return turns;
}
