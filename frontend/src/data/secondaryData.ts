/**
 * secondaryData.ts — retained only for CoverageItem type used in tests.
 * Primary content is now inline in CoveragePage.tsx per PROJECT-TRUTH.md §9.
 * The paymentRequests and approvedPlans exports are REMOVED — pages now use
 * ProposalPage.tsx and ManifestPage.tsx respectively.
 */

export interface CoverageItem {
  title: string
  description: string
  tag: string
}

// These are now defined inline in CoveragePage.tsx to keep them aligned
// with PROJECT-TRUTH.md. Export stubs here to avoid breaking any remaining imports.
export const coverageGuarantees: CoverageItem[] = []
export const coverageLimitations: CoverageItem[] = []
