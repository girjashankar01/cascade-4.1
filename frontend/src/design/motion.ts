/** CSS is the source of truth, including reduced-motion durations. */
export function getLockMotion(reducedMotion: boolean) {
  const tokens = getComputedStyle(document.documentElement)
  const points = tokens.getPropertyValue('--motion-ease-points').split(',').map(Number)
  return {
    duration: reducedMotion ? 0 : parseFloat(tokens.getPropertyValue('--motion-duration-explain')),
    ease: points as [number, number, number, number],
    openY: Number(tokens.getPropertyValue('--lock-rest-y')),
    closedY: Number(tokens.getPropertyValue('--lock-engaged-y')),
  }
}
