import { execFileSync } from 'node:child_process';
import fs from 'node:fs';
import path from 'node:path';
import { BACKEND, DB, PY } from './env';

/**
 * Local runs (no E2E_BASE_URL): start from a fresh SQLite database with the schema and the demo data.
 * Against docker compose or live URLs, the api container already migrated and seeded, so nothing to do.
 */
export default function globalSetup() {
  if (process.env.E2E_BASE_URL || !DB.startsWith('sqlite')) return;
  const file = DB.replace(/^sqlite\+aiosqlite:\/\/\//, '');
  for (const f of [file, `${file}-wal`, `${file}-shm`]) fs.rmSync(f, { force: true });
  const env = { ...process.env, DATABASE_URL: DB };
  execFileSync(PY, ['-m', 'alembic', 'upgrade', 'head'], { cwd: BACKEND, env, stdio: 'inherit' });
  execFileSync(PY, [path.join(BACKEND, 'seed/seed.py')], { cwd: BACKEND, env, stdio: 'inherit' });
}
