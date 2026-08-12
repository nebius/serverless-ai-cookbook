import { copyFile, cp, mkdir, readFile, writeFile } from "node:fs/promises";
import path from "node:path";
import { pathToFileURL } from "node:url";

export const CONTROL_UI_BOOTSTRAP_NAME = "bionemo-default-session.js";
const MODULE_SCRIPT_MARKER = '    <script type="module"';
const BOOTSTRAP_SCRIPT_TAG = `    <script src="./${CONTROL_UI_BOOTSTRAP_NAME}"></script>\n`;

export async function prepareControlUi({ sourceRoot, targetRoot, bootstrapPath }) {
  if (!sourceRoot || !targetRoot || !bootstrapPath) {
    throw new Error("sourceRoot, targetRoot, and bootstrapPath are required");
  }

  await mkdir(path.dirname(targetRoot), { recursive: true });
  await cp(sourceRoot, targetRoot, { recursive: true, force: true });
  await copyFile(bootstrapPath, path.join(targetRoot, CONTROL_UI_BOOTSTRAP_NAME));

  const indexPath = path.join(targetRoot, "index.html");
  const original = await readFile(indexPath, "utf8");
  if (original.includes(BOOTSTRAP_SCRIPT_TAG.trim())) return;

  const markerIndex = original.indexOf(MODULE_SCRIPT_MARKER);
  if (markerIndex < 0 || original.indexOf(MODULE_SCRIPT_MARKER, markerIndex + 1) >= 0) {
    throw new Error("Expected exactly one OpenClaw Control UI module script marker");
  }

  const prepared = `${original.slice(0, markerIndex)}${BOOTSTRAP_SCRIPT_TAG}${original.slice(markerIndex)}`;
  await writeFile(indexPath, prepared, "utf8");
}

async function main() {
  const [sourceRoot, targetRoot, bootstrapPath] = process.argv.slice(2);
  await prepareControlUi({ sourceRoot, targetRoot, bootstrapPath });
}

if (process.argv[1] && import.meta.url === pathToFileURL(process.argv[1]).href) {
  main().catch((error) => {
    process.stderr.write(`Control UI preparation failed: ${error.message}\n`);
    process.exitCode = 1;
  });
}
