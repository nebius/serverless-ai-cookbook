import { readFile, writeFile } from 'node:fs/promises';
const path = '/app/client/src/components/Chat/ChatView.tsx';
let source = await readFile(path, 'utf8');
for (const [before, after] of [
  ["import ConversationStarters from './Input/ConversationStarters';", ''],
  ['{isLandingPage && <ConversationStarters />}', ''],
  ["'flex-1 items-center justify-end sm:justify-center'", "'flex-1 min-h-0 overflow-y-auto items-center pt-4 pb-4 sm:pt-10'"],
]) {
  if (!source.includes(before)) throw new Error(`Unsupported ChatView: missing ${before}`);
  source = source.replace(before, after);
}
await writeFile(path, source);

// Keep provider setup accessible even when the menu only shows curated model specs.
const selectorPath = '/app/client/src/components/Chat/Menus/Endpoints/ModelSelector.tsx';
let selector = await readFile(selectorPath, 'utf8');
for (const [before, after] of [
  ["import { getConfigDefaults } from 'librechat-data-provider';", "import { EModelEndpoint, getConfigDefaults } from 'librechat-data-provider';"],
  ['    keyDialogEndpoint,\n', '    keyDialogEndpoint,\n    endpointRequiresUserKey,\n    handleOpenKeyDialog,\n'],
  ['className="relative flex min-w-0 max-w-[60vw] flex-col items-center gap-2 sm:max-w-xs"', 'className="relative flex min-w-0 max-w-full flex-wrap items-center gap-2"'],
  ['      <Menu\n', '      <span className="hidden text-xs text-text-secondary sm:inline">Chat model</span>\n      <Menu\n'],
  ['className="my-1 flex h-9 max-w-full', 'className="my-1 flex h-9 !w-auto max-w-[50vw]'],
  ['      <DialogManager\n', `      {selectedValues.endpoint && endpointRequiresUserKey(selectedValues.endpoint) && (
        <button type="button" id={\`endpoint-\${selectedValues.endpoint}-settings\`}
          className="rounded-lg border border-border-light px-2 py-1.5 text-xs text-text-secondary hover:bg-surface-hover focus-visible:ring-2 focus-visible:ring-ring-primary"
          onClick={(event) => handleOpenKeyDialog(selectedValues.endpoint as EModelEndpoint, event)}>
          Provider key
        </button>
      )}
      <DialogManager
`],
]) {
  if (!selector.includes(before)) throw new Error(`Unsupported ModelSelector: missing ${before}`);
  selector = selector.replace(before, after);
}
await writeFile(selectorPath, selector);

// Caller-provided enabled=true must not re-enable polling for a not-yet-created chat.
const queriesPath = '/app/client/src/data-provider/Subagents/queries.ts';
let queries = await readFile(queriesPath, 'utf8');
const oldQuery = '      refetchIntervalInBackground: false,\n      ...config,\n';
if (!queries.includes(oldQuery)) throw new Error('Unsupported subagent query options');
queries = queries.replace(oldQuery, `${oldQuery}      enabled: config?.enabled !== false && parentConversationId !== '' &&
        parentConversationId !== Constants.NEW_CONVO && parentConversationId !== Constants.PENDING_CONVO,
`);
// Remove the earlier enabled property so TypeScript does not see a duplicate.
queries = queries.replace(`      enabled:
        parentConversationId !== '' &&
        parentConversationId !== Constants.NEW_CONVO &&
        parentConversationId !== Constants.PENDING_CONVO,
`, '');
await writeFile(queriesPath, queries);

// The key API returns null for a missing key, and "never" for a saved key
// without expiry. Do not confuse those two states in the picker/composer.
const keyPath = '/app/client/src/hooks/Input/useUserKey.ts';
let keySource = await readFile(keyPath, 'utf8');
const oldExpiry = "    if (checkUserKey.data) {\n      return checkUserKey.data.expiresAt || 'never';\n    }";
if (!keySource.includes(oldExpiry)) throw new Error('Unsupported user key hook');
keySource = keySource.replace(oldExpiry, "    return checkUserKey.data?.expiresAt || undefined;");
keySource = keySource.replace('    if (!expiresAt) {\n      return true;\n    }', '    if (!expiresAt) {\n      return false;\n    }');
await writeFile(keyPath, keySource);

const requiredKeyPath = '/app/client/src/hooks/Input/useRequiresKey.ts';
let requiredKey = await readFile(requiredKeyPath, 'utf8');
const oldRequired = '  const requiresKey = !expiryTime && userProvidesKey;';
if (!requiredKey.includes(oldRequired)) throw new Error('Unsupported requires-key hook');
requiredKey = requiredKey.replace(oldRequired, `  const expired = expiryTime && expiryTime !== 'never' && new Date(expiryTime) <= new Date();
  const requiresKey = (!expiryTime || expired) && userProvidesKey;`);
await writeFile(requiredKeyPath, requiredKey);

// Restore embedded-viewer sizing and fullscreen delegation without relaxing
// the upstream HTML-only renderer or its sandbox.
const resourcePath = '/app/client/src/components/MCPUIResource/MCPUIResource.tsx';
let resource = await readFile(resourcePath, 'utf8');
const resizeOption = 'autoResizeIframe: { width: true, height: true },';
if (!resource.includes(resizeOption)) throw new Error('Unsupported MCP UI resource renderer');
resource = resource.replace(resizeOption, `autoResizeIframe: { width: false, height: true },
            iframeProps: {
              allow: 'fullscreen', allowFullScreen: true,
              style: { display: 'block', width: '100%', border: 0 },
            } as React.IframeHTMLAttributes<HTMLIFrameElement>,`);
await writeFile(resourcePath, resource);
