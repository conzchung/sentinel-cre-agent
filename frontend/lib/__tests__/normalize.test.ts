import { describe, it, expect } from 'vitest';
import { normalizePlan } from '@/lib/planParse';
import { normalizeActions } from '@/lib/streamParser';

// The restore path receives plan/actions as already-parsed JSON arrays (Cosmos
// stores them verbatim), NOT the Python-repr strings the live <PLAN>/<ACTION>
// stream carries. These array normalizers mirror the live parsers' validation.
describe('normalizePlan', () => {
  it('restores a stored plan array of step objects', () => {
    const raw = [
      { content: 'Pull figures', status: 'completed', remarks: null },
      { content: 'Compute YoY', status: 'in_progress', remarks: 'wip' },
    ];
    expect(normalizePlan(raw)).toEqual([
      { content: 'Pull figures', status: 'completed', remarks: null },
      { content: 'Compute YoY', status: 'in_progress', remarks: 'wip' },
    ]);
  });

  it('coerces an unknown status to pending', () => {
    expect(normalizePlan([{ content: 'x', status: 'weird' }])[0].status).toBe('pending');
  });

  it('defaults a missing content to empty string and remarks to null', () => {
    expect(normalizePlan([{ status: 'completed' }])[0]).toEqual({
      content: '',
      status: 'completed',
      remarks: null,
    });
  });

  it('filters malformed entries and returns [] for a non-array', () => {
    expect(normalizePlan([null, 'nope', { content: 'ok', status: 'pending' }])).toEqual([
      { content: 'ok', status: 'pending', remarks: null },
    ]);
    expect(normalizePlan(undefined)).toEqual([]);
    expect(normalizePlan('not an array')).toEqual([]);
  });
});

describe('normalizeActions', () => {
  it('restores a stored actions array', () => {
    const raw = [
      { tool: 'query_dataset', objective: 'City rents' },
      { tool: 'render_chart', objective: 'trend' },
    ];
    expect(normalizeActions(raw)).toEqual(raw);
  });

  it('defaults a missing objective to empty string', () => {
    expect(normalizeActions([{ tool: 'list_skills' }])).toEqual([
      { tool: 'list_skills', objective: '' },
    ]);
  });

  it('filters malformed entries and returns [] for a non-array', () => {
    expect(normalizeActions([null, 42, { tool: 'web_search', objective: 'news' }])).toEqual([
      { tool: 'web_search', objective: 'news' },
    ]);
    expect(normalizeActions(undefined)).toEqual([]);
    expect(normalizeActions('nope')).toEqual([]);
  });
});
