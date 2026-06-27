import { describe, it, expect } from 'vitest';
import { decodeChartBase64 } from '@/lib/chart';

describe('decodeChartBase64', () => {
  it('decodes base64 Plotly JSON back to the original string', () => {
    const figureJson = '{"data": [], "layout": {"title": {"text": "Hi"}}}';
    const b64 = Buffer.from(figureJson, 'utf-8').toString('base64');
    expect(decodeChartBase64(b64)).toBe(figureJson);
  });

  it('preserves a payload containing a literal </RESPONSE>', () => {
    const figureJson = '{"a": "</RESPONSE>"}';
    const b64 = Buffer.from(figureJson, 'utf-8').toString('base64');
    expect(decodeChartBase64(b64)).toBe(figureJson);
  });

  it('returns null on invalid base64 that is not valid JSON', () => {
    expect(decodeChartBase64('not valid json !!!')).toBeNull();
  });
});
