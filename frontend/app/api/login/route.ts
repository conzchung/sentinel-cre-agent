import { NextRequest, NextResponse } from 'next/server';
import { checkCredentials, signSession, SESSION_COOKIE } from '@/lib/session';

export async function POST(req: NextRequest) {
  let body: { username?: string; password?: string };
  try {
    body = await req.json();
  } catch {
    return NextResponse.json({ error: 'Invalid request' }, { status: 400 });
  }
  if (!checkCredentials(body.username ?? '', body.password ?? '')) {
    return NextResponse.json({ error: 'Invalid username or password' }, { status: 401 });
  }
  // Sign the normalized username so the forced user_id is deterministic
  // regardless of the casing the client submitted.
  const res = NextResponse.json({ ok: true });
  res.cookies.set(SESSION_COOKIE, signSession((body.username ?? '').toLowerCase()), {
    httpOnly: true,
    sameSite: 'lax',
    path: '/',
    maxAge: 30 * 24 * 60 * 60,
  });
  return res;
}
