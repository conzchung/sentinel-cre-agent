import { describe, it, expect } from 'vitest';
import { parsePlan } from '@/lib/planParse';

describe('parsePlan', () => {
  it('parses a python-repr list of step dicts', () => {
    const raw =
      "[{'content': 'Pull figures', 'status': 'in_progress', 'remarks': None}, " +
      "{'content': 'Compute YoY', 'status': 'pending', 'remarks': None}]";
    const steps = parsePlan(raw);
    expect(steps).toHaveLength(2);
    expect(steps[0]).toEqual({ content: 'Pull figures', status: 'in_progress', remarks: null });
    expect(steps[1].content).toBe('Compute YoY');
    expect(steps[1].status).toBe('pending');
  });

  it('preserves apostrophes inside content', () => {
    const raw = "[{'content': \"City's prime rents\", 'status': 'completed'}]";
    const steps = parsePlan(raw);
    expect(steps[0].content).toBe("City's prime rents");
    expect(steps[0].status).toBe('completed');
  });

  it('coerces an unknown status to pending', () => {
    const raw = "[{'content': 'x', 'status': 'weird'}]";
    expect(parsePlan(raw)[0].status).toBe('pending');
  });

  it('returns [] on empty or malformed input without throwing', () => {
    expect(parsePlan('')).toEqual([]);
    expect(parsePlan('not a list')).toEqual([]);
    expect(parsePlan('[{')).toEqual([]);
  });
});
