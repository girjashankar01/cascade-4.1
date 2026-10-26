import { FileTextIcon, AlertTriangleIcon } from './Icons';

export function EmptyState({
  title,
  message,
  action,
}: {
  title: string;
  message: string;
  action?: React.ReactNode;
}) {
  return (
    <div
      style={{
        padding: 'var(--space-8)',
        textAlign: 'center',
        backgroundColor: 'var(--bg-surface)',
        borderRadius: 'var(--radius-lg)',
        border: '1px dashed var(--border-default)',
        display: 'flex',
        flexDirection: 'column',
        alignItems: 'center',
        gap: 'var(--space-2)',
      }}
    >
      <FileTextIcon style={{ width: 28, height: 28, color: 'var(--text-muted)', opacity: 0.6 }} />
      <h4 style={{ margin: 0, fontSize: 'var(--text-base)', color: 'var(--text-primary)' }}>{title}</h4>
      <p style={{ margin: 0, fontSize: 'var(--text-sm)', color: 'var(--text-secondary)', maxWidth: '420px' }}>
        {message}
      </p>
      {action && <div style={{ marginTop: 'var(--space-3)' }}>{action}</div>}
    </div>
  );
}

export function ErrorState({
  title = 'An error occurred',
  message,
  onRetry,
}: {
  title?: string;
  message: string;
  onRetry?: () => void;
}) {
  return (
    <div
      style={{
        padding: 'var(--space-5)',
        backgroundColor: 'rgba(239, 68, 68, 0.08)',
        borderRadius: 'var(--radius-lg)',
        border: '1px solid rgba(239, 68, 68, 0.25)',
        display: 'flex',
        alignItems: 'flex-start',
        gap: 'var(--space-3)',
      }}
    >
      <AlertTriangleIcon style={{ width: 20, height: 20, color: '#f87171', flexShrink: 0, marginTop: 2 }} />
      <div style={{ flex: 1 }}>
        <h4 style={{ margin: '0 0 4px', fontSize: 'var(--text-sm)', color: '#fca5a5' }}>{title}</h4>
        <p style={{ margin: 0, fontSize: 'var(--text-xs)', color: 'var(--text-secondary)' }}>{message}</p>
        {onRetry && (
          <button
            type="button"
            className="btn btn-secondary btn-sm"
            onClick={onRetry}
            style={{ marginTop: 'var(--space-3)' }}
          >
            Retry
          </button>
        )}
      </div>
    </div>
  );
}
