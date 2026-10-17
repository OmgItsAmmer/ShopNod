import path from 'node:path';

/** Paths and URLs shared by the Playwright config, the global setup and the specs. */
export const ROOT = path.resolve(__dirname, '../..');
export const BACKEND = path.join(ROOT, 'backend');
export const DB = process.env.E2E_DATABASE_URL ?? `sqlite+aiosqlite:///${path.join(BACKEND, 'e2e.db').replaceAll('\\', '/')}`;
export const PY = process.env.E2E_PYTHON ?? path.join(BACKEND, '.venv', process.platform === 'win32' ? 'Scripts/python.exe' : 'bin/python');
