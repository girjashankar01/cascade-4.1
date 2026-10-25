import { Icon } from './Icon'
export function StatusMark({ outcome }: { outcome: 'allowed' | 'blocked' }) {
  return <span className={`status-mark status-mark--${outcome}`}><Icon name={outcome === 'allowed' ? 'check' : 'stop'} />{outcome === 'allowed' ? 'Allowed' : 'Blocked'}</span>
}
