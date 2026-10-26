/* Motion Tokens & Helpers for Cascade 4.1 */
/* CSS custom properties remain the single source of truth */

export interface LockMotionConfig {
  duration: number;
  ease: [number, number, number, number];
  openY: number;
  closedY: number;
}

export function getLockMotion(reducedMotion: boolean): LockMotionConfig {
  if (typeof document === 'undefined') {
    return {
      duration: reducedMotion ? 0 : 0.6,
      ease: [0.2, 0, 0, 1],
      openY: -40,
      closedY: 0,
    };
  }

  const tokens = getComputedStyle(document.documentElement);
  const rawPoints = tokens.getPropertyValue('--motion-ease-points').trim();
  const ease: [number, number, number, number] = rawPoints
    ? (rawPoints.split(',').map(Number) as [number, number, number, number])
    : [0.2, 0, 0, 1];

  const explainRaw = tokens.getPropertyValue('--motion-duration-explain').trim();
  const duration = reducedMotion ? 0 : (explainRaw ? parseFloat(explainRaw) : 0.6);

  const restYRaw = tokens.getPropertyValue('--lock-rest-y').trim();
  const openY = restYRaw ? Number(restYRaw) : -40;

  const engagedYRaw = tokens.getPropertyValue('--lock-engaged-y').trim();
  const closedY = engagedYRaw ? Number(engagedYRaw) : 0;

  return {
    duration,
    ease,
    openY,
    closedY,
  };
}

export function getMotionDuration(tokenName: '--motion-duration-quick' | '--motion-duration-enter' | '--motion-duration-explain'): number {
  if (typeof document === 'undefined') return 0;
  const val = getComputedStyle(document.documentElement).getPropertyValue(tokenName).trim();
  return val ? parseFloat(val) : 0;
}
