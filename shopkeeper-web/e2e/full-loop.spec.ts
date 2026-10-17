/**
 * Plan 3 Phase 3: the whole product in one test ("works end to end"), with two browsers at once on ONE website:
 * the shopkeeper (dashboard) and the shopper (`/shopper`). Each browser context has its own cookies and storage,
 * like two different people.
 */
import { type Browser, type Page, expect, test } from '@playwright/test';

test.describe.configure({ mode: 'serial' });

async function shopkeeperWizard(page: Page, name: string): Promise<string> {
  await page.goto('/');
  await page.getByTestId('demo-login').first().click();
  await expect(page).toHaveURL(/onboarding\/shop/);
  await page.getByLabel('Shop name').fill(name);
  await page.getByRole('radio', { name: /Bakery/ }).check({ force: true });
  await page.getByRole('button', { name: 'Continue' }).click();
  await page.getByTestId('use-demo-market').click();
  await expect(page).toHaveURL(/onboarding\/review/);
  await page.getByTestId('finish-setup').click();
  await expect(page).toHaveURL(/dashboard/);
  await expect(page.getByTestId('im-quiet')).toBeVisible();
  return (await (await page.request.get('/api/v1/auth/me')).json()).shop.id;
}

/** A second person on a phone-sized screen, opening the link from the dashboard's QR code. */
async function openShopper(browser: Browser, url: string): Promise<Page> {
  const ctx = await browser.newContext({ viewport: { width: 420, height: 900 } });
  const page = await ctx.newPage();
  await page.goto(url);
  return page;
}

async function shopperOnboard(page: Page) {
  await page.getByTestId('shopper-age').click(); // 18+
  await expect(page.getByRole('switch', { name: 'Shopping list' })).toBeChecked(); // consent: all purposes on
  await page.getByTestId('shopper-consent-next').click();
  await page.getByLabel('Shopping list (optional)').fill('bread, cake, croissant');
  await page.getByTestId('shopper-interests-next').click();
  // From the shop's QR code: straight into the Demo Market, no location prompt (S9).
  await expect(page.getByTestId('shopper-use-location')).toHaveCount(0);
  await page.getByTestId('shopper-join-demo').click();
  await expect(page.getByTestId('shopper-feed')).toBeVisible();
}

async function scanCode(page: Page, code: string) {
  await page.goto('/scan');
  await page.getByTestId('short-code-input').fill(code);
  await page.getByTestId('redeem-code').click();
}

test('full loop: quiet hour → proposal → approve → shopper gets it → claim → scan → redeemed → billed', async ({ page: shop, browser }) => {
  test.setTimeout(180_000);

  // 1. Shopkeeper: demo login → wizard (Bakery, Demo Market) → dashboard
  const shopName = `Loop Bakery ${Date.now() % 100000}`;
  const shopId = await shopkeeperWizard(shop, shopName);
  const qrHref = await shop.getByTestId('shopper-url').getAttribute('href');
  expect(qrHref).toContain(`/shopper/?market=demo&shop=${shopId}`); // same website
  expect(new URL(qrHref!).origin).toBe(new URL(shop.url()).origin);

  // 2. Shopper: opens the dashboard's link → 18+ → consent (all on) → interests + list → Demo Market
  const shopper = await openShopper(browser, qrHref!);
  await shopperOnboard(shopper);
  await expect(shopper.getByTestId('shopper-feed-empty')).toBeVisible();

  // 3. Shopkeeper: "Simulate a quiet hour" → a proposal card (≤ 10 s) → edit to 10% → approve
  await shop.getByTestId('simulate-quiet').click();
  await expect(shop.getByTestId('proposal-card').first()).toBeVisible({ timeout: 10_000 });
  await shop.getByTestId('edit').first().click();
  await shop.getByRole('dialog').locator('#edit-pct').fill('10');
  await shop.getByTestId('edit-approve').click();
  await expect(shop.getByText('Offer published')).toBeVisible();

  // 4. Shopper: the offer appears (≤ 15 s) with "why you see this" → Get offer → QR
  const card = shopper.locator(`[data-testid="shopper-offer"][data-shop-name="${shopName}"]`);
  await expect(card).toBeVisible({ timeout: 15_000 });
  await expect(card).toContainText('10');
  await expect(card.getByTestId('shopper-why')).toContainText(/On your list|You like Bakery|Near you/);
  await expect(card).toContainText('Everyone sees the same price');
  await card.getByRole('link').first().click();
  await shopper.getByTestId('shopper-get-offer').click();
  await expect(shopper.getByTestId('shopper-claim')).toHaveAttribute('data-status', 'issued');
  const code = (await shopper.getByTestId('shopper-short-code').textContent())!.trim();
  expect(code).toMatch(/^[A-Z2-9]{6}$/);

  // 5. Shopkeeper: scan page → the code → "✅ apply 10%"
  await scanCode(shop, code);
  const result = shop.getByTestId('scan-result');
  await expect(result).toHaveAttribute('data-result', 'ok');
  await expect(result).toContainText('Apply 10%');

  // 6. Shopper: the QR screen changes to "Redeemed" by itself and "You saved" goes up
  await expect(shopper.getByTestId('shopper-redeemed')).toBeVisible({ timeout: 10_000 });
  await expect(shopper.getByTestId('shopper-saved')).toContainText(/You saved .*[1-9]/);
  await shopper.getByTestId('shopper-tab-wallet').click();
  await expect(shopper.getByTestId('shopper-savings')).toContainText('1 redemption');

  // 7. Shopkeeper: billing shows 1 billable redemption, and the learning chart includes the decision
  await shop.goto('/billing');
  await expect(shop.getByTestId('billable-number')).toHaveText('1');
  await shop.goto('/insights');
  await expect(shop.getByTestId('learning-chart')).toBeVisible();
  await expect(shop.getByTestId('next-proposal')).toContainText('10%');

  // 8. Step 5 again → "already redeemed"
  await scanCode(shop, code);
  await expect(shop.getByTestId('scan-result')).toHaveAttribute('data-result', 'already_redeemed');

  // 9. AI-outage flag on → simulate quiet → the proposal says "rule-based"
  const offers = await (await shop.request.get('/api/v1/shop/offers?status=active')).json();
  for (const o of offers) {
    await shop.request.post(`/api/v1/shop/offers/${o.id}/end`, { headers: { 'Idempotency-Key': `e2e-end-${o.id}` } });
  }
  expect((await shop.request.post('/api/v1/admin/ai-outage', { data: { enabled: true } })).ok()).toBeTruthy();
  try {
    await shop.goto('/dashboard');
    await shop.getByTestId('simulate-quiet').click();
    const proposal = shop.getByTestId('proposal-card').first();
    await expect(proposal).toBeVisible({ timeout: 10_000 });
    await expect(proposal.getByText('Rule-based')).toBeVisible();
  } finally {
    await shop.request.post('/api/v1/admin/ai-outage', { data: { enabled: false } });
  }

  // The shopper can take their data with them, then delete it (privacy rights)
  await shopper.getByTestId('shopper-tab-settings').click();
  shopper.once('dialog', (d) => void d.accept());
  await shopper.getByTestId('shopper-delete').click();
  await expect(shopper.getByTestId('shopper-onboarding')).toBeVisible();
  await shopper.context().close();
});
