"use client";

import type { ReactNode } from "react";
import { Sidebar } from "./Sidebar";
import { CommandPalette } from "@/components/ui/CommandPalette";
import { LicenseProvider, useLicenseContext } from "@/components/licensing/LicenseProvider";
import { UpdateChecker } from "@/components/licensing/UpdateChecker";
import { LicenseExpiryBanner } from "@/components/licensing/UpgradePrompt";
import { useTelemetry } from "@/hooks/useTelemetry";

/**
 * Inner shell that consumes LicenseContext for banners and telemetry.
 * @param props.children - Page content
 * @returns Inner layout with license banners
 */
function AppShellInner({ children }: { children: ReactNode }) {
  const { daysRemaining, inGracePeriod } = useLicenseContext();
  useTelemetry();

  return (
    <div className="flex h-screen overflow-hidden">
      <Sidebar />
      <div className="flex flex-1 flex-col overflow-hidden">
        <LicenseExpiryBanner
          daysRemaining={daysRemaining}
          inGracePeriod={inGracePeriod}
        />
        <UpdateChecker />
        <main className="flex-1 overflow-y-auto bg-background dark:bg-background">
          {children}
        </main>
      </div>
      <CommandPalette />
    </div>
  );
}

/**
 * Main application shell with sidebar, command palette, and license enforcement.
 * Wraps everything in LicenseProvider for tier-aware rendering.
 * @param props.children - Page content
 * @returns App shell layout
 */
export function AppShell({ children }: { children: ReactNode }) {
  return (
    <LicenseProvider>
      <AppShellInner>{children}</AppShellInner>
    </LicenseProvider>
  );
}
