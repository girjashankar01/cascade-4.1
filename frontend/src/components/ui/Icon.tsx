export type IconName = 'arrow' | 'check' | 'stop' | 'sun' | 'moon' | 'lock' | 'unlock' | 'reset' | 'workspace' | 'plus' | 'edit' | 'close' | 'scenario' | 'run' | 'result' | 'balances' | 'details' | 'menu'
const paths: Record<IconName, string> = {
  arrow: 'M4 12h16m-6-6 6 6-6 6',
  check: 'm5 12 4 4L19 6',
  stop: 'M8 3h8l5 5v8l-5 5H8l-5-5V8zM8 8l8 8m0-8-8 8',
  sun: 'M12 2v2m0 16v2M2 12h2m16 0h2M5 5l1.5 1.5m11 11L19 19M5 19l1.5-1.5m11-11L19 5M16 12a4 4 0 1 1-8 0 4 4 0 0 1 8 0',
  moon: 'M20.5 13.5A8.7 8.7 0 0 1 10.5 3a9 9 0 1 0 10 10.5Z',
  lock: 'M7 10V7a5 5 0 0 1 10 0v3M5 10h14v11H5zM12 14v3',
  unlock: 'M7 10V7a5 5 0 0 1 9-3M5 10h14v11H5zM12 14v3',
  reset: 'M4 10a8 8 0 1 1 .5 6M4 4v6h6',
  workspace: 'M3 5h18v14H3zM3 10h18M8 5v5',
  plus: 'M12 5v14M5 12h14',
  edit: 'm15 4 5 5M4 20l5-1L21 7l-5-5L4 14z',
  close: 'm6 6 12 12M6 18 18 6',
  scenario: 'M4 4h6v6H4zM14 4h6v6h-6zM4 14h6v6H4zM14 14h6v6h-6z',
  run: 'm8 4 12 8-12 8z',
  result: 'M5 3h14v18H5zM8 8h8m-8 4h8m-8 4h5',
  balances: 'M3 7h18v13H3zM3 7l13-4v4m0 6h5m-4 3h.01',
  details: 'M12 10v7m0-10h.01M21 12a9 9 0 1 1-18 0 9 9 0 0 1 18 0',
  menu: 'M4 6h16M4 12h16M4 18h16',
}
export function Icon({ name, className = '' }: { name: IconName; className?: string }) {
  return <svg className={`icon ${className}`} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true"><path d={paths[name]} /></svg>
}
