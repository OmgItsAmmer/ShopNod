/**
 * Auto-predict, seen from the shopper's seat: a shopper who typed NOTHING still gets a feed that fits the moment,
 * the reasons change when the weather changes, and what they do is learned straight away (and can be forgotten).
 */
import { type Page, expect, test } from '@playwright/test';

test.describe.configure({ mode: 'serial' });

async function shopkeeperWithOffer(page: Page, name: string): Promise<string> {
  await page.goto('/');
  await page.getByTestId('demo-login').first().click();
  await page.getByLabel('Shop name').fill(name);
  await page.getByRole('radio', { name: /Bakery/ }).check({ force: true });
  await page.getByRole('button', { name: 'Continue' }).click();
  await page.getByTestId('use-demo-market').click();
  await page.getByTestId('finish-setup').click();
  await expect(page.getByTestId('im-quiet')).toBeVisible();
  const shopId = (await (await page.request.get('/api/v1/auth/me')).json()).shop.id;
  await page.getByTestId('simulate-quiet').click();
  await expect(page.getByTestId('proposal-card').first()).toBeVisible({ timeout: 10_000 });
  await page.getByTestId('edit').first().click();
  await page.getByRole('dialog').locator('#edit-pct').fill('10');
  await page.getByTestId('edit-approve').click();
  await expect(page.getByText('Offer published')).toBeVisible();
  return shopId;
}

test('a shopper who typed nothing: the feed follows the moment, learns from taps, and can forget', async ({ page: shop, browser }) => {
  test.setTimeout(150_000);
  const shopName = `Predict Bakery ${Date.now() % 100000}`;
  const shopId = await shopkeeperWithOffer(shop, shopName);

  // The shopper skips everything: no categories, no shopping list.
  const ctx = await browser.newContext({ viewport: { width: 420, height: 900 } });
  const me = await ctx.newPage();
  await me.goto(`/shopper/?market=demo&shop=${shopId}`);
  await me.getByTestId('shopper-age').click();
  await me.getByTestId('shopper-consent-next').click();
  for (const c of ['Bakery', 'Groceries']) await me.getByRole('checkbox', { name: c }).click();
  await me.getByLabel('Shopping list (optional)').fill('');
  await me.getByTestId('shopper-interests-next').click();
  await me.getByTestId('shopper-join-demo').click();

  const card = me.locator(`[data-testid="shopper-offer"][data-shop-name="${shopName}"]`);
  await expect(card).toBeVisible({ timeout: 15_000 });
  await expect(me.getByTestId('shopper-context')).toBeVisible();

  // Demo switch: pretend it is a rainy evening. The reason is about the moment, not about anything they typed.
  await me.getByTestId('shopper-context').getByText('Pretend it’s… (demo)').click();
  await me.getByTestId('pretend-evening').click();
  await me.getByTestId('pretend-rain').click();
  await expect(me.getByTestId('shopper-context-summary')).toContainText('Rainy evening');
  await expect(card.getByTestId('shopper-reason')).toHaveText('Rainy day: warm treats');

  // A hot day gives a different reason for the same offer.
  await me.getByTestId('pretend-hot').click();
  await expect(me.getByTestId('shopper-context-summary')).toContainText('Hot evening');
  await expect(card.getByTestId('shopper-reason')).not.toHaveText('Rainy day: warm treats');

  // Back to the real moment.
  await me.getByRole('button', { name: 'Use the real time and weather' }).click();
  await expect(me.getByTestId('shopper-context-summary')).not.toContainText('Hot evening');

  // Opening the offer and a thumbs-up teach it something straight away.
  await card.getByRole('link').first().click();
  await expect(me.getByTestId('shopper-reasons')).toBeVisible();
  await me.getByRole('button', { name: '👍' }).click();
  await me.getByTestId('shopper-tab-settings').click();
  await expect(me.getByTestId('shopper-learned')).toBeVisible();
  await expect(me.getByTestId('shopper-learned')).toContainText('Bakery');

  // ...and it can all be forgotten.
  await me.getByRole('button', { name: 'Forget what we learned' }).click();
  await expect(me.getByTestId('shopper-learned')).toHaveCount(0);
  await ctx.close();
});
