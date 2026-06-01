/**
 * Server-side proxy to the Chainos Engine. The Engine holds all LLM/provider
 * keys; the browser only ever talks to this same-origin proxy, so no key or
 * even the Engine URL is exposed client-side (CLAUDE.md §1.4). SSE streams pass
 * straight through (used by the agent console).
 */
import { type NextRequest } from 'next/server';

// 127.0.0.1 (not "localhost") to avoid Node resolving to IPv6 ::1 when the
// Engine is bound to IPv4.
const ENGINE_URL = process.env.ENGINE_URL ?? 'http://127.0.0.1:8000';

export const dynamic = 'force-dynamic';

async function forward(req: NextRequest, path: string[]): Promise<Response> {
  const search = req.nextUrl.search;
  const target = `${ENGINE_URL}/${path.join('/')}${search}`;

  const headers = new Headers();
  const ct = req.headers.get('content-type');
  if (ct) headers.set('content-type', ct);
  headers.set('accept', req.headers.get('accept') ?? '*/*');

  const hasBody = !['GET', 'HEAD'].includes(req.method);
  const init: RequestInit & { duplex?: 'half' } = {
    method: req.method,
    headers,
    body: hasBody ? req.body : undefined,
    duplex: hasBody ? 'half' : undefined,
  };

  const res = await fetch(target, init);
  // Pass the (possibly streaming) body straight back to the browser.
  const respHeaders = new Headers();
  const rct = res.headers.get('content-type');
  if (rct) respHeaders.set('content-type', rct);
  respHeaders.set('cache-control', 'no-cache, no-transform');
  return new Response(res.body, { status: res.status, headers: respHeaders });
}

export async function GET(req: NextRequest, ctx: { params: { path: string[] } }) {
  return forward(req, ctx.params.path);
}
export async function POST(req: NextRequest, ctx: { params: { path: string[] } }) {
  return forward(req, ctx.params.path);
}
export async function DELETE(req: NextRequest, ctx: { params: { path: string[] } }) {
  return forward(req, ctx.params.path);
}
export async function PATCH(req: NextRequest, ctx: { params: { path: string[] } }) {
  return forward(req, ctx.params.path);
}
