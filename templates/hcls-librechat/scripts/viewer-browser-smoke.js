// Run against an existing chat containing a real visualize_structure result.
// Uses the browser CLI; never submits scientific compute.
async (page) => {
  const check = (value, message) => { if (!value) throw new Error(message); };
  let frame;
  for (const candidate of page.frames()) {
    if (await candidate.locator('#viewer-status').count()) frame = candidate;
  }
  check(frame, 'No in-chat structure viewer');
  await frame.locator('[data-viewer-ready="true"]').waitFor();
  const element = await frame.frameElement();
  await element.scrollIntoViewIfNeeded();
  check(await frame.locator('canvas').count() > 0, 'Missing WebGL canvas');
  const status = await frame.locator('#viewer-status').innerText();
  const firstView = await frame.evaluate(() => viewer.getView());
  await frame.getByRole('button', { name: 'Start rotation', exact: true }).click();
  await frame.waitForFunction((initial) => JSON.stringify(viewer.getView()) !== JSON.stringify(initial), firstView);
  check(await frame.locator('#spin').getAttribute('aria-pressed') === 'true', 'Spin control not active');
  await frame.locator('#spin').click();
  check(await frame.locator('#spin').getAttribute('aria-pressed') === 'false', 'Spin control did not stop');
  await frame.getByLabel('Molecular representation').selectOption('sticks');
  await frame.getByRole('button', { name: 'Reset view', exact: true }).click();
  const box = await frame.locator('canvas').first().boundingBox();
  check(box && box.width > 200 && box.height > 200, 'Viewer collapsed');
  const beforeDrag = await frame.evaluate(() => viewer.getView());
  // The sticky composer can cover the bottom of a tall in-chat canvas.
  // Drag the visible portion, not the composer above it.
  const dragY = Math.max(box.y + 25, Math.min(box.y + box.height / 2, page.viewportSize().height - 220));
  await page.mouse.move(box.x + box.width / 2, dragY);
  await page.mouse.down();
  await page.mouse.move(box.x + box.width / 2 + 70, dragY + 35, { steps: 8 });
  await page.mouse.up();
  check(JSON.stringify(await frame.evaluate(() => viewer.getView())) !== JSON.stringify(beforeDrag), 'Drag rotation did not change camera');
  await frame.getByRole('button', { name: 'Full screen', exact: true }).click();
  await frame.waitForFunction(() => Boolean(document.fullscreenElement));
  await frame.getByRole('button', { name: 'Exit full screen', exact: true }).waitFor();
  await frame.waitForFunction(() => {
    const panel = document.querySelector('.panel').getBoundingClientRect();
    const canvas = document.querySelector('canvas').getBoundingClientRect();
    return panel.width >= innerWidth - 2 && panel.height >= innerHeight - 2 && canvas.height > innerHeight * 0.65;
  });
  await page.screenshot({ path: 'output/playwright/structure-fullscreen.png' });
  await frame.getByRole('button', { name: 'Exit full screen', exact: true }).click();
  await frame.waitForFunction(() => !document.fullscreenElement);
  await page.screenshot({ path: 'output/playwright/structure-inline.png' });
  const structureOptions = await frame.getByLabel('Structure', { exact: true }).locator('option').allTextContents();
  if (structureOptions.length > 1) {
    // Exercise every returned structure/pose, including SDF molecule results.
    for (let i = 0; i < structureOptions.length; i++) {
      await frame.getByLabel('Structure', { exact: true }).selectOption(String(i));
      check(await frame.locator('.panel').getAttribute('data-viewer-ready') === 'true', 'Structure selection failed');
    }
  }
  await page.reload();
  const restored = page.frameLocator('iframe[allow="fullscreen"]').first();
  await restored.locator('[data-viewer-ready="true"]').waitFor();
  return { status, structures: structureOptions, spin: 'pass', drag: 'pass', fullscreen: 'pass', reload: 'pass' };
}
