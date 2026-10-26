import { useId } from 'react'
import { LazyMotion, domAnimation, m, MotionConfig, useReducedMotion } from 'motion/react'
import { getLockMotion } from '../../design/motion'

export default function LockObject({ engaged }: { engaged: boolean }) {
  const id = useId().replaceAll(':', '')
  const reduced = useReducedMotion()
  const timing = getLockMotion(Boolean(reduced))
  const steel = `${id}-steel`
  const metal = `${id}-metal`
  const brass = `${id}-brass`
  return (
    <MotionConfig reducedMotion="user">
      <LazyMotion features={domAnimation} strict>
        <svg className="lock-object" viewBox="0 0 360 390" role="img" aria-label={engaged ? 'A solid metal lock with its shackle closed' : 'A solid metal lock with its shackle lifted open'}>
          <defs>
            <linearGradient id={steel} x1="120" y1="70" x2="235" y2="190" gradientUnits="userSpaceOnUse">
              <stop stopColor="var(--lock-steel-dark)" /><stop offset=".28" stopColor="var(--lock-steel-light)" /><stop offset=".55" stopColor="var(--lock-steel-mid)" /><stop offset=".8" stopColor="var(--lock-steel-light)" /><stop offset="1" stopColor="var(--lock-steel-dark)" />
            </linearGradient>
            <linearGradient id={metal} x1="110" y1="175" x2="250" y2="340" gradientUnits="userSpaceOnUse">
              <stop stopColor="var(--lock-metal-top)" /><stop offset=".4" stopColor="var(--lock-metal-mid)" /><stop offset="1" stopColor="var(--lock-metal-bottom)" />
            </linearGradient>
            <linearGradient id={brass} x1="150" y1="225" x2="210" y2="285" gradientUnits="userSpaceOnUse"><stop stopColor="var(--lock-brass-light)" /><stop offset="1" stopColor="var(--lock-brass-dark)" /></linearGradient>
          </defs>
          <ellipse cx="180" cy="359" rx="103" ry="12" fill="var(--lock-shadow)" opacity="var(--lock-shadow-opacity)" />
          <m.g initial={false} animate={{ y: engaged ? timing.closedY : timing.openY }} transition={{ duration: timing.duration, ease: timing.ease }}>
            <path d="M133 218v-89a47 47 0 0 1 94 0v67" fill="none" stroke="var(--lock-metal-edge)" strokeWidth="26" />
            <path d="M133 218v-90a47 47 0 0 1 94 0v65" fill="none" stroke={`url(#${steel})`} strokeWidth="22" />
            <path d="M125 184v-55a55 55 0 0 1 8-28" fill="none" stroke="var(--lock-steel-light)" strokeWidth="2" opacity="var(--lock-detail-opacity)" />
          </m.g>
          <path d="M110 174h140a14 14 0 0 1 14 14v135a22 22 0 0 1-22 22H118a22 22 0 0 1-22-22V188a14 14 0 0 1 14-14Z" fill="var(--lock-metal-edge)" />
          <rect x="96" y="170" width="168" height="168" rx="18" fill={`url(#${metal})`} />
          <path d="M111 172h138a13 13 0 0 1 13 13" fill="none" stroke="var(--lock-metal-highlight)" strokeWidth="2" />
          <rect x="106" y="181" width="148" height="145" rx="12" fill="none" stroke="var(--lock-metal-highlight)" opacity="var(--lock-detail-opacity)" />
          <path d="M113 321h134" stroke="var(--lock-metal-edge)" strokeWidth="2" />
          <circle cx="122" cy="198" r="4" fill="var(--lock-steel-dark)" /><path d="m120 196 4 4" stroke="var(--lock-steel-mid)" />
          <circle cx="238" cy="198" r="4" fill="var(--lock-steel-dark)" /><path d="m236 200 4-4" stroke="var(--lock-steel-mid)" />
          <circle cx="180" cy="254" r="32" fill="var(--lock-brass-edge)" /><circle cx="180" cy="252" r="30" fill={`url(#${brass})`} />
          <circle cx="180" cy="252" r="24" fill="none" stroke="var(--lock-brass-edge)" />
          <path d="M180 240a8 8 0 0 0-4 15l-3 12h14l-3-12a8 8 0 0 0-4-15Z" fill="var(--lock-keyhole)" />
          <path d="M152 296h56M164 303h32" stroke="var(--lock-metal-highlight)" opacity="var(--lock-detail-opacity)" />
        </svg>
      </LazyMotion>
    </MotionConfig>
  )
}
