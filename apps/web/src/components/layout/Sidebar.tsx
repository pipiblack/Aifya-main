"use client";

import { useTranslations } from "next-intl";
import { usePathname } from "next/navigation";
import { Link } from "@/i18n/routing";
import {
  LayoutDashboard,
  Users,
  UserPlus,
  Stethoscope,
  BedDouble,
  Pill,
  FlaskConical,
  Receipt,
  BarChart3,
  Settings,
  LogOut,
  Moon,
  Sun,
  ChevronLeft,
  ChevronRight,
  Siren,
  Package,
  Scissors,
  ArrowUpRight,
  Shield,
  SmilePlus,
  Baby,
  CalendarClock,
  Scan,
  PersonStanding,
  Lock,
  Sparkles,
  BookOpen,
  Activity,
  MessageSquare,
  Plug,
} from "lucide-react";
import { useTheme } from "next-themes";
import { useState } from "react";
import { cn } from "@/lib/utils";
import { useLicenseContext } from "@/components/licensing/LicenseProvider";
import { recordModuleVisit } from "@/hooks/useTelemetry";

interface NavItem {
  key: string;
  href: string;
  icon: React.ComponentType<{ className?: string }>;
  /** Module name for license gating. Undefined = always visible. */
  module?: string;
  /** Visual separator before this item */
  separator?: boolean;
}

/** Tier badge colors */
const TIER_BADGE: Record<string, { bg: string; text: string }> = {
  community: { bg: "bg-gray-500/20", text: "text-gray-400" },
  professional: { bg: "bg-blue-500/20", text: "text-blue-400" },
  enterprise: { bg: "bg-purple-500/20", text: "text-purple-400" },
  government: { bg: "bg-green-500/20", text: "text-green-400" },
};

/**
 * App sidebar with navigation, facility branding, license tier, and dark mode toggle.
 * Per CLAUDE.md: facility logo in sidebar header, "Powered by Aifya" in footer.
 *
 * @returns Sidebar component
 */
export function Sidebar() {
  const t = useTranslations("nav");
  const tc = useTranslations("common");
  const ta = useTranslations("auth");
  const pathname = usePathname();
  const { theme, setTheme } = useTheme();
  const [collapsed, setCollapsed] = useState(false);
  const { hasModule, tier } = useLicenseContext();

  const navItems: NavItem[] = [
    { key: "dashboard", href: "/", icon: LayoutDashboard },
    { key: "patients", href: "/patients", icon: Users, module: "patients" },
    { key: "registration", href: "/patients/register", icon: UserPlus, module: "patients" },
    { key: "opd", href: "/opd", icon: Stethoscope, module: "opd", separator: true },
    { key: "ipd", href: "/ipd", icon: BedDouble, module: "ipd" },
    { key: "emergency", href: "/emergency", icon: Siren, module: "emergency" },
    { key: "pharmacy", href: "/pharmacy", icon: Pill, module: "pharmacy", separator: true },
    { key: "laboratory", href: "/laboratory", icon: FlaskConical, module: "laboratory" },
    { key: "radiology", href: "/radiology", icon: Scan, module: "radiology" },
    { key: "theatre", href: "/theatre", icon: Scissors, module: "theatre" },
    { key: "dental", href: "/dental", icon: SmilePlus, module: "dental" },
    { key: "mch", href: "/mch", icon: Baby, module: "mch" },
    { key: "billing", href: "/billing", icon: Receipt, module: "billing", separator: true },
    { key: "insurance", href: "/insurance", icon: Shield, module: "insurance" },
    { key: "inventory", href: "/inventory", icon: Package, module: "inventory" },
    { key: "appointments", href: "/appointments", icon: CalendarClock, module: "appointments", separator: true },
    { key: "referrals", href: "/referrals", icon: ArrowUpRight, module: "referrals" },
    { key: "hr", href: "/hr", icon: PersonStanding, module: "hr" },
    { key: "reports", href: "/reports", icon: BarChart3, module: "reports" },
    { key: "analytics", href: "/analytics", icon: Activity, module: "analytics" },
    { key: "communications", href: "/communications", icon: MessageSquare, module: "communications" },
    { key: "integrations", href: "/integrations/fhir", icon: Plug, module: "fhir" },
    { key: "trials", href: "/trials", icon: FlaskConical, module: "clinical_trials", separator: true },
    { key: "knowledge", href: "/knowledge", icon: BookOpen, module: "knowledge" },
    { key: "settings", href: "/settings", icon: Settings },
  ];

  const isActive = (href: string) => {
    if (href === "/") {
      return pathname.endsWith("/en") || pathname.endsWith("/sw") || pathname === "/";
    }
    const clean = pathname.replace(/^\/(en|sw)/, "");
    return clean.startsWith(href);
  };

  const tierBadge = TIER_BADGE[tier] ?? TIER_BADGE.community;

  return (
    <aside
      className={cn(
        "flex h-screen flex-col bg-sidebar transition-all duration-300 ease-in-out",
        collapsed ? "w-[68px]" : "w-64",
      )}
    >
      {/* Header — facility logo + collapse */}
      <div className="flex h-16 items-center justify-between px-4">
        {!collapsed && (
          <div className="flex items-center gap-2.5">
            <div className="flex h-9 w-9 items-center justify-center rounded-xl bg-primary text-sm font-bold text-primary-foreground shadow-sm">
              A
            </div>
            <div>
              <span className="text-base font-bold text-sidebar-foreground">
                Aifya
              </span>
              <span className={cn("ml-1.5 rounded-md px-1.5 py-0.5 text-[10px] font-semibold uppercase", tierBadge.bg, tierBadge.text)}>
                {tier}
              </span>
            </div>
          </div>
        )}
        {collapsed && (
          <div className="mx-auto flex h-9 w-9 items-center justify-center rounded-xl bg-primary text-sm font-bold text-primary-foreground shadow-sm">
            A
          </div>
        )}
      </div>

      {/* Collapse toggle */}
      <div className="px-3 pb-2">
        <button
          onClick={() => setCollapsed(!collapsed)}
          className="flex w-full items-center justify-center rounded-lg p-1.5 text-sidebar-foreground/50 transition-colors hover:bg-sidebar-muted hover:text-sidebar-foreground"
        >
          {collapsed ? (
            <ChevronRight className="h-4 w-4" />
          ) : (
            <ChevronLeft className="h-4 w-4" />
          )}
        </button>
      </div>

      {/* Navigation */}
      <nav className="flex-1 overflow-y-auto px-3 pb-2">
        <ul className="space-y-0.5">
          {navItems.map((item) => {
            const locked = item.module ? !hasModule(item.module) : false;
            const active = isActive(item.href);
            const Icon = item.icon;

            return (
              <li key={item.key}>
                {item.separator && (
                  <div className="my-2 border-t border-sidebar-border" />
                )}
                {locked ? (
                  <Link
                    href="/settings/billing"
                    className={cn(
                      "group flex items-center gap-3 rounded-lg px-3 py-2 text-sm transition-all duration-150",
                      "text-sidebar-foreground/25 hover:text-sidebar-foreground/40 hover:bg-sidebar-muted/30",
                    )}
                    title={collapsed ? t(item.key) : undefined}
                  >
                    <Icon className="h-[18px] w-[18px] flex-shrink-0" />
                    {!collapsed && (
                      <>
                        <span className="flex-1 truncate">{t(item.key)}</span>
                        <Lock className="h-3 w-3 opacity-50" />
                      </>
                    )}
                  </Link>
                ) : (
                  <Link
                    href={item.href}
                    onClick={() => item.module && recordModuleVisit(item.module)}
                    className={cn(
                      "group flex items-center gap-3 rounded-lg px-3 py-2 text-sm font-medium transition-all duration-150",
                      active
                        ? "bg-sidebar-accent/15 text-sidebar-accent shadow-sm"
                        : "text-sidebar-foreground/70 hover:bg-sidebar-muted hover:text-sidebar-foreground",
                    )}
                    title={collapsed ? t(item.key) : undefined}
                  >
                    <Icon className={cn("h-[18px] w-[18px] flex-shrink-0", active && "text-sidebar-accent")} />
                    {!collapsed && <span className="truncate">{t(item.key)}</span>}
                    {active && !collapsed && (
                      <div className="ml-auto h-1.5 w-1.5 rounded-full bg-sidebar-accent" />
                    )}
                  </Link>
                )}
              </li>
            );
          })}
        </ul>
      </nav>

      {/* Footer */}
      <div className="border-t border-sidebar-border px-3 py-3 space-y-1">
        {/* Dark mode toggle */}
        <button
          onClick={() => setTheme(theme === "dark" ? "light" : "dark")}
          className="flex w-full items-center gap-3 rounded-lg px-3 py-2 text-sm text-sidebar-foreground/60 transition-colors hover:bg-sidebar-muted hover:text-sidebar-foreground"
        >
          {theme === "dark" ? (
            <Sun className="h-[18px] w-[18px]" />
          ) : (
            <Moon className="h-[18px] w-[18px]" />
          )}
          {!collapsed && (
            <span>{theme === "dark" ? tc("themeLight") : tc("themeDark")}</span>
          )}
        </button>

        {/* Logout */}
        <button className="flex w-full items-center gap-3 rounded-lg px-3 py-2 text-sm text-sidebar-foreground/60 transition-colors hover:bg-sidebar-muted hover:text-sidebar-foreground">
          <LogOut className="h-[18px] w-[18px]" />
          {!collapsed && <span>{ta("logout")}</span>}
        </button>

        {/* Upgrade prompt for community tier */}
        {!collapsed && tier === "community" && (
          <Link
            href="/settings/billing"
            className="mt-2 flex items-center gap-2 rounded-lg bg-sidebar-muted px-3 py-2.5 text-xs text-sidebar-foreground/70 transition-colors hover:bg-sidebar-accent/10 hover:text-sidebar-accent"
          >
            <Sparkles className="h-4 w-4 text-amber-400" />
            <span className="font-medium">Upgrade to Professional</span>
          </Link>
        )}

        {/* Powered by Aifya */}
        {!collapsed && (
          <p className="pt-2 text-center text-[10px] text-sidebar-foreground/30">
            {tc("poweredBy")}
          </p>
        )}
      </div>
    </aside>
  );
}
