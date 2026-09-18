// Run in a logged-in preview:
// playwright-cli -s=<session> run-code --filename templates/hcls-librechat/scripts/workspace-browser-acceptance.js
// Verifies that a browser upload can be read back byte-for-byte from the mounted workspace.
async (page) => {
  const content = 'scientific-ai-workbench-v2 acceptance 2026-09-18 r4\n';
  const objectPath = 'acceptance/workbench-v2-r4-acceptance.txt';
  await page.setViewportSize({ width: 1440, height: 1000 });
  const origin = await page.evaluate(() => location.origin);
  await page.goto(`${origin}/demos?tab=workspace`);
  await page.getByRole('button', { name: 'demo-assets/' }).waitFor({ timeout: 120_000 });
  await page.locator('input[type=file]').setInputFiles(
    '/home/tux/worktrees/scientific-ai-workbench-v2-20260918/templates/hcls-librechat/demos/workspace-acceptance.txt',
  );
  await page.getByRole('textbox', { name: 'Workspace object path' }).fill(objectPath);
  await page.getByRole('button', { name: 'Upload', exact: true }).waitFor({ state: 'visible' });
  if (await page.getByRole('button', { name: 'Upload', exact: true }).isDisabled()) {
    throw new Error('Workspace upload did not retain the selected browser file');
  }
  const [uploaded] = await Promise.all([
    page.waitForResponse((response) => response.request().method() === 'POST' && response.url().endsWith('/api/scientific-demos/workspace')),
    page.getByRole('button', { name: 'Upload', exact: true }).click(),
  ]);
  if (!uploaded.ok()) throw new Error(`Workspace upload failed with ${uploaded.status()}`);
  await page.getByRole('button', { name: 'acceptance/' }).click();
  const name = objectPath.split('/').at(-1);
  const [response, browserDownload] = await Promise.all([
    page.waitForResponse((item) => item.request().method() === 'GET' && item.url().includes('/api/scientific-demos/workspace/file?')),
    page.waitForEvent('download'),
    page.getByRole('button', { name, exact: true }).click(),
  ]);
  const downloaded = await response.text();
  if (!response.ok() || downloaded !== content || browserDownload.suggestedFilename() !== name) {
    throw new Error(`Workspace round trip failed: status=${response.status()} bytes=${downloaded.length}`);
  }
  return { objectPath, status: response.status(), bytes: downloaded.length, exact: true };
}
