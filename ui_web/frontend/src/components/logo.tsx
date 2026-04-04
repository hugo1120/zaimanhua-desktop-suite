import React from "react";

interface LogoProps extends React.ComponentPropsWithoutRef<"svg"> {
  size?: number | string;
}

export function Logo({ size = 32, ...props }: LogoProps) {
  return (
    <svg
      width={size}
      height={size}
      viewBox="0 0 24 24"
      fill="none"
      xmlns="http://www.w3.org/2000/svg"
      {...props}
    >
      {/* 漫画气泡底座 (Comic Panel / Speech Bubble) */}
      <path
        d="M3 8C3 5.23858 5.23858 3 8 3H16C18.7614 3 21 5.23858 21 8V14C21 16.7614 18.7614 19 16 19H12L8 22V19H8C5.23858 19 3 16.7614 3 14V8Z"
        fill="currentColor"
      />
      {/* 镂空的锐利 Z 字 (Negative Space Z) */}
      <path
        d="M7 7.5H17L14.5 10.5M9.5 13.5L7 16.5H17"
        stroke="var(--bg-card, #fff)"
        strokeWidth="2.5"
        strokeLinecap="round"
        strokeLinejoin="round"
      />
      {/* 再 字的点睛笔画 (The Soul of ZAI) */}
      <circle cx="12" cy="12" r="1.2" fill="var(--bg-card, #fff)" />
    </svg>
  );
}
