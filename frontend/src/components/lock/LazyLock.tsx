import { Component, lazy, Suspense } from 'react';
import type { ReactNode } from 'react';
import { Icon } from '../ui/Icon';

const LockObject = lazy(() => import('./LockObject'));

function LockFallback({ engaged }: { engaged: boolean }) {
  return (
    <div
      className="lock-fallback"
      role="img"
      aria-label={engaged ? 'The lock is engaged' : 'The lock is open'}
    >
      <Icon name={engaged ? 'lock' : 'unlock'} />
    </div>
  );
}

class LockBoundary extends Component<
  { children: ReactNode; engaged: boolean },
  { failed: boolean }
> {
  state = { failed: false };

  static getDerivedStateFromError() {
    return { failed: true };
  }

  render() {
    return this.state.failed ? (
      <LockFallback engaged={this.props.engaged} />
    ) : (
      this.props.children
    );
  }
}

export function LazyLock({ engaged }: { engaged: boolean }) {
  return (
    <div className="lock-frame">
      <LockBoundary engaged={engaged}>
        <Suspense fallback={<LockFallback engaged={engaged} />}>
          <LockObject engaged={engaged} />
        </Suspense>
      </LockBoundary>
    </div>
  );
}

export default LazyLock;
