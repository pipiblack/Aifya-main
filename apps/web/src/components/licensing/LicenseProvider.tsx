"use client";

import { createContext, useContext, useMemo } from "react";
import { useLicense } from "@/hooks/useLicense";
import type { LicenseValidation, SubscriptionTier } from "@aifya/shared";

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
    const tier = (license?.tier ?? "community") as SubscriptionTier;
    const modules = new Set(license?.enabled_modules ?? []);
    const flags = license?.feature_flags ?? {};

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
