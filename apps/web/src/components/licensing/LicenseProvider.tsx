"use client";

import { createContext, useContext, useMemo } from "react";
import { useLicense } from "@/hooks/useLicense";
import type { LicenseValidation, SubscriptionTier } from "@aifya/shared";

const TIER_ORDER: SubscriptionTier[] = [
  "community",
  "professional",
  "enterprise",
  "government",
];

const PROFESSIONAL_MODULES = [
  "patients",
  "encounters",
  "opd",
  "vitals",
  "billing",
  "ipd",
  "pharmacy",
  "laboratory",
  "radiology",
  "imaging",
  "appointments",
  "mch",
  "dental",
  "emergency",
  "theatre",
  "referrals",
  "insurance",
  "inventory",
  "hr",
  "reports",
  "finance",
  "analytics",
  "performance",
  "communications",
  "fhir",
  "fhir_api",
  "knowledge",
  "clinical_trials",
  "cds",
  "agents",
  "help",
  "help_bot",
  "federated",
  "scribe_ai",
  "claimflow_ai",
  "dhis2_sync",
  "mpesa_billing",
  "api_access",
  "multi_facility",
  "county_dashboard",
  "aggregate_reporting",
  "facility_comparison",
];

const PROFESSIONAL_FEATURE_FLAGS: Record<string, boolean> = {
  ai_features: true,
  custom_reports: true,
  api_access: false,
  data_export: true,
  white_label: false,
  priority_support: false,
  sla_guarantee: false,
  offline_mode: true,
  multi_language: true,
};

const FALLBACK_TIER = (
  process.env.NEXT_PUBLIC_DEFAULT_LICENSE_TIER ?? "professional"
) as SubscriptionTier;

function applyTierFloor(tier: SubscriptionTier): SubscriptionTier {
  return TIER_ORDER.indexOf(tier) >= TIER_ORDER.indexOf(FALLBACK_TIER)
    ? tier
    : FALLBACK_TIER;
}

/**
 * License context value — available to all child components.
 */
interface LicenseContextValue {
  /** Current tier: community | professional | enterprise | government */
  tier: SubscriptionTier;
  /** Full license validation data */
  license: LicenseValidation | undefined;
  /** Whether license data is still loading */
  isLoading: boolean;
  /** Check if a module is enabled */
  hasModule: (module: string) => boolean;
  /** Check if a feature flag is enabled */
  hasFeature: (flag: string) => boolean;
  /** Whether the license is in grace period */
  inGracePeriod: boolean;
  /** Whether an upgrade is available */
  upgradeAvailable: boolean;
  /** Days until expiry (null = no expiry) */
  daysRemaining: number | null;
}

const LicenseContext = createContext<LicenseContextValue>({
  tier: "community",
  license: undefined,
  isLoading: true,
  hasModule: () => true,
  hasFeature: () => false,
  inGracePeriod: false,
  upgradeAvailable: false,
  daysRemaining: null,
});

/**
 * Provider that fetches and caches facility license,
 * exposing tier info and entitlements to all child components.
 *
 * @param children - React child nodes
 * @returns Provider component
 */
export function LicenseProvider({ children }: { children: React.ReactNode }) {
  const { data: license, isLoading } = useLicense();

  const value = useMemo<LicenseContextValue>(() => {
    const tier = applyTierFloor((license?.tier ?? FALLBACK_TIER) as SubscriptionTier);
    const modules = new Set(license?.enabled_modules ?? []);
    const flags: Record<string, boolean> = { ...(license?.feature_flags ?? {}) };

    if (tier === "professional" && FALLBACK_TIER === "professional") {
      PROFESSIONAL_MODULES.forEach((module) => modules.add(module));
      Object.entries(PROFESSIONAL_FEATURE_FLAGS).forEach(([flag, enabled]) => {
        flags[flag] = flags[flag] === true || enabled;
      });
    }

    return {
      tier,
      license,
      isLoading,
      hasModule: (module: string) => modules.has(module),
      hasFeature: (flag: string) => flags[flag] === true,
      inGracePeriod: license?.in_grace_period ?? false,
      upgradeAvailable: license?.upgrade_available ?? false,
      daysRemaining: license?.days_remaining ?? null,
    };
  }, [license, isLoading]);

  return (
    <LicenseContext.Provider value={value}>
      {children}
    </LicenseContext.Provider>
  );
}

/**
 * Hook to access license context from any component.
 *
 * @returns License context value
 */
export function useLicenseContext() {
  return useContext(LicenseContext);
}
