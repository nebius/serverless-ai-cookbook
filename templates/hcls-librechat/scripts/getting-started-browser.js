// Run against the actual signed-in candidate. Does not submit chat or inference.
// playwright-cli -s=<session> run-code --filename <this file>
async (page) => {
  const assert = (condition, message) => { if (!condition) throw new Error(message); };
  const origin = new URL(page.url()).origin;
  await page.context().grantPermissions(['clipboard-read', 'clipboard-write']);
  const submitted = [];
  const watch = request => {
    if (request.method() === 'POST' && /\/api\/(ask|agents|scientific-demos\/(clinical|workshop\/runs))/.test(request.url())) submitted.push(request.url());
  };
  page.on('request', watch);
  try {
    await page.setViewportSize({width: 1440, height: 1000});
    await page.goto(`${origin}/c/new`);
    await page.getByRole('heading', {name: 'New here? Start with your sample data.'}).waitFor();
    const selector = await page.getByTestId('model-selector-button').innerText();
    await page.locator('[data-starter="tour"]').click();
    const tour = await page.getByRole('textbox', {name: 'Message input'}).inputValue();
    assert(tour.includes('Do not run inference yet') && tour.includes('/workspace/examples/v1/README.md'), 'Tour did not prepare the real no-inference prompt');
    assert(await page.getByTestId('model-selector-button').innerText() === selector, 'Tour changed the selected agent/model');
    await page.getByRole('link', {name: 'Getting started & example prompts'}).click();
    await page.getByRole('heading', {name: 'Your first scientific run'}).waitFor();
    const examples = page.locator('[data-example]');
    assert(await examples.count() === 6, 'Expected six concrete examples');
    const copied = [];
    for (const card of await examples.all()) {
      assert((await card.innerText()).includes('Input:') && (await card.innerText()).includes('You get:'), 'Example hides input/output expectations');
      await card.getByRole('button').click();
      const value = await page.evaluate(() => navigator.clipboard.readText());
      assert(value.length > 150 && !value.includes('LongevityHack2026'), 'Copied example is empty or event-specific');
      copied.push(value);
    }
    assert(new Set(copied).size === 6, 'Example prompts are duplicated');
    assert(!/Stockholm|LongevityHack|Sword AI Summit|3 October 2026/.test(await page.locator('body').innerText()), 'Event branding remains');
    await page.screenshot({path: 'output/playwright/getting-started-desktop.png', fullPage: true});
    await page.getByRole('link', {name: 'Open sample files'}).click();
    assert(new URL(page.url()).searchParams.get('path') === 'examples/v1', 'Sample link lost the bucket prefix');
    await page.getByRole('button', {name: 'Getting started', exact: true}).click();
    await page.reload();
    await page.getByRole('heading', {name: 'Your first scientific run'}).waitFor();
    await page.setViewportSize({width: 390, height: 844});
    assert(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth), 'Guide overflows on mobile');
    await page.locator('[data-example="tour"]').getByRole('button').click();
    assert((await page.evaluate(() => navigator.clipboard.readText())) === copied[0], 'Mobile prompt copy differs');
    await page.screenshot({path: 'output/playwright/getting-started-mobile.png', fullPage: true});
    await page.getByRole('link', {name: 'Start a chat', exact: true}).click();
    await page.locator('[data-starter="tour"]').waitFor();
    assert(submitted.length === 0, 'Onboarding submitted compute or chat');
    return {examples: copied.length, copied: copied.length, modelPreserved: true, samplePrefix: 'examples/v1', reload: true, mobile: true, submissions: submitted.length};
  } finally { page.off('request', watch); }
}
