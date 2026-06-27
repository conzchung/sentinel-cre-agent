import crypto from 'node:crypto';

// Secret used to HMAC-sign the session cookie. Required: there is no insecure
// default — a publicly-known fallback would let anyone forge a valid cookie.
function getSecret(): string {
  const secret = process.env.COOKIE_SECRET;
  if (!secret) {
    throw new Error('COOKIE_SECRET is not set. Set it before signing sessions.');
  }
  return secret;
}

// Single demo account, configured via env so no credentials live in the repo.
// Falls back to a generic placeholder for local development only.
const USERNAME = (process.env.AUTH_USERNAME || 'demo').toLowerCase();
const PASSWORD = process.env.AUTH_PASSWORD || 'demo';

export const SESSION_COOKIE = 'sentinel_session';

function hmac(username: string): string {
  return crypto.createHmac('sha256', getSecret()).update(username).digest('hex');
}

export function signSession(username: string): string {
  return `${username}:${hmac(username)}`;
}

export function verifySession(token: string | undefined): string | null {
  if (!token) return null;
  const idx = token.lastIndexOf(':');
  if (idx <= 0) return null;
  const username = token.slice(0, idx);
  const sig = token.slice(idx + 1);
  const expected = hmac(username);
  const a = Buffer.from(sig);
  const b = Buffer.from(expected);
  if (a.length === b.length && crypto.timingSafeEqual(a, b)) return username;
  return null;
}

export function checkCredentials(username: string, password: string): boolean {
  return (username || '').toLowerCase() === USERNAME && password === PASSWORD;
}
