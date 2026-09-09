import React from 'react';
import { useOptionalMessagesConversation, useOptionalMessagesOperations } from '~/Providers';
import { useConversationUIResources } from '~/hooks/Messages/useConversationUIResources';
import UIResourceRenderer, { isSupportedUIResource } from './Renderer';
import { handleUIAction } from '~/utils';
import { useLocalize } from '~/hooks';

interface MCPUIResourceProps {
  node: {
    properties: {
      resourceId: string;
    };
  };
}

/** Render interactive workbench resources at the full available page width. */
export function MCPUIResource(props: MCPUIResourceProps) {
  const { resourceId } = props.node.properties;
  const localize = useLocalize();
  const { ask } = useOptionalMessagesOperations();
  const { conversationId } = useOptionalMessagesConversation();
  const resourceContainerRef = React.useRef<HTMLSpanElement>(null);
  const [availableWidth, setAvailableWidth] = React.useState<number>();
  const conversationResourceMap = useConversationUIResources(conversationId ?? undefined);
  const uiResource = conversationResourceMap.get(resourceId ?? '');

  React.useLayoutEffect(() => {
    const container = resourceContainerRef.current;
    if (!container) return;

    let frame: number | undefined;
    const updateWidth = () => {
      frame = undefined;
      // This resource is rendered inside LibreChat's centered message column.
      // Its left edge can move when the sidebar changes, so measure that edge
      // and fill only the visible application area to its right.
      const left = Math.max(0, container.getBoundingClientRect().left);
      setAvailableWidth(Math.max(0, document.documentElement.clientWidth - left));
    };
    const scheduleWidthUpdate = () => {
      if (frame === undefined) frame = window.requestAnimationFrame(updateWidth);
    };
    const observer = new ResizeObserver(scheduleWidthUpdate);
    observer.observe(document.documentElement);
    // The message body changes size when the sidebar opens or closes, while
    // the application <main> is the element that actually receives that
    // layout change. Observe both so the viewer remains full-width in either
    // state.
    const layoutParents = [container.parentElement, container.closest('main')];
    for (const parent of new Set(layoutParents)) {
      if (parent) observer.observe(parent);
    }
    window.addEventListener('resize', scheduleWidthUpdate);
    scheduleWidthUpdate();
    return () => {
      if (frame !== undefined) window.cancelAnimationFrame(frame);
      observer.disconnect();
      window.removeEventListener('resize', scheduleWidthUpdate);
    };
  }, []);

  if (!uiResource) {
    return (
      <span className="inline-flex items-center rounded bg-surface-tertiary px-2 py-1 text-xs font-medium text-text-secondary">
        {localize('com_ui_ui_resource_not_found', { 0: resourceId ?? '' })}
      </span>
    );
  }
  if (!isSupportedUIResource(uiResource)) return null;

  try {
    return (
      <span
        ref={resourceContainerRef}
        className="block max-w-none px-4 align-middle"
        style={{ width: availableWidth === undefined ? '100%' : `${availableWidth}px` }}
      >
        <UIResourceRenderer
          resource={uiResource}
          onUIAction={async (result) => handleUIAction(result, ask)}
          htmlProps={{
            // Width is owned by the measured visible application area. Having
            // the iframe report a measured width creates a feedback loop.
            autoResizeIframe: { width: false, height: true },
            iframeProps: {
              allow: 'fullscreen',
              allowFullScreen: true,
              style: { display: 'block', width: '100%', maxWidth: 'none', border: 0 },
            },
          }}
        />
      </span>
    );
  } catch (error) {
    console.error('Error rendering UI resource:', error);
    return (
      <span className="inline-flex items-center rounded bg-status-error-subtle px-2 py-1 text-xs font-medium text-status-error">
        {localize('com_ui_ui_resource_error', { 0: uiResource.name || resourceId })}
      </span>
    );
  }
}
