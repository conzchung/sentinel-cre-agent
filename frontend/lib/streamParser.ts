import { parsePlan } from './planParse';
import { decodeChartBase64 } from './chart';
import type { Turn, Action } from './types';

const OPEN_TAGS = ['<PLAN>', '<ACTION>', '<RESPONSE>', '<SUGGESTION>', '<CHART>'] as const;
type OpenTag = (typeof OPEN_TAGS)[number];
const CLOSE: Record<OpenTag, string> = {
  '<PLAN>': '</PLAN>',
  '<ACTION>': '</ACTION>',
  '<RESPONSE>': '</RESPONSE>',
  '<SUGGESTION>': '</SUGGESTION>',
  '<CHART>': '</CHART>',
};

export function emptyAssistantTurn(): Turn {
  return { role: 'assistant', text: '', plan: [], actions: [], charts: [], suggestions: [] };
}

// Parse an <ACTION> block ("\n\nAction: tool\nDetails: objective\n...") into pairs.
export function parseActionBlock(raw: string): Action[] {
  const actions: Action[] = [];
  for (const block of raw.split('Action:').slice(1)) {
    const lines = block.split('\n');
    const tool = (lines[0] || '').trim();
    const detail = lines.find((l) => l.trim().startsWith('Details:'));
    const objective = detail ? detail.replace('Details:', '').trim() : '';
    if (tool) actions.push({ tool, objective });
  }
  return actions;
}

// Restore persisted actions (an already-parsed JSON array of {tool, objective})
// into Action[]. Missing / non-array → []; malformed entries filtered; missing
// objective → ''. The array twin of parseActionBlock (which parses the live
// <ACTION> text stream) — kept alongside it so the two stay in sync.
export function normalizeActions(raw: unknown): Action[] {
  if (!Array.isArray(raw)) return [];
  return raw
    .filter((x): x is Record<string, unknown> => !!x && typeof x === 'object')
    .map((x) => ({ tool: String(x.tool ?? ''), objective: String(x.objective ?? '') }))
    .filter((a) => a.tool);
}

// If the tail of `s` is a proper prefix of `close`, hold it back so a half-formed
// closing tag is never rendered as response text.
function holdBackPartialClose(s: string, close: string): string {
  const max = Math.min(close.length - 1, s.length);
  for (let k = max; k > 0; k--) {
    if (s.endsWith(close.slice(0, k))) return s.slice(0, s.length - k);
  }
  return s;
}

export function createStreamParser() {
  let buffer = '';
  let responseText = '';
  let turn = emptyAssistantTurn();

  function applyTag(tag: OpenTag, inner: string): void {
    if (tag === '<PLAN>') {
      turn.plan = parsePlan(inner);
    } else if (tag === '<ACTION>') {
      turn.actions = [...turn.actions, ...parseActionBlock(inner)];
    } else if (tag === '<SUGGESTION>') {
      turn.suggestions = inner.split('\n').map((s) => s.trim()).filter(Boolean);
    } else if (tag === '<CHART>') {
      const json = decodeChartBase64(inner);
      if (json) turn.charts = [...turn.charts, json];
    }
  }

  function process(): void {
    while (true) {
      // Find the earliest open tag in the buffer.
      let idx = -1;
      let tag: OpenTag | '' = '';
      for (const t of OPEN_TAGS) {
        const at = buffer.indexOf(t);
        if (at !== -1 && (idx === -1 || at < idx)) {
          idx = at;
          tag = t;
        }
      }
      if (idx === -1 || tag === '') return;

      const close = CLOSE[tag];
      const contentStart = idx + tag.length;
      const closeIdx = buffer.indexOf(close, contentStart);

      if (tag === '<RESPONSE>') {
        if (closeIdx === -1) {
          // Stream the partial response, holding back a possible partial close tag.
          const partial = holdBackPartialClose(buffer.slice(contentStart), close);
          turn.text = (responseText + partial).trim();
          return; // wait for more
        }
        responseText += buffer.slice(contentStart, closeIdx);
        turn.text = responseText.trim();
        buffer = buffer.slice(closeIdx + close.length);
        continue;
      }

      // Atomic tags: wait until the full closing tag has arrived.
      if (closeIdx === -1) return;
      applyTag(tag, buffer.slice(contentStart, closeIdx));
      buffer = buffer.slice(closeIdx + close.length);
    }
  }

  return {
    feed(chunk: string): Turn {
      buffer += chunk;
      process();
      return { ...turn };
    },
    current(): Turn {
      return { ...turn };
    },
    end(): Turn {
      process();
      return { ...turn };
    },
  };
}
