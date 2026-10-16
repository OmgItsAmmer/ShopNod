/**
 * Same-origin proxy to the real API. The browser only calls `/api/...` on its own address, so the
 * session cookie belongs to this app (Plan 3 §0.2). Replies are streamed, so SSE keeps working.
 */
import type { NextRequest } from 'next/server';

export const dynamic = 'force-dynamic';
export const runtime = 'nodejs';

const API = (process.env.API_INTERNAL_URL ?? 'http://localhost:8000').replace(/\/$/, '');
const HOP_BY_HOP = ['connection', 'keep-alive', 'transfer-encoding', 'upgrade', 'proxy-authenticate', 'proxy-authorization', 'te', 'trailer'];

async function forward(req: NextRequest, ctx: { params: Promise<{ path: string[] }> }): Promise<Response> {
  const { path } = await ctx.params;
  const url = `${API}/${path.map(encodeURIComponent).join('/')}${req.nextUrl.search}`;

  const headers = new Headers(req.headers);
  for (const h of [...HOP_BY_HOP, 'host', 'content-length']) headers.delete(h);
  headers.set('x-forwarded-host', req.headers.get('host') ?? '');
  headers.set('x-forwarded-proto', req.nextUrl.protocol.replace(':', ''));
  const ip = req.headers.get('x-forwarded-for');
  if (ip) headers.set('x-forwarded-for', ip);

  const hasBody = !['GET', 'HEAD'].includes(req.method);
  let upstream: Response;
  try {
    upstream = await fetch(url, {
      method: req.method,
      headers,
      body: hasBody ? req.body : undefined,
      // @ts-expect-error `duplex` is required by Node's fetch when streaming a request body
      duplex: hasBody ? 'half' : undefined,
      redirect: 'manual',
      cache: 'no-store',
      signal: req.signal,
    });
  } catch {
    return Response.json(
      { error: { code: 'internal_error', message: 'ShopNod is not reachable right now. Please try again in a moment.', retryable: true, request_id: null } },
      { status: 502 },
    );
  }

  const out = new Headers();
  upstream.headers.forEach((value, key) => {
    const k = key.toLowerCase();
    if (HOP_BY_HOP.includes(k) || k === 'content-encoding' || k === 'content-length' || k === 'set-cookie') return;
    out.set(key, value);
  });
  for (const cookie of upstream.headers.getSetCookie()) out.append('set-cookie', cookie);
  return new Response(upstream.body, { status: upstream.status, statusText: upstream.statusText, headers: out });
}

export { forward as GET, forward as POST, forward as PUT, forward as DELETE, forward as PATCH };
