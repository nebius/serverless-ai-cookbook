import React, { memo } from 'react';
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

// Existing NVIDIA artwork: green symbol and black wordmark. A white backing
// preserves those colors and legibility in both application themes.
function NvidiaLogo() {
  return (
    <svg
      height="14"
      width="77"
      style={{ flex: 'none', lineHeight: 1 }}
      viewBox="0 0 164 30"
      xmlns="http://www.w3.org/2000/svg"
      role="img"
      aria-label="NVIDIA"
    >
      <path
        d="M160.352,24.069L160.352,23.62L160.64,23.62C160.797,23.62 161.011,23.632 161.011,23.824C161.011,24.032 160.901,24.069 160.715,24.069L160.352,24.069M160.352,24.384L160.544,24.384L160.991,25.168L161.481,25.168L160.987,24.352C161.242,24.333 161.452,24.212 161.452,23.868C161.452,23.441 161.157,23.303 160.659,23.303L159.938,23.303L159.938,25.168L160.352,25.168L160.352,24.384M162.45,24.238C162.45,23.143 161.599,22.508 160.65,22.508C159.695,22.508 158.845,23.143 158.845,24.238C158.845,25.333 159.695,25.971 160.65,25.971C161.598,25.971 162.45,25.333 162.45,24.238M161.93,24.238C161.93,25.036 161.343,25.572 160.65,25.572L160.65,25.566C159.937,25.572 159.361,25.036 159.361,24.238C159.361,23.441 159.938,22.907 160.65,22.907C161.344,22.907 161.93,23.441 161.93,24.238"
        style={{ fill: '#000000' }}
      />
      <path
        d="M96.374,5.707L96.376,25.367L101.928,25.367L101.928,5.707L96.374,5.707ZM52.697,5.681L52.697,25.367L58.3,25.367L58.3,10.086L62.67,10.1C64.107,10.1 65.1,10.445 65.793,11.184C66.672,12.12 67.03,13.628 67.03,16.389L67.03,25.367L72.457,25.367L72.457,14.49C72.457,6.727 67.509,5.68 62.668,5.68L52.698,5.68L52.697,5.681ZM105.314,5.708L105.314,25.367L114.32,25.367C119.118,25.367 120.684,24.569 122.377,22.78C123.575,21.524 124.348,18.766 124.348,15.753C124.348,12.99 123.693,10.525 122.551,8.99C120.494,6.245 117.531,5.708 113.106,5.708L105.314,5.708ZM110.822,9.988L113.209,9.988C116.672,9.988 118.912,11.544 118.912,15.579C118.912,19.616 116.672,21.171 113.209,21.171L110.822,21.171L110.822,9.988ZM88.369,5.708L83.735,21.288L79.295,5.709L73.302,5.708L79.642,25.367L87.645,25.367L94.036,5.708L88.369,5.708ZM126.932,25.367L132.485,25.367L132.485,5.709L126.93,5.708L126.932,25.367ZM142.496,5.715L134.743,25.36L140.218,25.36L141.445,21.888L150.62,21.888L151.781,25.36L157.725,25.36L149.913,5.714L142.496,5.715ZM146.1,9.3L149.464,18.504L142.631,18.504L146.101,9.3L146.1,9.3Z"
        style={{ fill: '#000000' }}
      />
      <path
        d="M16.889,8.985L16.889,6.28C17.151,6.26 17.417,6.247 17.687,6.238C25.087,6.006 29.942,12.597 29.942,12.597C29.942,12.597 24.698,19.879 19.076,19.879C18.333,19.882 17.594,19.764 16.889,19.529L16.889,11.325C19.769,11.673 20.349,12.945 22.081,15.833L25.933,12.585C25.933,12.585 23.121,8.897 18.381,8.897C17.866,8.897 17.373,8.933 16.889,8.985ZM16.889,0.047L16.889,4.09C17.154,4.069 17.42,4.052 17.687,4.042C27.977,3.696 34.682,12.482 34.682,12.482C34.682,12.482 26.982,21.846 18.959,21.846C18.224,21.846 17.535,21.778 16.889,21.663L16.889,24.161C17.442,24.231 18.015,24.273 18.613,24.273C26.078,24.273 31.477,20.461 36.705,15.948C37.572,16.642 41.121,18.331 41.85,19.071C36.879,23.231 25.295,26.586 18.727,26.586C18.113,26.584 17.5,26.552 16.889,26.49L16.889,30L45.264,30L45.264,0.047L16.889,0.047ZM16.889,19.529L16.889,21.662C9.984,20.432 8.067,13.254 8.067,13.254C8.067,13.254 11.383,9.58 16.889,8.985L16.889,11.325L16.878,11.324C13.988,10.977 11.731,13.677 11.731,13.677C11.731,13.677 12.996,18.221 16.889,19.529ZM4.625,12.943C4.625,12.943 8.717,6.903 16.889,6.28L16.889,4.088C7.838,4.815 0,12.48 0,12.48C0,12.48 4.439,25.313 16.889,26.488L16.889,24.16C7.753,23.011 4.625,12.943 4.625,12.943Z"
        style={{ fill: 'rgb(118,185,0)' }}
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
    <span data-testid="powered-by-partners" className="inline-flex items-center justify-center gap-2">
      <span className="text-text-secondary">Powered by</span>
      <span className="inline-flex h-6 items-center rounded-md bg-white px-2">
        <NvidiaLogo />
      </span>
      <span className="text-text-secondary">and</span>
      <img src="/assets/logo.svg" alt="Nebius" width="87" height="24" className="h-6 w-auto shrink-0" />
    </span>
  );

  const mainContentParts = typeof config?.customFooter === 'string' ? config.customFooter : null;

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
