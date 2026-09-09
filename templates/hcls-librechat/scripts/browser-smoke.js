// Run against an already logged-in, isolated test workspace:
// playwright-cli -s=<session> run-code --filename templates/hcls-librechat/scripts/browser-smoke.js
// Does not save credentials or send a chat/compute request. It prepares drafts.
async (page) => {
  const check = (condition, message) => { if (!condition) throw new Error(message); };
  const requests = [];
  const collect = (request) => {
    if (request.method() === 'POST' && /\/api\/(agents|ask)/.test(request.url())) requests.push(request.url());
  };
  page.on('request', collect);
  try {
    await page.getByRole('link', { name: 'New chat', exact: true }).click();
    await page.setViewportSize({ width: 1440, height: 1000 });
    const select = async (group, label) => {
      await page.getByTestId('model-selector-button').click();
      check((await page.getByRole('option').allTextContents()).join('|') === 'Nebius Token Factory|OpenAI|Claude', 'Unexpected raw endpoint/tutorial group');
      await page.getByRole('option', { name: group, exact: true }).click();
      await page.getByRole('menuitem').filter({ hasText: label }).click();
    };
    await select('Nebius Token Factory', 'Qwen 3 30B');
    const chosenModel = await page.getByTestId('model-selector-button').innerText();
    const prompts = [];
    for (const card of await page.locator('[data-workflow]').all()) {
      await card.click();
      check(await card.getAttribute('aria-pressed') === 'true', 'Missing workflow selection feedback');
      check(await page.getByTestId('model-selector-button').innerText() === chosenModel, 'Workflow changed LLM');
      prompts.push(await page.getByRole('textbox', { name: 'Message input' }).inputValue());
      await page.getByRole('button', { name: 'Send message', exact: true }).click({ trial: true });
    }
    check(prompts.length === 6 && new Set(prompts).size === 6, 'Expected six distinct workflow prompts');
    check(requests.length === 0, 'Workflow sent a chat request');
    await page.getByRole('button', { name: 'Clear', exact: true }).click();
    check(await page.getByRole('textbox', { name: 'Message input' }).inputValue() === '', 'Clear did not clear draft');
    await page.screenshot({ path: 'output/playwright/after-landing-desktop.png' });
    for (const [group, label] of [['OpenAI', 'GPT-5.6 Luna'], ['Claude', 'Claude Sonnet 5']]) {
      await select(group, label);
      // This acceptance fixture intentionally has no OpenAI/Claude keys.
      await page.getByRole('status').filter({ hasText: 'Connect your provider key' }).waitFor();
      check(await page.getByRole('textbox', { name: 'Message input' }).isDisabled(), 'Missing key did not block send');
      await page.getByRole('button', { name: 'Provider key', exact: true }).click();
      const dialog = page.getByRole('dialog');
      check(!(await dialog.innerText()).includes('Current key: never expires'), 'Missing key displayed as configured');
      await page.getByRole('button', { name: 'Close', exact: true }).click();
    }
    await select('Nebius Token Factory', 'Qwen 3 30B');
    await page.setViewportSize({ width: 390, height: 844 });
    check(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth), 'Mobile horizontal overflow');
    await page.getByTestId('model-selector-button').click();
    await page.screenshot({ path: 'output/playwright/after-mobile-selector.png' });
    await page.keyboard.press('Escape');
    await page.locator('[data-workflow="literature"]').click();
    check((await page.getByRole('textbox', { name: 'Message input' }).inputValue()).includes('scientific question'), 'Mobile workflow is inaccessible');
    await page.getByRole('button', { name: 'Send message', exact: true }).click({ trial: true });
    const sendBox = await page.getByRole('button', { name: 'Send message', exact: true }).boundingBox();
    check(sendBox && sendBox.y >= 0 && sendBox.y + sendBox.height <= 844, 'Mobile draft hides Send below the viewport');
    await page.screenshot({ path: 'output/playwright/after-mobile.png' });
    check(requests.length === 0, 'Setup unexpectedly sent a chat request');
    return { workflows: 6, preservedModel: chosenModel, providerKeyDialogs: 2, computeRequests: requests.length, mobile: 'pass' };
  } finally {
    page.off('request', collect);
  }
}
