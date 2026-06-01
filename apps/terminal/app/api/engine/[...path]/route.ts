/**
 * Server-side proxy to the Chainos Engine. The Terminal browser never holds the
 * Engine URL or any key; it only talks to this same-origin proxy, which forwards
 * to PRODUCTION read endpoints. (127.0.0.1, not localhost, to avoid IPv6 ::1.)
 */
import { type NextRequest } from 'next/server';

const ENGINE_URL = process.env.ENGINE_URL ?? 'http://127.0.0.1:8000';

export const dynamic = 'force-dynamic';

async function forward(req: NextRequest, path: string[]): Promise<Response> {
  const target = `${ENGINE_URL}/${path.join('/')}${req.nextUrl.search}`;
  const res = await fetch(target, {
    method: req.method,
    headers: { accept: req.headers.get('accept') ?? '*/*' },
  });
  const headers = new Headers();
  const ct = res.headers.get('content-type');
  if (ct) headers.set('content-type', ct);
  headers.set('cache-control', 'no-store');
  return new Response(res.body, { status: res.status, headers });
}

export async function GET(req: NextRequest, ctx: { params: { path: string[] } }) {
  return forward(req, ctx.params.path);
}
// Predict's cache-warm trigger is a POST; reads stay GET.
export async function POST(req: NextRequest, ctx: { params: { path: string[] } }) {
  return forward(req, ctx.params.path);
}
