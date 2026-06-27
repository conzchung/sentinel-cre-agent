import type { PlanStep, PlanStatus } from './types';

const STATUSES: PlanStatus[] = ['pending', 'in_progress', 'completed', 'deleted'];

// A small tolerant parser for the subset of Python literal syntax the <PLAN>
// payload uses: lists, dicts, single/double-quoted strings (with backslash
// escapes), None/True/False, and numbers. Returns null on any malformed input
// rather than throwing, so a bad plan never breaks the render.
export function parsePyLiteral(src: string): unknown {
  let i = 0;

  function skipWs(): void {
    while (i < src.length && /\s/.test(src[i])) i++;
  }

  function parseValue(): unknown {
    skipWs();
    const c = src[i];
    if (c === '[') return parseList();
    if (c === '{') return parseDict();
    if (c === "'" || c === '"') return parseString();
    return parseAtom();
  }

  function parseList(): unknown[] {
    const arr: unknown[] = [];
    i++; // [
    skipWs();
    if (src[i] === ']') { i++; return arr; }
    while (i < src.length) {
      arr.push(parseValue());
      skipWs();
      if (src[i] === ',') { i++; skipWs(); if (src[i] === ']') { i++; return arr; } continue; }
      if (src[i] === ']') { i++; return arr; }
      throw new Error('bad list');
    }
    throw new Error('unterminated list');
  }

  function parseDict(): Record<string, unknown> {
    const obj: Record<string, unknown> = {};
    i++; // {
    skipWs();
    if (src[i] === '}') { i++; return obj; }
    while (i < src.length) {
      skipWs();
      const key = parseValue();
      skipWs();
      if (src[i] !== ':') throw new Error('expected :');
      i++;
      const val = parseValue();
      obj[String(key)] = val;
      skipWs();
      if (src[i] === ',') { i++; skipWs(); if (src[i] === '}') { i++; return obj; } continue; }
      if (src[i] === '}') { i++; return obj; }
      throw new Error('bad dict');
    }
    throw new Error('unterminated dict');
  }

  function parseString(): string {
    const quote = src[i];
    i++; // opening quote
    let out = '';
    while (i < src.length && src[i] !== quote) {
      if (src[i] === '\\') {
        i++;
        const e = src[i];
        out += e === 'n' ? '\n' : e === 't' ? '\t' : e;
        i++;
        continue;
      }
      out += src[i];
      i++;
    }
    if (src[i] !== quote) throw new Error('unterminated string');
    i++; // closing quote
    return out;
  }

  function parseAtom(): unknown {
    const m = /^(None|True|False|-?\d+(?:\.\d+)?)/.exec(src.slice(i));
    if (!m) throw new Error('bad atom');
    i += m[0].length;
    const t = m[0];
    if (t === 'None') return null;
    if (t === 'True') return true;
    if (t === 'False') return false;
    return Number(t);
  }

  try {
    const v = parseValue();
    return v;
  } catch {
    return null;
  }
}

export function parsePlan(raw: string): PlanStep[] {
  const value = parsePyLiteral((raw || '').trim());
  if (!Array.isArray(value)) return [];
  return value
    .filter((x): x is Record<string, unknown> => !!x && typeof x === 'object')
    .map((x) => {
      const status = x.status as PlanStatus;
      return {
        content: String(x.content ?? ''),
        status: STATUSES.includes(status) ? status : 'pending',
        remarks: (x.remarks ?? null) as string | null,
      };
    });
}
