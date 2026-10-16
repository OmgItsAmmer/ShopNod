/**
 * Plan 2 standalone checks, driven through the real browser UI:
 * wizard (< 90 s), "I'm quiet" -> proposal card, keyboard-only inbox, edit refused by guardrails,
 * approve, reject, scan by short code, billing, RTL, MCP confirmation card, and an axe accessibility pass.
 * (Plan 3's full-loop test reuses these flows.)
 */
import { execFileSync } from 'node:child_process';
import path from 'node:path';
import AxeBuilder from '@axe-core/playwright';
import { type Page, expect, test } from '@playwright/test';

const backend = path.resolve(__dirname, '../../backend');
const DB = process.env.E2E_DATABASE_URL ?? `sqlite+aiosqlite:///${path.join(backend, 'e2e.db').replaceAll('\\', '/')}`;
const PY = process.env.E2E_PYTHON ?? path.join(backend, '.venv', process.platform === 'win32' ? 'Scripts/python.exe' : 'bin/python');

/** Plan 1 is not built yet: `dev_claim.py` makes a claim and prints its QR text and short code. */
function devClaim(shopId: string): { short_code: string; qr_text: string } {
  const out = execFileSync(PY, [path.join(backend, 'seed/dev_claim.py'), '--shop', shopId], {
    cwd: backend,
    env: { ...process.env, DATABASE_URL: DB },
    encoding: 'utf8',
  });
  const get = (k: string) => out.split('\n').find((l) => l.trim().startsWith(`${k}:`))!.split(': ').slice(1).join(': ').trim();
  return { short_code: get('short_code'), qr_text: get('qr_text') };
}

async function shopIdOf(page: Page): Promise<string> {
  const me = await page.request.get('/api/v1/auth/me');
  return (await me.json()).shop.id;
}

/** Landing -> "Try as a judge" -> 3-step wizard -> dashboard. Returns the elapsed seconds. */
async function completeWizard(page: Page, name = 'E2E Bakery', category = /Bakery/): Promise<number> {
  const t0 = Date.now();
  await page.goto('/');
  await page.getByTestId('demo-login').click();
  await expect(page).toHaveURL(/onboarding\/shop/);
  await page.getByLabel('Shop name').fill(name);
  await page.getByRole('radio', { name: category }).check({ force: true });
  await page.getByRole('button', { name: 'Continue' }).click();
  await expect(page).toHaveURL(/onboarding\/location/);
  await page.getByTestId('use-demo-market').click();
  await expect(page).toHaveURL(/onboarding\/review/);
  await expect(page.getByRole('table').first()).toBeVisible();
  await page.getByTestId('finish-setup').click();
  await expect(page).toHaveURL(/dashboard/);
  await expect(page.getByTestId('im-quiet')).toBeVisible();
  return (Date.now() - t0) / 1000;
}

async function simulateQuiet(page: Page) {
  await page.getByTestId('simulate-quiet').click();
  await expect(page.getByTestId('proposal-card').first()).toBeVisible({ timeout: 10_000 });
}

test.describe.configure({ mode: 'serial' });

test('wizard: judge goes from the landing page to their dashboard in under 90 seconds', async ({ page }) => {
  const seconds = await completeWizard(page);
  expect(seconds).toBeLessThan(90);
  await expect(page.getByTestId('shop-name')).toHaveText('E2E Bakery');
  await expect(page.getByTestId('shopper-qr')).toBeVisible();
  const href = await page.getByTestId('shopper-url').getAttribute('href');
  expect(href).toMatch(/\/\?market=demo&shop=[0-9a-f-]{36}$/);
  // the browser only ever talks to its own origin
  const external: string[] = [];
  page.on('request', (r) => {
    const u = new URL(r.url());
    if (u.origin !== 'http://localhost:3000' && !u.hostname.endsWith('openstreetmap.org') && u.protocol.startsWith('http')) external.push(r.url());
  });
  await page.reload();
  await expect(page.getByTestId('im-quiet')).toBeVisible();
  expect(external).toEqual([]);
});

test('inbox: "Simulate a quiet hour" gives a proposal card, and it works with the keyboard only', async ({ page }) => {
  await completeWizard(page, 'Keyboard Bakery');
  await simulateQuiet(page);
  const card = page.getByTestId('proposal-card').first();
  await expect(card.getByTestId('proposal-reason')).not.toBeEmpty();
  await expect(card.getByText('Rule-based')).toBeVisible(); // no OpenAI key: honest label
  await expect(card.getByTestId('margin-chip').first()).toBeVisible(); // costs are known from the template
  await expect(page.getByTestId('inbox')).toContainText('J / K move');

  // keyboard: focus the card, press E (edit) -> dialog -> Escape; then A approves
  await card.focus();
  await page.keyboard.press('e');
  await expect(page.getByRole('dialog')).toBeVisible();
  await page.keyboard.press('Escape');
  await expect(page.getByRole('dialog')).toBeHidden();
  await card.focus();
  await page.keyboard.press('a');
  await expect(page.getByText('Offer published')).toBeVisible();
  await expect(page.getByTestId('offer-card').first()).toBeVisible();
  await expect(page.getByTestId('proposal-card')).toHaveCount(0);
});

test('edit to 40% is refused with the limit; edit to 15% publishes with the offer-text label', async ({ page }) => {
  await completeWizard(page, 'Edit Bakery');
  await simulateQuiet(page);
  await page.getByTestId('edit').first().click();
  const dialog = page.getByRole('dialog');
  await dialog.locator('#edit-pct').fill('40');
  await expect(dialog.getByText(/Above your 25% limit/)).toBeVisible();
  await dialog.getByTestId('edit-approve').click();
  await expect(page.getByText(/The most you allow is 25%/)).toBeVisible(); // 422 guardrail_violation, with the limit
  await expect(dialog).toBeVisible(); // nothing was published or changed
  // 15% for 30 customers would exceed the daily budget: refused with the money amounts, never adjusted
  await dialog.locator('#edit-pct').fill('15');
  await dialog.getByTestId('edit-approve').click();
  await expect(page.getByText(/only .* is left in your discount budget/)).toBeVisible();
  await dialog.locator('#edit-cap').fill('20');
  await expect(dialog.getByText('AI-written, approved by the shop')).toBeVisible();
  await dialog.getByTestId('edit-approve').click();
  await expect(page.getByText('Offer published')).toBeVisible();
  const card = page.getByTestId('offer-card').first();
  await expect(card).toContainText('15');
  // the decision is in the approvals log, with its channel
  await page.goto('/audit');
  await expect(page.getByTestId('audit-table')).toContainText('Edited from 10% to 15%');
  await expect(page.getByTestId('audit-table')).toContainText('Dashboard');
  // and the learning page shows the next proposal now starts at the edited 15%
  await page.goto('/insights');
  await expect(page.getByTestId('next-proposal')).toContainText('15%');
  await expect(page.getByTestId('learning-chart')).toBeVisible();
});

test('reject with a reason', async ({ page }) => {
  await completeWizard(page, 'Reject Bakery');
  await simulateQuiet(page);
  await page.getByTestId('reject').first().click();
  await page.getByLabel('Too generous').check();
  await page.getByTestId('confirm-reject').click();
  await expect(page.getByText('Rejected. ShopNod will learn from this.')).toBeVisible();
  await expect(page.getByTestId('proposal-card')).toHaveCount(0);
  await page.goto('/insights');
  await expect(page.getByText('Too generous')).toBeVisible();
});

test('scan by short code: ✅ then "already redeemed"; billing shows 1 billable redemption', async ({ page }) => {
  await completeWizard(page, 'Scan Bakery');
  await simulateQuiet(page);
  await page.getByTestId('edit').first().click();
  await page.getByRole('dialog').locator('#edit-pct').fill('10');
  await page.getByTestId('edit-approve').click();
  await expect(page.getByText('Offer published')).toBeVisible();

  const claim = devClaim(await shopIdOf(page));
  await page.goto('/scan');
  await expect(page.getByTestId('short-code-input')).toBeVisible(); // always visible, even before the camera starts
  await page.getByTestId('short-code-input').fill(claim.short_code.toLowerCase());
  await page.getByTestId('redeem-code').click();
  const result = page.getByTestId('scan-result');
  await expect(result).toHaveAttribute('data-result', 'ok');
  await expect(result).toContainText('Apply 10%');
  await page.getByTestId('scan-next').click();

  await page.getByTestId('short-code-input').fill(claim.short_code);
  await page.getByTestId('redeem-code').click();
  await expect(page.getByTestId('scan-result')).toHaveAttribute('data-result', 'already_redeemed');
  await expect(page.getByTestId('scan-result')).toContainText('Already redeemed');
  await page.getByTestId('scan-next').click();

  await page.getByTestId('short-code-input').fill('ZZZZZZ');
  await page.getByTestId('redeem-code').click();
  await expect(page.getByTestId('scan-result')).toHaveAttribute('data-result', 'invalid');
  await page.keyboard.press('Escape');

  await page.goto('/billing');
  await expect(page.getByTestId('billable-number')).toHaveText('1');
  await page.goto('/dashboard');
  await expect(page.getByTestId('tile-redemptions')).toContainText('1');
  await expect(page.getByTestId('offer-redeemed').first()).toContainText('1 of');
});

test('scan page works without a camera (no permission needed for the short-code box)', async ({ page, context }) => {
  await completeWizard(page, 'NoCam Bakery');
  await page.goto('/scan');
  await expect(page.getByTestId('start-camera')).toBeVisible();
  await expect(page.getByTestId('short-code-input')).toBeEnabled();
  await context.clearPermissions();
});

test('MCP approval: the assistant asks, a confirm card appears, and only the click publishes', async ({ page }) => {
  await completeWizard(page, 'Claude Bakery');
  await simulateQuiet(page);
  const proposalId = await page.getByTestId('proposal-card').first().getAttribute('data-proposal-id');

  // create a token in Settings -> "Connect your AI assistant"
  await page.goto('/settings');
  await page.getByRole('tab', { name: 'AI assistant' }).click();
  await page.getByTestId('create-token').click();
  const token = (await page.getByTestId('token-value').textContent())!.trim();
  expect(token).toMatch(/^snpat_/);
  await expect(page.getByTestId('mcp-config')).toContainText('"type": "http"');
  await expect(page.getByTestId('mcp-config')).toContainText('/mcp');

  // the assistant (here: a JSON-RPC call straight to the MCP server) asks to approve at 12%
  const mcp = await page.request.post('http://localhost:8001/mcp', {
    headers: { Authorization: `Bearer ${token}`, Accept: 'application/json, text/event-stream', 'Content-Type': 'application/json' },
    data: { jsonrpc: '2.0', id: 1, method: 'tools/call', params: { name: 'approve_proposal', arguments: { proposal_id: proposalId, final_pct: 12 } } },
  }).catch(() => null);
  test.skip(!mcp, 'MCP server is not running on :8001');
  expect(JSON.stringify(await mcp!.json())).toContain('awaiting_confirmation');

  await page.goto('/dashboard');
  const card = page.getByTestId('confirmation-card');
  await expect(card).toBeVisible();
  await expect(card).toContainText('12%');
  await expect(page.getByTestId('offer-card')).toHaveCount(0); // nothing is live yet
  await page.getByTestId('confirm-publish').click();
  await expect(page.getByText('Confirmed. The offer is live.')).toBeVisible();
  await page.goto('/audit');
  await expect(page.getByTestId('audit-table')).toContainText('AI assistant, confirmed by you');
});

test('Urdu switches the page to right-to-left', async ({ page }) => {
  await page.goto('/');
  await page.getByTestId('language-switcher').selectOption('ur');
  await expect(page.locator('html')).toHaveAttribute('dir', 'rtl');
  await expect(page.locator('html')).toHaveAttribute('lang', 'ur');
  await expect(page.getByTestId('demo-login')).toContainText('جج');
  await page.getByTestId('language-switcher').selectOption('en');
  await expect(page.locator('html')).toHaveAttribute('dir', 'ltr');
});

test('accessibility: no serious axe violations on the main pages (light and dark)', async ({ page }) => {
  await completeWizard(page, 'Axe Bakery');
  await simulateQuiet(page);
  const found: string[] = [];
  const scan = async (label: string) => {
    const res = await new AxeBuilder({ page }).withTags(['wcag2a', 'wcag2aa', 'wcag21aa', 'wcag22aa']).exclude('.leaflet-container').analyze();
    for (const v of res.violations.filter((x) => x.impact === 'serious' || x.impact === 'critical')) {
      found.push(`${label}: ${v.id} ${v.nodes.map((n) => n.target.join(' ')).slice(0, 3).join(' | ')}`);
    }
  };
  for (const url of ['/dashboard', '/offers', '/scan', '/items', '/guardrails', '/insights', '/agent-trace', '/audit', '/billing', '/settings']) {
    await page.goto(url);
    await page.waitForLoadState('load');
    await page.waitForTimeout(1200); // the live stream keeps the network busy, so networkidle never happens
    await scan(url);
  }
  await page.goto('/dashboard');
  await page.emulateMedia({ colorScheme: 'dark' });
  await page.evaluate(() => document.documentElement.classList.add('dark'));
  await scan('dark /dashboard');
  expect(found).toEqual([]);
});
