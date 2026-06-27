import 'server-only';

import { cookies } from 'next/headers';
import { verifySession, SESSION_COOKIE } from './session';

// Read and verify the session cookie. Returns the username or null.
export async function getSession(): Promise<string | null> {
  const store = await cookies();
  return verifySession(store.get(SESSION_COOKIE)?.value);
}
