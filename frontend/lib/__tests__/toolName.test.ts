import { describe, it, expect } from 'vitest';
import { prettyToolName, toolIconKey } from '../toolName';

describe('prettyToolName', () => {
  it('title-cases snake_case tool ids', () => {
    expect(prettyToolName('read_skill')).toBe('Read Skill');
    expect(prettyToolName('query_dataset')).toBe('Query Dataset');
    expect(prettyToolName('web_search')).toBe('Web Search');
    expect(prettyToolName('render_chart')).toBe('Render Chart');
  });

  it('uppercases known acronyms', () => {
    expect(prettyToolName('knowledge_search_rag')).toBe('Knowledge Search RAG');
    expect(prettyToolName('generate_pdf')).toBe('Generate PDF');
  });

  it('handles kebab-case, extra spaces, and empty input', () => {
    expect(prettyToolName('create-plan')).toBe('Create Plan');
    expect(prettyToolName('  read   skill  ')).toBe('Read Skill');
    expect(prettyToolName('')).toBe('');
  });
});

describe('toolIconKey', () => {
  it('maps tool ids to icon keys by substring', () => {
    expect(toolIconKey('read_skill')).toBe('skill');
    expect(toolIconKey('query_dataset')).toBe('data');
    expect(toolIconKey('render_chart')).toBe('chart');
    expect(toolIconKey('web_search')).toBe('web');
    expect(toolIconKey('knowledge_search')).toBe('knowledge');
    expect(toolIconKey('generate_report')).toBe('report');
    expect(toolIconKey('create_plan')).toBe('plan');
  });

  it('falls back to a generic tool icon', () => {
    expect(toolIconKey('something_unknown')).toBe('tool');
    expect(toolIconKey('')).toBe('tool');
  });
});
