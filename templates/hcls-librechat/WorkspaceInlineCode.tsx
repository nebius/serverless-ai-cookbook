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

export default function WorkspaceInlineCode({ children, className, onDoubleClick }: {
  children: React.ReactNode;
  className?: string;
  onDoubleClick?: React.MouseEventHandler;
}) {
  const href = workspaceCodeHref(children);
  const code = <code onDoubleClick={onDoubleClick} className={className}>{children}</code>;
  return href ? <a href={href} target="_blank" rel="noopener noreferrer">{code}</a> : code;
}
