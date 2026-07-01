import { describe, it, expect } from 'vitest';
import { rebuildHistory } from '@/lib/rebuildHistory';

describe('rebuildHistory', () => {
  it('rebuilds user and assistant turns with valid figures', () => {
    const fig = '{"data": [], "layout": {}}';
    const dialog = [
      { role: 'user', content: 'hello', figures: [] },
      { role: 'assistant', content: 'hi there', figures: [fig] },
    ];
    const turns = rebuildHistory(dialog);
    expect(turns).toHaveLength(2);
    expect(turns[0]).toMatchObject({ role: 'user', text: 'hello', charts: [] });
    expect(turns[1]).toMatchObject({ role: 'assistant', text: 'hi there', charts: [fig] });
  });

  it('skips an unparseable figure but keeps the text', () => {
    const dialog = [{ role: 'assistant', content: 'answer', figures: ['{bad json'] }];
    const turns = rebuildHistory(dialog);
    expect(turns[0].text).toBe('answer');
    expect(turns[0].charts).toEqual([]);
  });

  it('handles null/empty dialog', () => {
    expect(rebuildHistory([])).toEqual([]);
    expect(rebuildHistory(null as unknown as unknown[])).toEqual([]);
  });

  it('restores persisted plan and actions on an assistant turn', () => {
    const dialog = [
      {
        role: 'assistant',
        content: 'Rents are firm.',
        plan: [{ content: 'Pull figures', status: 'completed', remarks: null }],
        actions: [{ tool: 'query_dataset', objective: 'City rents' }],
      },
    ];
    const turns = rebuildHistory(dialog);
    expect(turns[0].plan).toEqual([
      { content: 'Pull figures', status: 'completed', remarks: null },
    ]);
    expect(turns[0].actions).toEqual([{ tool: 'query_dataset', objective: 'City rents' }]);
  });

  it('restores old messages without plan/actions as empty arrays', () => {
    const turns = rebuildHistory([{ role: 'assistant', content: 'answer' }]);
    expect(turns[0].plan).toEqual([]);
    expect(turns[0].actions).toEqual([]);
  });

  it('coerces a malformed stored status to pending without throwing', () => {
    const dialog = [
      { role: 'assistant', content: 'x', plan: [{ content: 'y', status: 'bogus' }] },
    ];
    expect(rebuildHistory(dialog)[0].plan[0].status).toBe('pending');
  });
});
