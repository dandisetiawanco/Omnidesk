import React from "react";

interface BrandMarkProps {
  size?: number;
  decorative?: boolean;
}

export const BrandMark: React.FC<BrandMarkProps> = ({ size = 28, decorative = true }) => (
  <svg
    width={size}
    height={size}
    viewBox="0 0 64 64"
    fill="none"
    role={decorative ? undefined : "img"}
    aria-hidden={decorative ? "true" : undefined}
    aria-label={decorative ? undefined : "OmniDesk logo"}
  >
    <rect x="4" y="4" width="56" height="56" rx="14" fill="var(--text-primary)" />
    <path
      d="M21 15H43L49 21V43L43 49H21L15 43V21L21 15Z"
      stroke="var(--bg-surface)"
      strokeWidth="3"
      strokeLinejoin="round"
    />
    <path
      d="M25 25H39V39H25V25Z"
      stroke="var(--accent-text)"
      strokeWidth="3"
      strokeLinejoin="round"
    />
    <path
      d="M35 29L43 21"
      stroke="var(--accent-text)"
      strokeWidth="3"
      strokeLinecap="round"
    />
    <circle cx="32" cy="32" r="2.75" fill="var(--bg-surface)" />
  </svg>
);
