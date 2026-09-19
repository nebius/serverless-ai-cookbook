import React from 'react';

/** Recognize only the existing authenticated workspace UI, not arbitrary URLs. */
export function workspaceCodeHref(children: unknown): string | undefined {
  const value = typeof children === 'string' ? children
    : Array.isArray(children) && children.every((part) => typeof part === 'string')
      ? children.join('') : undefined;
  if (!value?.startsWith('/demos?') || /[\s\\]/u.test(value)) return undefined;
  const url = new URL(value, 'https://workspace.invalid');
  if (url.pathname !== '/demos' || url.hash || url.searchParams.get('tab') !== 'workspace') return undefined;
  const permitted = ['tab', 'path', 'file'];
  if ([...url.searchParams.keys()].some((key) => !permitted.includes(key)) ||
      permitted.some((key) => url.searchParams.getAll(key).length !== 1)) return undefined;
  const folder = url.searchParams.get('path') ?? '';
  const file = url.searchParams.get('file') ?? '';
  const validPath = (path: string) => !/[\u0000-\u001f\u007f\\]/u.test(path) &&
    !path.split('/').some((part) => part === '.' || part === '..') &&
    (!path.startsWith('/') || path === '/workspace' || path.startsWith('/workspace/'));
  if (!file || !validPath(folder) || !validPath(file)) return undefined;
  return url.pathname + url.search;
}

/** Add navigation only to a block containing complete workspace URL lines. */
export function workspaceCodeLinks(children: unknown): Array<{ href: string; label: string }> {
  const text = typeof children === 'string' ? children
    : Array.isArray(children) && children.every((part) => typeof part === 'string')
      ? children.join('') : undefined;
  if (!text) return [];
  const lines = text.split(/\r?\n/u).filter((line) => line !== '');
  if (!lines.length) return [];
  const hrefs = lines.map(workspaceCodeHref);
  if (hrefs.some((href) => !href)) return [];
  return hrefs.map((href) => ({
    href: href!,
    label: new URL(href!, 'https://workspace.invalid').searchParams.get('file')!.split('/').pop()!,
  }));
}

/** Keep the original fenced renderer/copy text; add adjacent authenticated links. */
export function WorkspaceCodeBlockLinks({ codeChildren, children }: {
  codeChildren: React.ReactNode;
  children: React.ReactNode;
}) {
  const links = workspaceCodeLinks(codeChildren);
  if (!links.length) return <>{children}</>;
  return <>{children}<nav aria-label="Workspace files" className="my-2">
    <ul className="flex flex-wrap gap-x-4 gap-y-2">
      {links.map(({ href, label }, index) => <li key={`${index}:${href}`}>
        <a href={href} target="_blank" rel="noopener noreferrer" className="underline">
          {label}
        </a>
      </li>)}
    </ul>
  </nav></>;
}

export default function WorkspaceInlineCode({ children, className, onDoubleClick }: {
  children: React.ReactNode;
  className?: string;
  onDoubleClick?: React.MouseEventHandler;
}) {
  const href = workspaceCodeHref(children);
  const code = <code onDoubleClick={onDoubleClick} className={className}>{children}</code>;
  return href ? <a href={href} target="_blank" rel="noopener noreferrer">{code}</a> : code;
}
