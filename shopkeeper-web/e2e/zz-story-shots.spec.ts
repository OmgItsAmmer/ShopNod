import { expect, test } from '@playwright/test';
test('story screenshots', async ({ browser }) => {
  test.setTimeout(170_000);
  const ctx = await browser.newContext({ viewport: { width: 1440, height: 1000 } });
  const page = await ctx.newPage();
  page.on('pageerror', (e) => console.log('PAGEERROR', e.message.slice(0, 300)));
  page.on('response', async (r) => { if (r.url().includes('/api/') && r.status() >= 400) console.log('HTTP', r.status(), r.url().slice(22, 110), (await r.text().catch(() => '')).slice(0, 160)); });
  await page.goto('/');
  await page.getByTestId('watch-story').click();
  await expect(page.getByTestId('story')).toBeVisible();
  const shots = [[2500,'a-intro'],[9000,'b-quiet'],[16000,'c-ai'],[24000,'d-guardrails'],[29500,'e-approve'],[37000,'f-match'],[45000,'g-offer'],[51500,'h-scan'],[57500,'i-redeemed'],[72000,'j-impact']] as const;
  const t0 = Date.now();
  for (const [at, name] of shots) {
    const wait = at - (Date.now() - t0);
    if (wait > 0) await page.waitForTimeout(wait);
    await page.screenshot({ path: 'C:/Users/ammer/AppData/Local/Temp/claude/c--Programming-Projects-10-Hackethon-shopnod/e5d50b87-5f2b-49aa-849f-ef184a3b88ed/scratchpad/story-' + name + '.png' });
    console.log('SHOT', name, await page.getByTestId('story-log').innerText().catch(() => '-'));
  }
  console.log('MODE', await page.getByTestId('story-mode').innerText());
  await expect(page.getByTestId('story-end')).toBeVisible({ timeout: 30_000 });
  await page.screenshot({ path: 'C:/Users/ammer/AppData/Local/Temp/claude/c--Programming-Projects-10-Hackethon-shopnod/e5d50b87-5f2b-49aa-849f-ef184a3b88ed/scratchpad/story-k-end.png' });
});
