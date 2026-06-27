// Pure helpers that turn a raw backend tool id (e.g. "read_skill") into a
// human label ("Read Skill") and pick an icon key for it. Kept framework-free
// so they can be unit-tested; the React layer maps the icon key to an SVG.

import type { ToolIconKey } from './types';

export type { ToolIconKey };

const SPECIAL_CASE: Record<string, string> = {
  rag: 'RAG',
  pdf: 'PDF',
  url: 'URL',
  csv: 'CSV',
  id: 'ID',
};

/**
 * Title-case a snake_case / kebab-case tool id into a display label.
 * "read_skill" → "Read Skill", "web_search" → "Web Search".
 * Unknown shapes degrade gracefully (already-spaced or single words pass through).
 */
export function prettyToolName(tool: string): string {
  if (!tool) return '';
  return tool
    .trim()
    .split(/[_\s-]+/)
    .filter(Boolean)
    .map((w) => {
      const lower = w.toLowerCase();
      if (SPECIAL_CASE[lower]) return SPECIAL_CASE[lower];
      return lower.charAt(0).toUpperCase() + lower.slice(1);
    })
    .join(' ');
}

/** Choose an icon key for a raw tool id, matching on substrings. */
export function toolIconKey(tool: string): ToolIconKey {
  const t = (tool || '').toLowerCase();
  if (t.includes('chart') || t.includes('plot') || t.includes('figure')) return 'chart';
  if (t.includes('skill')) return 'skill';
  if (t.includes('report') || t.includes('pdf')) return 'report';
  if (t.includes('plan')) return 'plan';
  if (t.includes('knowledge') || t.includes('rag')) return 'knowledge';
  if (t.includes('web') || t.includes('search')) return 'web';
  if (t.includes('dataset') || t.includes('data') || t.includes('quer') || t.includes('analysis'))
    return 'data';
  return 'tool';
}
