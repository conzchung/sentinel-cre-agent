import { NextRequest, NextResponse } from 'next/server';
import { getSession } from '@/lib/auth';
import { FASTAPI_URL, apiHeaders } from '@/lib/api';

export const runtime = 'nodejs';
export const dynamic = 'force-dynamic';

export async function POST(req: NextRequest) {
  const user = await getSession();
  if (!user) return NextResponse.json({ error: 'Unauthorized' }, { status: 401 });

  let body: { message?: string; thread_id?: string };
  try {
    body = await req.json();
  } catch {
    return NextResponse.json({ error: 'Invalid request' }, { status: 400 });
  }

  const upstream = await fetch(`${FASTAPI_URL}/market_agent/execution-agent-stream`, {
    method: 'POST',
    headers: apiHeaders({ 'Content-Type': 'application/json' }),
    body: JSON.stringify({
      message: body.message ?? '',
      thread_id: body.thread_id ?? '',
      user_id: user, // never trust a client-supplied user_id
    }),
  });

  return new NextResponse(upstream.body, {
    status: upstream.status,
    headers: { 'Content-Type': 'text/plain; charset=utf-8', 'Cache-Control': 'no-cache' },
  });
}
