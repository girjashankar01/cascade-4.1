import {
  CheckCircleIcon,
  XCircleIcon,
  AlertTriangleIcon,
  ShieldIcon,
  LockIcon,
} from './Icons';

interface StatusBadgeProps {
  status: string;
  size?: 'sm' | 'md';
}

export function StatusBadge({ status, size = 'md' }: StatusBadgeProps) {
  const norm = (status || '').toUpperCase();

  let className = 'badge badge-neutral';
  let Icon = ShieldIcon;

  if (norm === 'VERIFIED' || norm === 'PASS' || norm === 'GROUNDED' || norm === 'APPROVED' || norm === 'EXECUTED' || norm === 'MATCH' || norm === 'ALREADY_EXECUTED') {
    className = 'badge badge-verified';
    Icon = CheckCircleIcon;
  } else if (norm === 'MISMATCH' || norm === 'FAIL' || norm === 'REJECTED') {
    className = 'badge badge-mismatch';
    Icon = XCircleIcon;
  } else if (norm === 'UNCERTAIN' || norm === 'WARNING') {
    className = 'badge badge-uncertain';
    Icon = AlertTriangleIcon;
  } else if (norm === 'UNSUPPORTED' || norm === 'NOT_APPLICABLE' || norm === 'NOT_RUN') {
    className = 'badge badge-unsupported';
    Icon = LockIcon;
  }

  const sizeClass = size === 'sm' ? 'btn-sm' : '';

  return (
    <span className={`${className} ${sizeClass}`} role="status">
      <Icon width={12} height={12} />
      <span>{norm || 'UNKNOWN'}</span>
    </span>
  );
}
