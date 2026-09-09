import React, { useEffect, memo } from 'react';
import TagManager from 'react-gtm-module';
import ReactMarkdown from 'react-markdown';
import type { TStartupConfig } from 'librechat-data-provider';
import { useGetStartupConfig } from '~/data-provider';
import { useLocalize } from '~/hooks';

type FooterProps = {
  className?: string;
  startupConfig?: FooterStartupConfig | null;
};

type FooterStartupConfig = Pick<
  Partial<TStartupConfig>,
  'analyticsGtmId' | 'customFooter'
> & {
  interface?: Pick<NonNullable<TStartupConfig['interface']>, 'privacyPolicy' | 'termsOfService'>;
};

function NvidiaMark() {
  return (
    <svg
      height="0.9em"
      style={{ flex: 'none', lineHeight: 1 }}
      viewBox="0 0 24 24"
      width="0.9em"
      xmlns="http://www.w3.org/2000/svg"
      aria-hidden="true"
    >
      <title>NVIDIA</title>
      <path
        d="M10.212 8.976V7.62c.127-.01.256-.017.388-.021 3.596-.117 5.957 3.184 5.957 3.184s-2.548 3.647-5.282 3.647a3.227 3.227 0 01-1.063-.175v-4.109c1.4.174 1.681.812 2.523 2.258l1.873-1.627a4.905 4.905 0 00-3.67-1.846 6.594 6.594 0 00-.729.044m0-4.476v2.025c.1-.01.2-.019.3-.024 5.002-.174 8.261 4.226 8.261 4.226s-3.743 4.69-7.643 4.69c-.338 0-.675-.031-1.007-.092v1.25c.278.038.558.057.838.057 3.629 0 6.253-1.91 8.794-4.169.421.347 2.146 1.193 2.501 1.564-2.416 2.083-8.048 3.763-11.24 3.763-.308 0-.603-.02-.894-.048V19.5H24v-15H10.21zm0 9.756v1.068c-3.356-.616-4.287-4.21-4.287-4.21a7.173 7.173 0 014.287-2.138v1.172h-.005a3.182 3.182 0 00-2.502 1.178s.615 2.276 2.507 2.931m-5.961-3.3c1.436-1.935 3.604-3.148 5.961-3.336V6.523C5.81 6.887 2 10.723 2 10.723s2.158 6.427 8.21 7.015v-1.166C5.77 16 4.25 10.958 4.25 10.958h-.002z"
        fill="#76B900"
        fillRule="nonzero"
      />
    </svg>
  );
}

function Footer({ className, startupConfig }: FooterProps) {
  const shouldFetchConfig = startupConfig === undefined;
  const { data: fetchedConfig } = useGetStartupConfig({ enabled: shouldFetchConfig });
  const config = shouldFetchConfig ? fetchedConfig : startupConfig;
  const localize = useLocalize();

  const privacyPolicy = config?.interface?.privacyPolicy;
  const termsOfService = config?.interface?.termsOfService;

  const privacyPolicyRender = privacyPolicy?.externalUrl != null && (
    <a className="text-text-secondary underline" href={privacyPolicy.externalUrl} rel="noreferrer">
      {localize('com_ui_privacy_policy')}
    </a>
  );

  const termsOfServiceRender = termsOfService?.externalUrl != null && (
    <a className="text-text-secondary underline" href={termsOfService.externalUrl} rel="noreferrer">
      {localize('com_ui_terms_of_service')}
    </a>
  );

  const defaultContent = (
    <span className="inline-flex items-center gap-1.5">
      <span>Powered by</span>
      <span className="inline-flex items-center gap-0.5 font-semibold tracking-wide">
        <NvidiaMark />
        <span>NVIDIA</span>
      </span>
    </span>
  );

  const mainContentParts = (
    typeof config?.customFooter === 'string'
      ? config.customFooter
      : null
  );

  const mainContentRender =
    mainContentParts == null ? (
      [defaultContent]
    ) : (
      mainContentParts.split('|').map((text, index) => (
        <React.Fragment key={`main-content-part-${index}`}>
          <ReactMarkdown
            components={{
              a: ({ node: _n, href, children, ...otherProps }) => {
                return (
                  <a
                    className="text-text-secondary underline"
                    href={href}
                    target="_blank"
                    rel="noopener noreferrer"
                    {...otherProps}
                  >
                    {children}
                  </a>
                );
              },

              p: ({ node: _n, ...props }) => <span {...props} />,
            }}
          >
            {text.trim()}
          </ReactMarkdown>
        </React.Fragment>
      ))
    );

  const footerElements = [...mainContentRender, privacyPolicyRender, termsOfServiceRender].filter(
    Boolean,
  );

  return (
    <div className="relative w-full">
      <div
        className={
          className ??
          'absolute bottom-0 left-0 right-0 hidden items-center justify-center gap-2 px-2 py-2 text-center text-xs text-text-primary sm:flex md:px-[60px]'
        }
      >
        {footerElements.map((contentRender, index) => {
          const isLastElement = index === footerElements.length - 1;
          return (
            <React.Fragment key={`footer-element-${index}`}>
              {contentRender}
              {!isLastElement && (
                <div
                  key={`separator-${index}`}
                  className="h-2 border-r-[1px] border-border-medium"
                />
              )}
            </React.Fragment>
          );
        })}
      </div>
    </div>
  );
}

const MemoizedFooter = memo(Footer);
MemoizedFooter.displayName = 'Footer';

export default MemoizedFooter;
