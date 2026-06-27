import { NextResponse } from 'next/server';
import { getSession } from '@/lib/auth';
import { FASTAPI_URL, apiHeaders } from '@/lib/api';

export const dynamic = 'force-dynamic';

export async function GET() {
  const user = await getSession();
  if (!user) return NextResponse.json({ error: 'Unauthorized' }, { status: 401 });

  try {
    const r = await fetch(
      `${FASTAPI_URL}/market_agent/user-thread-ids/${encodeURIComponent(user)}`,
      { headers: apiHeaders() },
    );
    if (r.status === 404) return NextResponse.json([]);
    if (!r.ok) return NextResponse.json([]);
    return NextResponse.json(await r.json());
  } catch {
    return NextResponse.json([]);
  }
}
