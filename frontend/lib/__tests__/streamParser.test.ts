import { describe, it, expect } from 'vitest';
import { createStreamParser, parseActionBlock, emptyAssistantTurn } from '@/lib/streamParser';

function feedAll(parser: ReturnType<typeof createStreamParser>, chunks: string[]) {
  let turn = emptyAssistantTurn();
  for (const c of chunks) turn = parser.feed(c);
  return parser.end();
}

describe('parseActionBlock', () => {
  it('extracts tool + objective pairs', () => {
    const raw = '\n\nAction: query_dataset\nDetails: get prime rents\n';
    expect(parseActionBlock(raw)).toEqual([{ tool: 'query_dataset', objective: 'get prime rents' }]);
  });

  it('extracts multiple actions', () => {
    const raw =
      '\n\nAction: query_dataset\nDetails: rents\n\nAction: render_chart\nDetails: trend\n';
    expect(parseActionBlock(raw)).toEqual([
      { tool: 'query_dataset', objective: 'rents' },
      { tool: 'render_chart', objective: 'trend' },
    ]);
  });
});

describe('createStreamParser', () => {
  it('assembles plan, action, response, suggestions in order', () => {
    const stream =
      "<PLAN>\n[{'content': 'Step one', 'status': 'in_progress'}]\n</PLAN>\n\n" +
      '<ACTION>\n\nAction: query_dataset\nDetails: rents\n</ACTION>\n\n' +
      '<RESPONSE>\nCity prime rents are firm.\n</RESPONSE>\n\n' +
      '<SUGGESTION>\nCompute YoY growth\nChart the trend\nSearch live news\n</SUGGESTION>\n\n';
    const parser = createStreamParser();
    const turn = feedAll(parser, [stream]);
    expect(turn.plan).toEqual([{ content: 'Step one', status: 'in_progress', remarks: null }]);
    expect(turn.actions).toEqual([{ tool: 'query_dataset', objective: 'rents' }]);
    expect(turn.text).toBe('City prime rents are firm.');
    expect(turn.suggestions).toEqual(['Compute YoY growth', 'Chart the trend', 'Search live news']);
  });

  it('streams response text incrementally as it grows', () => {
    const parser = createStreamParser();
    parser.feed('<RESPONSE>\nHello');
    expect(parser.current().text).toBe('Hello');
    parser.feed(' world');
    expect(parser.current().text).toBe('Hello world');
    const turn = parser.feed('\n</RESPONSE>\n\n');
    expect(turn.text).toBe('Hello world');
  });

  it('handles a tag split across two chunks', () => {
    const parser = createStreamParser();
    parser.feed('<RESPONSE>\nDone</RESP');
    expect(parser.current().text).toBe('Done'); // partial close tag held back
    const turn = parser.feed('ONSE>\n\n');
    expect(turn.text).toBe('Done');
  });

  it('handles an OPEN tag split across two chunks', () => {
    const parser = createStreamParser();
    parser.feed('<RESP');
    expect(parser.current().text).toBe(''); // partial open tag not yet recognized
    const turn = parser.feed('ONSE>\nHello world\n</RESPONSE>\n\n');
    expect(turn.text).toBe('Hello world');
  });

  it('decodes a chart whose payload contains a literal </RESPONSE>', () => {
    const figureJson = '{"data": [], "layout": {"title": {"text": "</RESPONSE>"}}}';
    const b64 = Buffer.from(figureJson, 'utf-8').toString('base64');
    const stream = `<CHART>\n${b64}\n</CHART>\n\n<RESPONSE>\nText after chart.\n</RESPONSE>\n\n`;
    const parser = createStreamParser();
    const turn = feedAll(parser, [stream]);
    expect(turn.charts).toEqual([figureJson]);
    expect(turn.text).toBe('Text after chart.');
  });
});
