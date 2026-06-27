import { describe, it, expect } from 'vitest';
import { signSession, verifySession, checkCredentials } from '@/lib/session';

describe('session', () => {
  it('signs and verifies a round-trip', () => {
    const token = signSession('demo');
    expect(verifySession(token)).toBe('demo');
  });

  it('rejects a tampered token', () => {
    const token = signSession('demo');
    const tampered = token.slice(0, -1) + (token.endsWith('a') ? 'b' : 'a');
    expect(verifySession(tampered)).toBeNull();
  });

  it('rejects an impostor username with a stale signature', () => {
    const token = signSession('demo');
    const sig = token.split(':')[1];
    expect(verifySession(`admin:${sig}`)).toBeNull();
  });

  it('rejects undefined and malformed tokens', () => {
    expect(verifySession(undefined)).toBeNull();
    expect(verifySession('no-colon')).toBeNull();
  });

  it('checks the configured credentials case-insensitively on username', () => {
    expect(checkCredentials('demo', 'demo')).toBe(true);
    expect(checkCredentials('DEMO', 'demo')).toBe(true);
    expect(checkCredentials('demo', 'wrong')).toBe(false);
    expect(checkCredentials('someone', 'demo')).toBe(false);
  });
});
