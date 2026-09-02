import React from 'react'

export type IconName =
  | 'chart'
  | 'check'
  | 'circleCheck'
  | 'cookie'
  | 'close'
  | 'copy'
  | 'download'
  | 'external'
  | 'film'
  | 'phone'
  | 'upload'
  | 'user'

interface IconProps {
  name: IconName
  size?: number
  className?: string
}

const Icon: React.FC<IconProps> = ({ name, size = 16, className }) => {
  const commonProps = {
    fill: 'none',
    stroke: 'currentColor',
    strokeWidth: 1.8,
    strokeLinecap: 'round' as const,
    strokeLinejoin: 'round' as const,
  }

  return (
    <svg
      className={`ui-icon${className ? ` ${className}` : ''}`}
      width={size}
      height={size}
      viewBox="0 0 24 24"
      aria-hidden="true"
      focusable="false"
      {...commonProps}
    >
      {name === 'chart' && (
        <>
          <path d="M4 19V5" />
          <path d="M4 19h16" />
          <path d="M8 16v-5" />
          <path d="M12 16V7" />
          <path d="M16 16v-8" />
        </>
      )}
      {name === 'check' && <path d="m5 12 4 4L19 6" />}
      {name === 'circleCheck' && (
        <>
          <circle cx="12" cy="12" r="9" />
          <path d="m8 12 2.5 2.5L16.5 9" />
        </>
      )}
      {name === 'cookie' && (
        <>
          <circle cx="12" cy="12" r="8.5" />
          <circle cx="8.5" cy="8.8" r="1" fill="currentColor" stroke="none" />
          <circle cx="14.8" cy="8.8" r="1" fill="currentColor" stroke="none" />
          <circle cx="9.2" cy="14.8" r="1" fill="currentColor" stroke="none" />
          <circle cx="15.2" cy="15.4" r="1" fill="currentColor" stroke="none" />
        </>
      )}
      {name === 'close' && (
        <>
          <path d="m6 6 12 12" />
          <path d="m18 6-12 12" />
        </>
      )}
      {name === 'copy' && (
        <>
          <rect x="8" y="8" width="11" height="12" rx="2" />
          <path d="M16 8V6a2 2 0 0 0-2-2H6a2 2 0 0 0-2 2v9a2 2 0 0 0 2 2h2" />
        </>
      )}
      {name === 'download' && (
        <>
          <path d="M12 3v12" />
          <path d="m7 11 5 5 5-5" />
          <path d="M5 21h14" />
        </>
      )}
      {name === 'external' && (
        <>
          <path d="M14 4h6v6" />
          <path d="m20 4-9 9" />
          <path d="M18 13v5a2 2 0 0 1-2 2H6a2 2 0 0 1-2-2V8a2 2 0 0 1 2-2h5" />
        </>
      )}
      {name === 'film' && (
        <>
          <rect x="3" y="4" width="18" height="16" rx="2" />
          <path d="M8 4v16M16 4v16M3 9h5M16 9h5M3 15h5M16 15h5" />
        </>
      )}
      {name === 'phone' && (
        <>
          <rect x="7" y="2.5" width="10" height="19" rx="2" />
          <path d="M10 5h4" />
          <path d="M11 18.5h2" />
        </>
      )}
      {name === 'upload' && (
        <>
          <path d="M12 16V4" />
          <path d="m7 9 5-5 5 5" />
          <path d="M5 20h14" />
        </>
      )}
      {name === 'user' && (
        <>
          <circle cx="12" cy="8" r="3.5" />
          <path d="M5 20a7 7 0 0 1 14 0" />
        </>
      )}
    </svg>
  )
}

export default Icon