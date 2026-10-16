import 'server-only';
import type { Me } from '@shopnod/shared-types';
import { cookies } from 'next/headers';

/** Server components talk to the real API directly (API_INTERNAL_URL) and forward the session cookie. */
export const API_INTERNAL_URL = process.env.API_INTERNAL_URL ?? 'http://localhost:8000';

export async function getMe(): Promise<Me | null> {
  const jar = await cookies();
  const session = jar.get('sn_session');
  if (!session) return null;
  try {
    const res = await fetch(`${API_INTERNAL_URL}/v1/auth/me`, {
      headers: { cookie: `sn_session=${session.value}` },
      cache: 'no-store',
    });
    return res.ok ? ((await res.json()) as Me) : null;
  } catch {
    return null;
  }
}
