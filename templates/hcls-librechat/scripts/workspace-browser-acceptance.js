// Run in a logged-in preview:
// playwright-cli -s=<session> run-code --filename templates/hcls-librechat/scripts/workspace-browser-acceptance.js
// Verifies that a browser upload can be read back byte-for-byte from the mounted workspace.
async (page) => {
  const content = 'scientific-ai-workbench-v2 acceptance 2026-09-18 r2\n';
  const objectPath = 'acceptance/workbench-v2-r2-acceptance.txt';
  const origin = await page.evaluate(() => location.origin);
  await page.goto(`${origin}/demos?tab=workspace`);
  await page.locator('input[type=file]').setInputFiles(
    'templates/hcls-librechat/demos/workspace-acceptance.txt',
  );
  await page.getByRole('textbox', { name: 'Workspace object path' }).fill(objectPath);
  await page.getByRole('button', { name: 'Upload', exact: true }).click();
  await page.waitForFunction(
    (name) => document.body.innerText.includes(name),
    'workbench-v2-r2-acceptance.txt',
    { timeout: 120_000 },
  );
  const response = await page.request.get(
    `/api/scientific-demos/workspace/file?path=${encodeURIComponent(objectPath)}`,
  );
  const downloaded = await response.text();
  if (!response.ok() || downloaded !== content) {
    throw new Error(`Workspace round trip failed: status=${response.status()} bytes=${downloaded.length}`);
  }
  return { objectPath, status: response.status(), bytes: downloaded.length, exact: true };
}
