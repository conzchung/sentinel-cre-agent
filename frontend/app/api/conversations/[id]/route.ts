import { NextRequest, NextResponse } from 'next/server';
import { getSession } from '@/lib/auth';
import { FASTAPI_URL, apiHeaders } from '@/lib/api';

export const dynamic = 'force-dynamic';

export async function GET(_req: NextRequest, { params }: { params: Promise<{ id: string }> }) {
  const user = await getSession();
  if (!user) return NextResponse.json({ error: 'Unauthorized' }, { status: 401 });
  const { id } = await params;
  try {
    const r = await fetch(
      `${FASTAPI_URL}/market_agent/fetch-dialog/${encodeURIComponent(id)}`,
      { headers: apiHeaders() },
    );
    if (r.status === 404) return NextResponse.json({ dialog: [] });
    if (!r.ok) return NextResponse.json({ dialog: [] });
    return NextResponse.json(await r.json());
  } catch {
    return NextResponse.json({ dialog: [] });
  }
}

export async function DELETE(_req: NextRequest, { params }: { params: Promise<{ id: string }> }) {
  const user = await getSession();
  if (!user) return NextResponse.json({ error: 'Unauthorized' }, { status: 401 });
  const { id } = await params;
  try {
    const r = await fetch(
      `${FASTAPI_URL}/market_agent/delete-dialog/${encodeURIComponent(id)}`,
      { method: 'DELETE', headers: apiHeaders() },
    );
    return NextResponse.json({ ok: r.ok });
  } catch {
    return NextResponse.json({ ok: false });
  }
}
