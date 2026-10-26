import { CheckCircleIcon, ArrowRightIcon, AlertTriangleIcon } from '../common/Icons';

export type LifecycleStage =
  | 'evidence'
  | 'claims'
  | 'manifest'
  | 'approval'
  | 'simulation'
  | 'verification'
  | 'attestation'
  | 'execution';

interface LifecycleStripProps {
  currentStage?: LifecycleStage;
  hasSources?: boolean;
  hasClaims?: boolean;
  hasConflicts?: boolean;
  hasManifest?: boolean;
  isApproved?: boolean;
  isVerified?: boolean;
  hasAttestation?: boolean;
  isExecuted?: boolean;
  onSelectStage?: (stage: LifecycleStage) => void;
}

export function LifecycleStrip({
  currentStage,
  hasSources = false,
  hasClaims = false,
  hasConflicts = false,
  hasManifest = false,
  isApproved = false,
  isVerified = false,
  hasAttestation = false,
  isExecuted = false,
  onSelectStage,
}: LifecycleStripProps) {
  const steps: {
    id: LifecycleStage;
    label: string;
    isComplete: boolean;
    isBlocked?: boolean;
  }[] = [
    { id: 'evidence', label: '1. Evidence', isComplete: hasSources },
    { id: 'claims', label: '2. Claims', isComplete: hasClaims },
    { id: 'manifest', label: '3. Manifest', isComplete: hasManifest, isBlocked: hasConflicts },
    { id: 'approval', label: '4. Approval', isComplete: isApproved },
    { id: 'simulation', label: '5. Simulation', isComplete: isVerified || hasAttestation },
    { id: 'verification', label: '6. Verification', isComplete: isVerified },
    { id: 'attestation', label: '7. Attestation', isComplete: hasAttestation },
    { id: 'execution', label: '8. Execution', isComplete: isExecuted },
  ];

  return (
    <div className="lifecycle-strip" role="region" aria-label="Governance Lifecycle Progression">
      {steps.map((step, idx) => {
        const isCurrent = currentStage === step.id;
        let stepClass = 'lifecycle-step';
        if (step.isBlocked) stepClass += ' blocked';
        else if (step.isComplete) stepClass += ' complete';
        if (isCurrent) stepClass += ' current';

        return (
          <div key={step.id} style={{ display: 'flex', alignItems: 'center', gap: 'var(--space-2)' }}>
            <button
              type="button"
              className={stepClass}
              onClick={() => onSelectStage && onSelectStage(step.id)}
              title={`Stage: ${step.label}`}
            >
              {step.isBlocked ? (
                <AlertTriangleIcon width={12} height={12} style={{ color: '#f87171' }} />
              ) : step.isComplete ? (
                <CheckCircleIcon width={12} height={12} style={{ color: '#34d399' }} />
              ) : (
                <span style={{ width: 8, height: 8, borderRadius: '50%', backgroundColor: 'var(--text-muted)', display: 'inline-block' }} />
              )}
              <span>{step.label}</span>
            </button>
            {idx < steps.length - 1 && <ArrowRightIcon className="lifecycle-arrow" width={10} height={10} />}
          </div>
        );
      })}
    </div>
  );
}
